# -*- coding: utf-8 -*-
"""단지 속성 사전·품질플래그 적용 — builder_norm·builder_group·brand (P2).

`collective_building_attributes`의 원문 컬럼(`builder_raw`)은 읽기만 하고,
판단이 들어간 파생 컬럼만 갱신한다. 사전 자체는
`pipeline/collective/danji_brand_dictionary.py`가 SSOT다.

K-apt 원본 이상값은 **지우지 않고 `attr_quality_flags`로 표시**한다 — 회귀에서
해당 변수를 결측 처리하되 그 사유를 사용자에게 노출해야 하기 때문이다
(`docs/COLLECTIVE_TWO_STAGE_HEDONIC_DESIGN.md` §0.1).

    py pipeline/collective/apply_danji_dictionary.py --snapshot-ym 202607
    py pipeline/collective/apply_danji_dictionary.py --snapshot-ym 202607 --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from collective.danji_brand_dictionary import (  # noqa: E402
    BRAND_META,
    builder_group,
    detect_brand,
    is_joint_construction,
    is_public_brand,
    is_public_builder,
    normalize_builder,
    split_joint_builders,
)
from collective.db_utils import get_collective_engine  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DICTIONARY_VERSION = "2026.08.09"

_TMP_TABLE = "_danji_dictionary_map"

# 국내 최고층 공동주택은 100층 내외(엘시티 101층) — 그 이상은 입력 오류로 본다.
# 하한 2층은 K-apt에 층수·동수가 1로 기록된 자리표시자를 잡는다(498세대 1동 1층 등).
MAX_PLAUSIBLE_FLOOR = 101
MIN_PLAUSIBLE_FLOOR = 3
# 세대당 주차 5대 초과는 세대수 오기입의 신호(실측 최대 97.8대 = 11세대·1,076면).
MAX_PLAUSIBLE_PARKING_PER_HOUSEHOLD = 5.0
# 층당 세대수 상한. 실측 분포(층수 3 이상)에서 p99=19.8이므로 20을 넘으면
# 세대수·동수·층수 중 하나가 틀린 것이다 — **어느 필드가 틀렸는지는 특정할 수 없다.**
MAX_HOUSEHOLDS_PER_FLOOR = 20


def _load(conn, snapshot_ym: str) -> pd.DataFrame:
    return pd.read_sql(
        text(
            """
            SELECT a.building_key,
                   a.snapshot_ym,
                   a.asset_type,
                   a.match_tier,
                   a.builder_raw,
                   COALESCE(m.danji_name, '') AS kapt_name,
                   a.households,
                   a.dong_count,
                   a.max_floor,
                   a.parking_per_household,
                   a.n_tx
            FROM collective_building_attributes a
            LEFT JOIN builder_master m
                   ON m.danji_code = a.danji_code
                  AND m.snapshot_ym = a.snapshot_ym
            WHERE a.snapshot_ym = :ym
            """
        ),
        conn,
        params={"ym": snapshot_ym},
    )


def _load_display_names(conn, keys: list[str]) -> dict[str, str]:
    """브랜드는 거래원장 display_name(실거래 단지명)에서 추출한다.

    K-apt 단지명이 아니라 원장 단지명을 쓰는 이유는, 미매칭 단지도 동일한
    규칙으로 브랜드를 뽑아야 브랜드 커버리지가 tier에 종속되지 않기 때문이다.
    """
    if not keys:
        return {}
    rows = conn.execute(
        text(
            """
            SELECT building_key, MAX(display_name) AS display_name
            FROM collective_transactions
            WHERE building_key = ANY(:keys)
            GROUP BY building_key
            """
        ),
        {"keys": keys},
    ).mappings().all()
    return {str(r["building_key"]): str(r["display_name"] or "") for r in rows}


def _quality_flags(row: pd.Series) -> str | None:
    """K-apt 원본 이상값 탐지. 값은 그대로 두고 코드만 남긴다."""
    flags: list[str] = []
    hh = row.get("households")
    dong = row.get("dong_count")
    floor = row.get("max_floor")
    pph = row.get("parking_per_household")

    if pd.notna(hh) and float(hh) <= 0:
        flags.append("hh_zero")
    floor_ok = pd.notna(floor) and MIN_PLAUSIBLE_FLOOR <= float(floor) <= MAX_PLAUSIBLE_FLOOR
    if pd.notna(floor) and not floor_ok:
        flags.append("floor_implausible")
    if pd.notna(pph) and float(pph) > MAX_PLAUSIBLE_PARKING_PER_HOUSEHOLD:
        flags.append("parking_implausible")
    # 세대수 ↔ 동수·층수 정합성. 층수가 이미 자리표시자면 이 검사는 의미가 없다.
    # 오피스텔은 호수 밀도가 아파트 층당 세대 상한을 자주 넘긴다 (지웰 509/15).
    if (
        str(row.get("asset_type") or "") != "officetel"
        and floor_ok
        and pd.notna(hh)
        and pd.notna(dong)
        and float(dong) > 0
        and float(hh) > 0
    ):
        if float(hh) / (float(dong) * float(floor)) > MAX_HOUSEHOLDS_PER_FLOOR:
            flags.append("scale_inconsistent")
    return ",".join(flags) if flags else None


def _multi_builder_label(raw: object) -> tuple[str | None, bool]:
    """D·F: 시공사가 둘 이상이면 첫 회사 + ' 외', 한 곳이면 그 이름만."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None, False
    text = str(raw)
    parts = split_joint_builders(text)
    if not parts:
        n = normalize_builder(text)
        return (n or None), False
    if len(parts) == 1:
        return parts[0], False
    return f"{parts[0]} 외", True


def _apply_multi_builder_labels(out: pd.DataFrame) -> pd.DataFrame:
    if "match_tier" not in out.columns:
        return out
    mask = out["match_tier"].isin(["D", "F"])
    if not mask.any():
        return out
    parsed = out.loc[mask, "builder_raw"].map(_multi_builder_label)
    out.loc[mask, "builder_norm"] = parsed.map(lambda p: p[0])
    out.loc[mask, "builder_group"] = parsed.map(lambda p: p[0])
    out.loc[mask, "builder_is_joint"] = parsed.map(lambda p: p[1])
    out.loc[mask, "builder_is_public"] = out.loc[mask, "builder_raw"].map(
        lambda r: is_public_builder(
            builder_group(None if r is None or (isinstance(r, float) and pd.isna(r)) else str(r))
        )
    )
    return out


def _derive(df: pd.DataFrame, names: dict[str, str]) -> pd.DataFrame:
    out = df.copy()
    out["builder_norm"] = out["builder_raw"].map(normalize_builder).replace("", None)
    out["builder_group"] = out["builder_raw"].map(builder_group)
    out["builder_is_joint"] = out["builder_raw"].map(is_joint_construction)
    out["builder_is_public"] = out["builder_group"].map(is_public_builder)

    source_name = out["building_key"].map(lambda k: names.get(str(k), ""))
    fallback = out["kapt_name"].fillna("")
    source_name = source_name.where(source_name.str.len() > 0, fallback)
    out["brand"] = source_name.map(detect_brand)
    out["brand_is_public"] = out["brand"].map(is_public_brand)
    out["brand_confidence"] = out["brand"].map(
        lambda b: (BRAND_META.get(b) or {}).get("confidence") if b else None
    )
    out["attr_quality_flags"] = out.apply(_quality_flags, axis=1)
    out["dictionary_version"] = DICTIONARY_VERSION
    return _apply_multi_builder_labels(out)


def _report(df: pd.DataFrame) -> None:
    total = len(df)
    tx_total = int(df["n_tx"].fillna(0).sum()) or 1
    has_group = df["builder_group"].notna()
    has_brand = df["brand"].notna()
    log.info("행 %s (거래 %s)", total, tx_total)
    log.info(
        "builder_group 채움 %s (%.1f%%) · 거래가중 %.1f%%",
        int(has_group.sum()),
        100 * has_group.mean(),
        100 * df.loc[has_group, "n_tx"].fillna(0).sum() / tx_total,
    )
    log.info(
        "brand 검출 %s (%.1f%%) · 거래가중 %.1f%% · 공동시공 %s",
        int(has_brand.sum()),
        100 * has_brand.mean(),
        100 * df.loc[has_brand, "n_tx"].fillna(0).sum() / tx_total,
        int(df["builder_is_joint"].fillna(False).sum()),
    )
    groups = (
        df[has_group]
        .groupby("builder_group")
        .agg(buildings=("building_key", "count"), tx=("n_tx", "sum"))
        .sort_values("tx", ascending=False)
    )
    log.info("기업집단 %s개 · 단지 30개 이상 %s개", len(groups), int((groups["buildings"] >= 30).sum()))
    for name, row in groups.head(10).iterrows():
        log.info("  %s 단지=%s 거래=%s", name, int(row.buildings), int(row.tx))
    brands = (
        df[has_brand]
        .groupby("brand")
        .agg(buildings=("building_key", "count"), tx=("n_tx", "sum"))
        .sort_values("tx", ascending=False)
    )
    log.info("브랜드 %s개 · 단지 30개 이상 %s개", len(brands), int((brands["buildings"] >= 30).sum()))

    flagged = df["attr_quality_flags"].dropna()
    log.info("품질 플래그 %s건 (%.2f%%)", len(flagged), 100 * len(flagged) / max(total, 1))
    if len(flagged):
        codes: dict[str, int] = {}
        for value in flagged:
            for code in str(value).split(","):
                codes[code] = codes.get(code, 0) + 1
        for code, cnt in sorted(codes.items(), key=lambda x: -x[1]):
            log.info("  %s=%s", code, cnt)


def _write(conn, df: pd.DataFrame) -> int:
    cols = [
        "building_key",
        "snapshot_ym",
        "builder_norm",
        "builder_group",
        "builder_is_joint",
        "builder_is_public",
        "brand",
        "brand_is_public",
        "brand_confidence",
        "attr_quality_flags",
        "dictionary_version",
    ]
    payload = df[cols].where(pd.notna(df[cols]), None)
    conn.execute(text(f"DROP TABLE IF EXISTS {_TMP_TABLE}"))
    conn.execute(
        text(
            f"""
            CREATE TEMP TABLE {_TMP_TABLE} (
                building_key CHAR(64),
                snapshot_ym CHAR(6),
                builder_norm VARCHAR(200),
                builder_group VARCHAR(200),
                builder_is_joint BOOLEAN,
                builder_is_public BOOLEAN,
                brand VARCHAR(80),
                brand_is_public BOOLEAN,
                brand_confidence VARCHAR(10),
                attr_quality_flags VARCHAR(120),
                dictionary_version VARCHAR(20)
            )
            """
        )
    )
    payload.to_sql(_TMP_TABLE, conn, if_exists="append", index=False)
    result = conn.execute(
        text(
            f"""
            UPDATE collective_building_attributes a
               SET builder_norm = m.builder_norm,
                   builder_group = m.builder_group,
                   builder_is_joint = m.builder_is_joint,
                   builder_is_public = m.builder_is_public,
                   brand = m.brand,
                   brand_is_public = m.brand_is_public,
                   brand_confidence = m.brand_confidence,
                   attr_quality_flags = m.attr_quality_flags,
                   dictionary_version = m.dictionary_version
              FROM {_TMP_TABLE} m
             WHERE a.building_key = m.building_key
               AND a.snapshot_ym = m.snapshot_ym
            """
        )
    )
    conn.execute(text(f"DROP TABLE IF EXISTS {_TMP_TABLE}"))
    return int(result.rowcount or 0)


def main() -> None:
    ap = argparse.ArgumentParser(description="단지 속성 사전 적용 (P2)")
    ap.add_argument("--snapshot-ym", default="202607")
    ap.add_argument("--dry-run", action="store_true", help="DB 쓰기 없이 리포트만")
    args = ap.parse_args()

    eng = get_collective_engine()
    with eng.begin() as conn:
        df = _load(conn, args.snapshot_ym)
        if df.empty:
            log.error("collective_building_attributes 에 snapshot_ym=%s 행이 없습니다 (P1 먼저 실행)", args.snapshot_ym)
            raise SystemExit(1)
        names = _load_display_names(conn, df["building_key"].astype(str).tolist())
        derived = _derive(df, names)
        _report(derived)
        if args.dry_run:
            log.info("dry-run — DB 미변경")
            return
        updated = _write(conn, derived)
        log.info("갱신 행 %s (dictionary_version=%s)", updated, DICTIONARY_VERSION)


if __name__ == "__main__":
    main()
