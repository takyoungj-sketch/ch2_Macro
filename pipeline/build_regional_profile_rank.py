#!/usr/bin/env python3
"""
regional_profile → 같은 grain 전국 순위 마트 (D-053).

라이브 JSONB ORDER BY 를 피하고, 프로필 재빌드 끝에 한 번 쌓는다.

  python build_regional_profile_rank.py
  python build_regional_profile_rank.py --profile-version v2.1-national --window-years 3
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Engine

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import default_as_of_month, parse_as_of_month  # noqa: E402
from collective.db_utils import get_collective_engine, get_land_engine_for_region_copy  # noqa: E402

log = logging.getLogger(__name__)

DDL_PATH = REPO / "db" / "070_regional_profile_rank.sql"
DEFAULT_PROFILE_VERSION = "v2.1-national"
MIX_TYPES = (
    "토지",
    "상가",
    "공장",
    "단독다가구",
    "아파트",
    "오피스텔",
    "연립다세대",
    "분양권",
)

SIDO_SHORT = {
    "11": "서울",
    "12": "전남광주",
    "26": "부산",
    "27": "대구",
    "28": "인천",
    "30": "대전",
    "31": "울산",
    "36": "세종",
    "41": "경기",
    "43": "충북",
    "44": "충남",
    "47": "경북",
    "48": "경남",
    "50": "제주",
    "51": "강원",
    "52": "전북",
}

SIDO_FULL = {
    "11": "서울특별시",
    "12": "전남광주통합특별시",
    "26": "부산광역시",
    "27": "대구광역시",
    "28": "인천광역시",
    "30": "대전광역시",
    "31": "울산광역시",
    "36": "세종특별자치시",
    "41": "경기도",
    "43": "충청북도",
    "44": "충청남도",
    "47": "경상북도",
    "48": "경상남도",
    "50": "제주특별자치도",
    "51": "강원특별자치도",
    "52": "전북특별자치도",
}


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Pearson r. n<3 또는 한쪽 분산 0이면 None."""
    n = len(xs)
    if n < 3 or n != len(ys):
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = 0.0
    dx = 0.0
    dy = 0.0
    for x, y in zip(xs, ys):
        vx = x - mx
        vy = y - my
        num += vx * vy
        dx += vx * vx
        dy += vy * vy
    if dx <= 0.0 or dy <= 0.0:
        return None
    return num / (dx * dy) ** 0.5


def type_share_corr(items: Sequence[dict[str, Any]], bucket: str) -> dict[str, Any]:
    """유형 비중(지역 합=1)의 단면 Pearson 행렬. bucket=type_amounts|type_counts."""
    series: dict[str, list[float]] = {t: [] for t in MIX_TYPES}
    n = 0
    for x in items:
        tot = sum(float(x[bucket][t]) for t in MIX_TYPES)
        if tot <= 0:
            continue
        n += 1
        for t in MIX_TYPES:
            series[t].append(float(x[bucket][t]) / tot)
    matrix: list[list[float | None]] = []
    for a in MIX_TYPES:
        row: list[float | None] = []
        for b in MIX_TYPES:
            if a == b:
                row.append(1.0 if n >= 3 else None)
            else:
                r = pearson(series[a], series[b])
                row.append(round(r, 4) if r is not None else None)
        matrix.append(row)
    return {"types": list(MIX_TYPES), "n": n, "matrix": matrix}


def competition_ranks_desc(values: Sequence[float]) -> list[int]:
    """SQL RANK() — 동점이면 같은 위, 다음은 건너뛴다 (1,2,2,4)."""
    n = len(values)
    ranks = [0] * n
    if n == 0:
        return ranks
    order = sorted(range(n), key=lambda i: values[i], reverse=True)
    for pos, i in enumerate(order):
        if pos > 0 and values[i] == values[order[pos - 1]]:
            ranks[i] = ranks[order[pos - 1]]
        else:
            ranks[i] = pos + 1
    return ranks


def ranks_per_capita(amounts: Sequence[float], populations: Sequence[int | None]) -> list[int | None]:
    """인구 > 0 인 행만 분모. 나머지 None."""
    idx = [i for i, p in enumerate(populations) if p is not None and p > 0]
    out: list[int | None] = [None] * len(amounts)
    if not idx:
        return out
    ratios = [amounts[i] / float(populations[i]) for i in idx]  # type: ignore[arg-type]
    sub = competition_ranks_desc(ratios)
    for i, r in zip(idx, sub):
        out[i] = r
    return out


def _sido_short(code: str) -> str:
    return SIDO_SHORT.get(str(code)[:2], str(code)[:2])


def _city_token(sigungu_name: str) -> str:
    tok = (sigungu_name or "").strip().split()[0] if sigungu_name else ""
    return tok or (sigungu_name or "").strip()


def _looks_like_dong(name: str) -> bool:
    n = (name or "").strip()
    if n.endswith(("시", "군", "구")):
        return False
    return n.endswith(("동", "가"))


def _join_label(*parts: str) -> str:
    """연속 중복 토큰 제거 — '서울 역삼동 역삼동' → '서울 역삼동'."""
    out: list[str] = []
    for raw in parts:
        p = (raw or "").strip()
        if not p:
            continue
        if out and out[-1] == p:
            continue
        out.append(p)
    return " ".join(out)


def _sigungu_label(
    code: str,
    row: dict[str, str] | None,
    names: dict[str, dict[str, dict[str, str]]],
) -> str:
    key = str(code).strip()[:5]
    mapped = names.get("sigungu", {}).get(key)
    if mapped and mapped.get("sigungu_name"):
        return mapped["sigungu_name"]
    return (row or {}).get("sigungu_name") or ""


def _apply_ddl(engine: Engine) -> None:
    sql = DDL_PATH.read_text(encoding="utf-8")
    cleaned: list[str] = []
    for stmt in sql.split(";"):
        body = "\n".join(
            ln for ln in stmt.splitlines() if not ln.strip().startswith("--")
        ).strip()
        if body:
            cleaned.append(body)
    with engine.begin() as conn:
        for stmt in cleaned:
            conn.execute(text(stmt))


def _load_name_rows(land_eng: Engine) -> dict[str, dict[str, dict[str, str]]]:
    maps: dict[str, dict[str, dict[str, str]]] = {
        "beopjungri": {},
        "eupmyeondong": {},
        "sigungu": {},
        "city": {},
    }
    sql = """
        SELECT sido_code, sido_name, sigungu_code, sigungu_name,
               eupmyeondong_code, eupmyeondong_name,
               beopjungri_code, beopjungri_name
        FROM region_codes
    """
    with land_eng.connect() as conn:
        if not conn.execute(text("SELECT to_regclass('public.region_codes') IS NOT NULL")).scalar():
            log.warning("land region_codes 없음 — 순위 이름은 코드로 대체")
            return maps
        rows = conn.execute(text(sql)).mappings().all()
    for r in rows:
        beop = str(r["beopjungri_code"] or "").strip()
        eup = str(r["eupmyeondong_code"] or "").strip()
        sg = str(r["sigungu_code"] or "").strip()
        payload = {
            "sido_code": str(r["sido_code"] or "").strip(),
            "sido_name": str(r["sido_name"] or "").strip(),
            "sigungu_name": str(r["sigungu_name"] or "").strip(),
            "eupmyeondong_name": str(r["eupmyeondong_name"] or "").strip(),
            "beopjungri_name": str(r["beopjungri_name"] or "").strip(),
        }
        if beop and beop not in maps["beopjungri"]:
            maps["beopjungri"][beop] = payload
        if eup and eup not in maps["eupmyeondong"]:
            maps["eupmyeondong"][eup] = payload
        if sg:
            prev = maps["sigungu"].get(sg)
            if prev is None:
                maps["sigungu"][sg] = payload
            elif _looks_like_dong(prev.get("sigungu_name") or "") and not _looks_like_dong(
                payload["sigungu_name"]
            ):
                maps["sigungu"][sg] = payload
            try:
                city = str(int(sg) // 10 * 10).zfill(5)
            except ValueError:
                city = ""
            if city and city not in maps["city"]:
                maps["city"][city] = payload
    return maps


def name_short(level: str, code: str, names: dict[str, dict[str, dict[str, str]]]) -> str:
    code = str(code).strip()
    if level == "sido":
        return SIDO_FULL.get(code[:2], _sido_short(code))
    if level == "city":
        row = names["city"].get(code)
        if row:
            tok = _city_token(row["sigungu_name"])
            return _join_label(_sido_short(code), tok)
        return code
    if level == "sigungu":
        if code == "36110":
            return "세종 전체"
        row = names["sigungu"].get(code)
        if row:
            return _join_label(_sido_short(code), row["sigungu_name"])
        return code
    if level == "eupmyeondong":
        row = names["eupmyeondong"].get(code)
        if row:
            sg = _sigungu_label(code, row, names)
            eup = row["eupmyeondong_name"]
            if row.get("sido_code") == "36":
                return _join_label("세종", sg or row.get("sigungu_name") or "")
            return _join_label(_sido_short(code), sg, eup)
        return code
    if level == "beopjungri":
        row = names["beopjungri"].get(code)
        if row:
            sg = _sigungu_label(code, row, names)
            eup = row["eupmyeondong_name"]
            beop = row["beopjungri_name"]
            if row.get("sido_code") == "36":
                return _join_label("세종", row.get("sigungu_name") or "", beop)
            return _join_label(_sido_short(code), sg, eup, beop)
        return code
    return code


def _mix_cell(mix: dict[str, Any], type_name: str, key: str) -> float:
    totals = mix.get("totals_by_type") or {}
    cell = totals.get(type_name) or {}
    if not isinstance(cell, dict):
        return 0.0
    try:
        return float(cell.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def refresh_regional_profile_rank(
    coll_eng: Engine,
    land_eng: Engine | None,
    *,
    profile_version: str,
    window_years: int,
    as_of: date | None,
) -> dict[str, int]:
    _apply_ddl(coll_eng)
    names = _load_name_rows(land_eng) if land_eng is not None else {
        "beopjungri": {},
        "eupmyeondong": {},
        "sigungu": {},
        "city": {},
    }

    params: dict[str, Any] = {"pv": profile_version, "wy": window_years}
    as_of_sql = ""
    if as_of is not None:
        as_of_sql = "AND as_of_month = :as_of"
        params["as_of"] = as_of

    fetch_sql = f"""
        SELECT region_level, region_code, as_of_month, features
        FROM regional_profile
        WHERE profile_version = :pv
          AND window_years = :wy
          {as_of_sql}
    """
    with coll_eng.connect() as conn:
        if not conn.execute(text("SELECT to_regclass('public.regional_profile') IS NOT NULL")).scalar():
            raise SystemExit("regional_profile 없음")
        rows = conn.execute(text(fetch_sql), params).mappings().all()

    if not rows:
        log.warning("regional_profile 행 없음 version=%s window=%s as_of=%s", profile_version, window_years, as_of)
        return {}

    grouped: dict[Any, list] = defaultdict(list)
    for r in rows:
        grouped[r["as_of_month"]].append(r)
    as_of_keys = [as_of] if as_of is not None else sorted(grouped.keys())

    rank_rows: list[dict[str, Any]] = []
    mix_rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}

    for as_of_i in as_of_keys:
        chunk = grouped.get(as_of_i) or []
        by_level: dict[str, list[dict[str, Any]]] = {}
        for r in chunk:
            feats = r["features"] or {}
            if not isinstance(feats, dict):
                feats = dict(feats)
            mix = feats.get("yearly_mix") or {}
            if not isinstance(mix, dict):
                mix = {}
            pop_raw = feats.get("population")
            pop: int | None
            try:
                pop = int(pop_raw) if pop_raw is not None else None
            except (TypeError, ValueError):
                pop = None
            if pop is not None and pop <= 0:
                pop = None
            try:
                amount = float(mix.get("total_amount_3y") or 0)
            except (TypeError, ValueError):
                amount = 0.0
            try:
                count = int(mix.get("total_count_3y") or 0)
            except (TypeError, ValueError):
                count = 0
            level = str(r["region_level"])
            code = str(r["region_code"]).strip()
            type_counts = {t: _mix_cell(mix, t, "count") for t in MIX_TYPES}
            type_amounts = {t: _mix_cell(mix, t, "amount") for t in MIX_TYPES}
            by_level.setdefault(level, []).append(
                {
                    "code": code,
                    "pop": pop,
                    "amount": amount,
                    "count": count,
                    "type_counts": type_counts,
                    "type_amounts": type_amounts,
                }
            )

        for level, items in by_level.items():
            amounts = [x["amount"] for x in items]
            counts_v = [float(x["count"]) for x in items]
            pops = [x["pop"] for x in items]
            ra = competition_ranks_desc(amounts)
            rc = competition_ranks_desc(counts_v)
            rp = ranks_per_capita(amounts, pops)
            n_cap = sum(1 for p in pops if p is not None)
            sum_c = {t: 0.0 for t in MIX_TYPES}
            sum_a = {t: 0.0 for t in MIX_TYPES}
            for x in items:
                for t in MIX_TYPES:
                    sum_c[t] += x["type_counts"][t]
                    sum_a[t] += x["type_amounts"][t]
            tot_c = sum(sum_c.values()) or 0.0
            tot_a = sum(sum_a.values()) or 0.0
            share_c = {t: round(sum_c[t] / tot_c, 6) if tot_c > 0 else 0.0 for t in MIX_TYPES}
            share_a = {t: round(sum_a[t] / tot_a, 6) if tot_a > 0 else 0.0 for t in MIX_TYPES}
            type_corr = {
                "amount": type_share_corr(items, "type_amounts"),
                "count": type_share_corr(items, "type_counts"),
            }
            mix_rows.append(
                {
                    "profile_version": profile_version,
                    "as_of": as_of_i,
                    "window_years": window_years,
                    "level": level,
                    "universe_n": len(items),
                    "n_per_capita": n_cap,
                    "share_count": json.dumps(share_c, ensure_ascii=False),
                    "share_amount": json.dumps(share_a, ensure_ascii=False),
                    "type_corr": json.dumps(type_corr, ensure_ascii=False),
                }
            )
            for i, x in enumerate(items):
                rank_rows.append(
                    {
                        "profile_version": profile_version,
                        "as_of": as_of_i,
                        "window_years": window_years,
                        "level": level,
                        "code": x["code"],
                        "name_short": name_short(level, x["code"], names),
                        "population": x["pop"],
                        "amount_3y": x["amount"],
                        "count_3y": x["count"],
                        "rank_amount": ra[i],
                        "rank_count": rc[i],
                        "rank_per_capita": rp[i],
                    }
                )
            key = f"{as_of_i}:{level}"
            counts[key] = len(items)
            if level == "sigungu" and len(items) < 200:
                log.warning("sigungu n=%s as_of=%s (may not be national)", len(items), as_of_i)

    insert_rank = text(
        """
        INSERT INTO regional_profile_rank (
            profile_version, as_of_month, window_years, region_level, region_code,
            name_short, population, amount_3y, count_3y,
            rank_amount, rank_count, rank_per_capita
        ) VALUES (
            :profile_version, :as_of, :window_years, :level, :code,
            :name_short, :population, :amount_3y, :count_3y,
            :rank_amount, :rank_count, :rank_per_capita
        )
        """
    )
    insert_mix = text(
        """
        INSERT INTO regional_profile_national_mix (
            profile_version, as_of_month, window_years, region_level,
            universe_n, n_per_capita, share_count, share_amount, type_corr
        ) VALUES (
            :profile_version, :as_of, :window_years, :level,
            :universe_n, :n_per_capita, CAST(:share_count AS jsonb), CAST(:share_amount AS jsonb),
            CAST(:type_corr AS jsonb)
        )
        """
    )
    with coll_eng.begin() as conn:
        if as_of is None:
            conn.execute(
                text(
                    """
                    DELETE FROM regional_profile_rank
                    WHERE profile_version = :pv AND window_years = :wy
                    """
                ),
                {"pv": profile_version, "wy": window_years},
            )
            conn.execute(
                text(
                    """
                    DELETE FROM regional_profile_national_mix
                    WHERE profile_version = :pv AND window_years = :wy
                    """
                ),
                {"pv": profile_version, "wy": window_years},
            )
        else:
            conn.execute(
                text(
                    """
                    DELETE FROM regional_profile_rank
                    WHERE profile_version = :pv AND window_years = :wy AND as_of_month = :as_of
                    """
                ),
                {"pv": profile_version, "wy": window_years, "as_of": as_of},
            )
            conn.execute(
                text(
                    """
                    DELETE FROM regional_profile_national_mix
                    WHERE profile_version = :pv AND window_years = :wy AND as_of_month = :as_of
                    """
                ),
                {"pv": profile_version, "wy": window_years, "as_of": as_of},
            )
        if rank_rows:
            conn.execute(insert_rank, rank_rows)
        if mix_rows:
            conn.execute(insert_mix, mix_rows)

    log.info(
        "regional_profile_rank upserted %s rows levels=%s",
        len(rank_rows),
        counts,
    )
    return counts


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    p = argparse.ArgumentParser(description="regional_profile 전국 순위 마트 (D-053)")
    p.add_argument("--as-of", type=str, default=None)
    p.add_argument("--window-years", type=int, default=3)
    p.add_argument("--profile-version", type=str, default=DEFAULT_PROFILE_VERSION)
    args = p.parse_args()
    as_of = parse_as_of_month(args.as_of) if args.as_of else None
    coll = get_collective_engine()
    try:
        land = get_land_engine_for_region_copy()
    except Exception as exc:  # noqa: BLE001
        log.warning("land engine 실패 (%s) — 이름은 코드", exc)
        land = None
    refresh_regional_profile_rank(
        coll,
        land,
        profile_version=args.profile_version,
        window_years=args.window_years,
        as_of=as_of,
    )


if __name__ == "__main__":
    main()
