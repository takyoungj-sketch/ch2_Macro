"""
GUKTO 정제 xlsx → built_transactions 적재.

  일반상가_정제.xlsx  (상업, 집합 제외됨)
  공장창고_매매_정제.xlsx (유형=집합 행 drop)
  단독다가구_매매_정제.xlsx (주택유형→building_use, 용도지역 없음)
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from db_utils import get_built_engine, get_land_engine_for_region_copy

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[2]
DEFAULT_COMMERCIAL = Path(r"C:\startcoding\GUKTO\상업업무용_매매\상업업무용_매매_정제\일반상가_정제.xlsx")
DEFAULT_FACTORY = Path(r"C:\startcoding\GUKTO\공장창고_매매\공장창고_매매_정제\공장창고_매매_정제.xlsx")
DEFAULT_DETACHED = Path(
    r"C:\startcoding\GUKTO\단독다가구_매매\단독다가구_매매_정제\단독다가구_매매_정제.xlsx"
)
DDL = REPO / "db" / "015_built_transactions.sql"

COL_MAP = {
    "주1": "addr1",
    "주2": "addr2",
    "주3": "addr3",
    "주4": "addr4",
    "주5": "addr5",
    "번지": "lot_number",
    "거래연도": "trade_year_label",
    "용도지역": "zone_type",
    "건축물용도": "building_use",
    "유형": "building_use",  # 단독다가구 주택유형 → building_use 통일
    "건축규모": "building_scale",
    "대지규모": "land_scale",
    "연식구분": "age_bucket",
    "금액": "price",
    "연면적": "gross_area",
    "대지면적": "land_area",
    "연식": "building_age",
    "도로": "road_code",
    "층": "floor",
}


def _parse_contract_year(label: object) -> int | None:
    if label is None or (isinstance(label, float) and pd.isna(label)):
        return None
    s = str(label).strip().replace("'", "").replace("‘", "")
    if not s:
        return None
    if s.isdigit():
        n = int(s)
        if n < 100:
            return 2000 + n
        return n
    return None


def _tx_hash(row: dict) -> str:
    parts = [
        row.get("asset_type", ""),
        row.get("addr1", ""),
        row.get("addr2", ""),
        row.get("addr3", ""),
        row.get("addr4", ""),
        row.get("addr5", ""),
        row.get("lot_number", ""),
        str(row.get("contract_year", "")),
        str(row.get("price", "")),
        str(row.get("gross_area", "")),
        str(row.get("building_use", "")),
    ]
    return hashlib.sha256("|".join(str(p) if p is not None else "" for p in parts).encode("utf-8")).hexdigest()


def _normalize_df(df: pd.DataFrame, asset_type: str) -> pd.DataFrame:
    rename = {k: v for k, v in COL_MAP.items() if k in df.columns}
    out = df.rename(columns=rename).copy()
    if "유형" in df.columns and "building_use" not in out.columns:
        out["building_use"] = df["유형"]
    if asset_type == "factory" and "유형" in df.columns:
        mask = df["유형"].astype(str).str.strip() != "집합"
        out = out.loc[mask].copy()
    for c in set(COL_MAP.values()):
        if c not in out.columns:
            out[c] = None
    if asset_type == "detached":
        out["zone_type"] = None
    out["asset_type"] = asset_type
    out["deal_form"] = "general"
    out["contract_year"] = out["trade_year_label"].map(_parse_contract_year)
    out["contract_month"] = None
    out["contract_date"] = None
    out["is_valid"] = True
    for num in (
        "building_scale",
        "land_scale",
        "age_bucket",
        "price",
        "gross_area",
        "land_area",
        "building_age",
        "road_code",
        "floor",
    ):
        out[num] = pd.to_numeric(out[num], errors="coerce")
    if "road_code" in out.columns:
        out["road_code"] = out["road_code"].replace("-", pd.NA)
        out["road_code"] = pd.to_numeric(out["road_code"], errors="coerce")
    out = out.dropna(subset=["price", "gross_area"])
    out = out[out["gross_area"] > 0]
    return out


def _load_region_lookup(engine) -> dict[tuple[str, str, str, str], tuple[str, str, str, str]]:
    """(sido, sigungu, eup, ri_name) → codes. 단순 이름 매칭."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT sido_name, sigungu_name, eupmyeondong_name, beopjungri_name,
                       sido_code, sigungu_code, eupmyeondong_code, beopjungri_code
                FROM region_codes
                WHERE COALESCE(is_active, true)
                """
            )
        ).fetchall()
    lookup: dict[tuple[str, str, str, str], tuple[str, str, str, str]] = {}
    for r in rows:
        key = (
            str(r.sido_name or "").strip(),
            str(r.sigungu_name or "").strip(),
            str(r.eupmyeondong_name or "").strip(),
            str(r.beopjungri_name or "").strip(),
        )
        lookup[key] = (
            str(r.sido_code).strip(),
            str(r.sigungu_code).strip(),
            str(r.eupmyeondong_code).strip(),
            str(r.beopjungri_code).strip(),
        )
    return lookup


def _null_if_nan(val):
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    if isinstance(val, str) and val.strip().lower() in ("", "nan", "none"):
        return None
    return val


def _clean_code(val, width: int | None = None) -> str | None:
    val = _null_if_nan(val)
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None
    if width is not None:
        s = s[:width]
    return s or None


def _attach_codes(df: pd.DataFrame, lookup: dict) -> pd.DataFrame:
    sido_c, sg_c, eup_c, bj_c = [], [], [], []
    for _, row in df.iterrows():
        a1 = str(row.get("addr1") or "").strip()
        a2 = str(row.get("addr2") or "").strip()
        a3 = str(row.get("addr3") or "").strip()
        a4 = str(row.get("addr4") or "").strip() if pd.notna(row.get("addr4")) else ""
        a5 = str(row.get("addr5") or "").strip() if pd.notna(row.get("addr5")) else ""
        ri = a5 or a4
        hit = lookup.get((a1, a2, a3, ri))
        if not hit and a4:
            hit = lookup.get((a1, a2, a3, a4))
        if not hit:
            # 읍면동만 맞는 첫 beopjungri
            for (s, g, e, _), codes in lookup.items():
                if s == a1 and g == a2 and e == a3:
                    hit = codes
                    break
        if hit:
            sido_c.append(hit[0])
            sg_c.append(hit[1])
            eup_c.append(hit[2])
            bj_c.append(hit[3])
        else:
            sido_c.append(None)
            sg_c.append(None)
            eup_c.append(None)
            bj_c.append(None)
    df = df.copy()
    df["sido_code"] = sido_c
    df["sigungu_code"] = sg_c
    df["eupmyeondong_code"] = eup_c
    df["beopjungri_code"] = bj_c
    return df


def ensure_schema(engine) -> None:
    sql = DDL.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(sql))


def copy_region_codes_if_empty(built_engine, land_engine) -> None:
    sync_region_codes_from_land(built_engine, land_engine, force=False)


def sync_region_codes_from_land(built_engine, land_engine, *, force: bool = False) -> None:
    with built_engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM region_codes")).scalar()
    if n and int(n) > 0 and not force:
        log.info("region_codes already %s rows (use --refresh-region-codes to overwrite)", n)
        return
    log.info("Syncing region_codes from land_stats (force=%s) …", force)
    with land_engine.connect() as src, built_engine.begin() as dst:
        rows = src.execute(text("SELECT * FROM region_codes")).mappings().all()
        if not rows:
            raise SystemExit("land_stats.region_codes empty — run seed_region_codes first")
        if force:
            dst.execute(text("TRUNCATE region_codes RESTART IDENTITY"))
        for row in rows:
            dst.execute(
                text(
                    """
                    INSERT INTO region_codes (
                        sido_code, sido_name, sigungu_code, sigungu_name,
                        eupmyeondong_code, eupmyeondong_name,
                        beopjungri_code, beopjungri_name, is_active, updated_at
                    ) VALUES (
                        :sido_code, :sido_name, :sigungu_code, :sigungu_name,
                        :eupmyeondong_code, :eupmyeondong_name,
                        :beopjungri_code, :beopjungri_name, :is_active, :updated_at
                    )
                    ON CONFLICT (beopjungri_code) DO UPDATE SET
                        sido_code = EXCLUDED.sido_code,
                        sido_name = EXCLUDED.sido_name,
                        sigungu_code = EXCLUDED.sigungu_code,
                        sigungu_name = EXCLUDED.sigungu_name,
                        eupmyeondong_code = EXCLUDED.eupmyeondong_code,
                        eupmyeondong_name = EXCLUDED.eupmyeondong_name,
                        beopjungri_name = EXCLUDED.beopjungri_name,
                        is_active = EXCLUDED.is_active,
                        updated_at = EXCLUDED.updated_at
                    """
                ),
                dict(row),
            )
    log.info("region_codes synced: %s rows from land_stats", len(rows))


def ingest_file(path: Path, asset_type: str, engine, lookup: dict, truncate_type: bool) -> int:
    log.info("Reading %s (%s)", path, asset_type)
    df = pd.read_excel(path)
    df = _normalize_df(df, asset_type)
    df = _attach_codes(df, lookup)
    if truncate_type:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM built_transactions WHERE asset_type = :t"),
                {"t": asset_type},
            )
    inserted = 0
    batch: list[dict] = []
    stmt = text(
        """
        INSERT INTO built_transactions (
            transaction_hash, asset_type, deal_form,
            addr1, addr2, addr3, addr4, addr5, lot_number,
            beopjungri_code, sido_code, sigungu_code, eupmyeondong_code,
            trade_year_label, contract_year, contract_month, contract_date,
            zone_type, building_use, building_scale, land_scale, age_bucket,
            price, gross_area, land_area, building_age, road_code, floor,
            is_valid
        ) VALUES (
            :transaction_hash, :asset_type, :deal_form,
            :addr1, :addr2, :addr3, :addr4, :addr5, :lot_number,
            :beopjungri_code, :sido_code, :sigungu_code, :eupmyeondong_code,
            :trade_year_label, :contract_year, :contract_month, :contract_date,
            :zone_type, :building_use, :building_scale, :land_scale, :age_bucket,
            :price, :gross_area, :land_area, :building_age, :road_code, :floor,
            :is_valid
        )
        ON CONFLICT (transaction_hash) DO NOTHING
        """
    )
    for _, row in df.iterrows():
        rec = {c: (None if pd.isna(row.get(c)) else row.get(c)) for c in COL_MAP.values()}
        rec.update(
            {
                "asset_type": asset_type,
                "deal_form": "general",
                "contract_year": row.get("contract_year"),
                "contract_month": None,
                "contract_date": None,
                "is_valid": True,
                "beopjungri_code": row.get("beopjungri_code"),
                "sido_code": row.get("sido_code"),
                "sigungu_code": row.get("sigungu_code"),
                "eupmyeondong_code": row.get("eupmyeondong_code"),
            }
        )
        for k in list(rec.keys()):
            if rec[k] is not None and hasattr(rec[k], "item"):
                try:
                    rec[k] = rec[k].item()
                except Exception:
                    pass
        rec["transaction_hash"] = _tx_hash(rec)
        for ck in ("beopjungri_code", "sido_code", "sigungu_code", "eupmyeondong_code"):
            w = {"sido_code": 2, "sigungu_code": 5, "eupmyeondong_code": 8, "beopjungri_code": 10}.get(ck)
            rec[ck] = _clean_code(rec.get(ck), w)
        for k in list(rec.keys()):
            rec[k] = _null_if_nan(rec[k])
        batch.append(rec)
        if len(batch) >= 2000:
            with engine.begin() as conn:
                for b in batch:
                    conn.execute(stmt, b)
            inserted += len(batch)
            batch.clear()
    if batch:
        with engine.begin() as conn:
            for b in batch:
                conn.execute(stmt, b)
        inserted += len(batch)
    log.info("%s inserted/attempted %d rows (dedupe via hash)", asset_type, inserted)
    return inserted


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--commercial", type=Path, default=DEFAULT_COMMERCIAL)
    p.add_argument("--factory", type=Path, default=DEFAULT_FACTORY)
    p.add_argument("--detached", type=Path, default=DEFAULT_DETACHED)
    p.add_argument("--commercial-only", action="store_true")
    p.add_argument("--factory-only", action="store_true")
    p.add_argument("--detached-only", action="store_true")
    p.add_argument(
        "--refresh-region-codes",
        action="store_true",
        help="land_stats.region_codes 를 built_stats 에 덮어씀 (월간 배치 권장)",
    )
    args = p.parse_args()

    only_flags = sum([args.commercial_only, args.factory_only, args.detached_only])
    if only_flags > 1:
        raise SystemExit("--*-only flags are mutually exclusive")

    built = get_built_engine()
    land = get_land_engine_for_region_copy()
    ensure_schema(built)
    if args.refresh_region_codes:
        sync_region_codes_from_land(built, land, force=True)
    else:
        copy_region_codes_if_empty(built, land)
    lookup = _load_region_lookup(built)

    run_all = only_flags == 0
    if run_all or args.commercial_only:
        ingest_file(args.commercial, "commercial", built, lookup, truncate_type=True)
    if run_all or args.factory_only:
        ingest_file(
            args.factory,
            "factory",
            built,
            lookup,
            truncate_type=run_all or args.factory_only,
        )
    if run_all or args.detached_only:
        ingest_file(
            args.detached,
            "detached",
            built,
            lookup,
            truncate_type=run_all or args.detached_only,
        )

    with built.connect() as conn:
        for t in ("commercial", "factory", "detached"):
            n = conn.execute(
                text("SELECT COUNT(*) FROM built_transactions WHERE asset_type=:t"),
                {"t": t},
            ).scalar()
            log.info("built_transactions.%s = %s", t, n)


if __name__ == "__main__":
    main()
