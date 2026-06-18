#!/usr/bin/env python3
"""
장기(2010~2020) 집합 CSV → collective_building_annual_stats 보강 (4유형).

원본: raw/raw long term/{유형}_2010_2020/
2021~ 구간은 base 원장 annual build — 여기서는 contract_year < 2021 만 upsert.
"""

from __future__ import annotations

import argparse
import logging
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
                "median": st["median"],
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
            count, mean, std, ci_lower, ci_upper, median, batch_id
        ) VALUES (
            :building_key, :asset_type, :contract_year, :display_name,
            :addr1, :addr2, :addr3, :addr4, :beopjungri_code,
            :count, :mean, :std, :ci_lower, :ci_upper, :median, :batch_id
        )
        ON CONFLICT (building_key, asset_type, contract_year)
        DO UPDATE SET
            count = EXCLUDED.count,
            mean = EXCLUDED.mean,
            std = EXCLUDED.std,
            ci_lower = EXCLUDED.ci_lower,
            ci_upper = EXCLUDED.ci_upper,
            median = EXCLUDED.median,
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


def ingest_asset(engine, asset_type: AssetType, root: Path, *, year_to: int, batch_id: str) -> int:
    files = _find_csvs(root)
    if not files:
        log.warning("no CSV under %s — skip %s", root, asset_type)
        return 0
    if asset_type not in SCHEMAS:
        log.warning("unknown schema for %s", asset_type)
        return 0
    total = 0
    for fp in files:
        log.info("[%s] read %s", asset_type, fp.name)
        raw = read_molit_raw_csv(fp)
        df = _prepare_df(raw, asset_type, fp)
        df = df[df["contract_year"].notna() & (df["contract_year"] <= year_to)]
        records = _group_annual(df, asset_type, batch_id)
        upsert(records, engine)
        total += len(records)
        log.info("  upserted %s annual rows", len(records))
    return total


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input-root", type=Path, default=RAW_LONG)
    p.add_argument("--year-to", type=int, default=2020)
    p.add_argument("--asset-type", type=str, default=None, choices=list(ASSET_DIRS.keys()))
    args = p.parse_args()

    engine = get_collective_engine()
    batch_id = str(uuid.uuid4())
    types: list[AssetType] = [args.asset_type] if args.asset_type else list(ASSET_DIRS.keys())  # type: ignore
    grand = 0
    for at in types:
        subdir = args.input_root / ASSET_DIRS[at]
        grand += ingest_asset(engine, at, subdir, year_to=args.year_to, batch_id=batch_id)
    log.info("long-term ingest done total=%s", grand)


if __name__ == "__main__":
    main()
