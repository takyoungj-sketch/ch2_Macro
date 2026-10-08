#!/usr/bin/env python3
"""
장기(2010~2020) 집합 CSV → collective_building_annual_stats 보강 (4유형).

원본: raw/raw long term/{유형}_2010_2020/
2021~ 구간은 base 원장 annual build — 여기서는 contract_year < 2021 만 upsert.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from collective.building_keys import attach_building_identity  # noqa: E402
from collective.db_utils import get_collective_engine  # noqa: E402
from collective.molit_schemas import AssetType, SCHEMAS  # noqa: E402
from collective.refine import read_molit_raw_csv, refine_dataframe  # noqa: E402
from stats import compute_stats  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RAW_LONG = REPO / "raw" / "raw long term"

ASSET_DIRS: dict[AssetType, str] = {
    "apartment": "아파트_2010_2020",
    "rowhouse": "연립다세대_2010_2020",
    "officetel": "오피스텔_2010_2020",
    "presale": "분양입주권_2010_2020",
}


def _find_csvs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.csv"))


def _prepare_df(raw: pd.DataFrame, asset_type: AssetType, path: Path) -> pd.DataFrame:
    keyed = raw.copy()
    if keyed.shape[1] > 0:
        row_id = keyed.iloc[:, 0].astype(str).str.strip()
    else:
        row_id = pd.Series(range(len(keyed)), index=keyed.index, dtype="int64").astype(str)
    keyed["_source_key"] = path.name + "|" + row_id
    df = refine_dataframe(keyed, asset_type, input_kind="raw")
    return attach_building_identity(df, asset_type)


def _group_annual(df: pd.DataFrame, asset_type: str, batch_id: str) -> list[dict]:
    if df.empty or "building_key" not in df.columns:
        return []
    records: list[dict] = []
    for (bk, cy), grp in df.groupby(["building_key", "contract_year"], dropna=True):
        prices = grp["unit_price"].dropna().astype(float).tolist()
        if not prices:
            continue
        st = compute_stats(prices)
        row0 = grp.iloc[0]
        records.append(
            {
                "building_key": bk,
                "asset_type": asset_type,
                "contract_year": int(cy),
                "display_name": str(row0.get("display_name") or row0.get("building_name") or ""),
                "addr1": row0.get("addr1"),
                "addr2": row0.get("addr2"),
                "addr3": row0.get("addr3"),
                "addr4": row0.get("addr4"),
                "beopjungri_code": row0.get("beopjungri_code"),
                "count": st["count"],
                "mean": st["mean"],
                "std": st["std"],
                "ci_lower": st["ci_lower"],
                "ci_upper": st["ci_upper"],
                "p25": st["p25"],
                "median": st["median"],
                "p75": st["p75"],
                "batch_id": batch_id,
            }
        )
    return records


def upsert(records: list[dict], engine) -> None:
    if not records:
        return
    sql = text(
        """
        INSERT INTO collective_building_annual_stats (
            building_key, asset_type, contract_year, display_name,
            addr1, addr2, addr3, addr4, beopjungri_code,
            count, mean, std, ci_lower, ci_upper, p25, median, p75, batch_id
        ) VALUES (
            :building_key, :asset_type, :contract_year, :display_name,
            :addr1, :addr2, :addr3, :addr4, :beopjungri_code,
            :count, :mean, :std, :ci_lower, :ci_upper, :p25, :median, :p75, :batch_id
        )
        ON CONFLICT (building_key, asset_type, contract_year)
        DO UPDATE SET
            count = EXCLUDED.count,
            mean = EXCLUDED.mean,
            std = EXCLUDED.std,
            ci_lower = EXCLUDED.ci_lower,
            ci_upper = EXCLUDED.ci_upper,
            p25 = EXCLUDED.p25,
            median = EXCLUDED.median,
            p75 = EXCLUDED.p75,
            computed_at = NOW(),
            batch_id = EXCLUDED.batch_id
        WHERE EXCLUDED.contract_year < 2021
        """
    )
    with engine.begin() as conn:
        for rec in records:
            if int(rec["contract_year"]) >= 2021:
                continue
            conn.execute(sql, rec)


_YEAR_IN_NAME = re.compile(r"_(19\d{2}|20\d{2})(?:_|\.csv$)")


def _named_year(path: Path) -> int | None:
    m = _YEAR_IN_NAME.search(path.name)
    return int(m.group(1)) if m else None


def update_quartiles_only(records: list[dict], engine) -> int:
    """기존 연도 행의 25%·75%만 갱신. 건수·평균·중앙값은 그대로 둔다."""
    rows = [
        (r["building_key"], r["asset_type"], int(r["contract_year"]), r["p25"], r["p75"])
        for r in records
        if r.get("p25") is not None and r.get("p75") is not None
    ]
    if not rows:
        return 0
    from psycopg2.extras import execute_values

    sql = """
        UPDATE collective_building_annual_stats AS a
        SET p25 = q.p25, p75 = q.p75
        FROM (VALUES %s) AS q(building_key, asset_type, contract_year, p25, p75)
        WHERE a.building_key = q.building_key
          AND a.asset_type = q.asset_type
          AND a.contract_year = q.contract_year
    """
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cur:
            execute_values(
                cur,
                sql,
                rows,
                template="(%s, %s, %s::smallint, %s::numeric, %s::numeric)",
                page_size=1000,
            )
            updated = cur.rowcount
        raw.commit()
    finally:
        raw.close()
    return int(updated or 0)


def ingest_asset(
    engine,
    asset_type: AssetType,
    root: Path,
    *,
    year_to: int,
    batch_id: str,
    quartiles_only: bool = False,
) -> int:
    files = _find_csvs(root)
    if not files:
        log.warning("no CSV under %s — skip %s", root, asset_type)
        return 0
    if asset_type not in SCHEMAS:
        log.warning("unknown schema for %s", asset_type)
        return 0
    total = 0
    for fp in files:
        named = _named_year(fp)
        if named is not None and named > year_to:
            continue
        log.info("[%s] read %s", asset_type, fp.name)
        raw = read_molit_raw_csv(fp)
        df = _prepare_df(raw, asset_type, fp)
        df = df[df["contract_year"].notna() & (df["contract_year"] <= year_to)]
        records = _group_annual(df, asset_type, batch_id)
        if quartiles_only:
            updated = update_quartiles_only(records, engine)
            log.info("  quartiles updated %s / grouped %s", updated, len(records))
            total += updated
        else:
            upsert(records, engine)
            total += len(records)
            log.info("  upserted %s annual rows", len(records))
    return total


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input-root", type=Path, default=RAW_LONG)
    p.add_argument("--year-to", type=int, default=2020)
    p.add_argument("--asset-type", type=str, default=None, choices=list(ASSET_DIRS.keys()))
    p.add_argument(
        "--quartiles-only",
        action="store_true",
        help="기존 행의 p25·p75만 갱신 (건수·평균·중앙값 유지)",
    )
    args = p.parse_args()

    engine = get_collective_engine()
    batch_id = str(uuid.uuid4())
    types: list[AssetType] = [args.asset_type] if args.asset_type else list(ASSET_DIRS.keys())  # type: ignore
    grand = 0
    for at in types:
        subdir = args.input_root / ASSET_DIRS[at]
        grand += ingest_asset(
            engine,
            at,
            subdir,
            year_to=args.year_to,
            batch_id=batch_id,
            quartiles_only=args.quartiles_only,
        )
    log.info("long-term ingest done total=%s", grand)


if __name__ == "__main__":
    main()
