#!/usr/bin/env python3
"""
장기(2010~2020) 집합 상업·공장 CSV → collective_cluster_annual_stats 보강.

원본: raw/raw long term/{상업업무|공장창고}_2010_2020/
유형 == 집합 행만 사용. 2021~ 구간은 build_collective_cluster_annual_stats — 여기서는 contract_year < 2021 만 upsert.
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
COMM_PIPE = REPO / "pipeline" / "collective_commercial"
sys.path.insert(0, str(REPO / "pipeline" / "collective"))
sys.path.insert(0, str(COMM_PIPE))

from db_utils import get_collective_engine  # noqa: E402
from import_refined import enrich_commercial_road  # noqa: E402
from molit_raw_common import _finalize, parse_collective_rows, read_molit_csv  # noqa: E402
from stats import compute_stats  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RAW_LONG = REPO / "raw" / "raw long term"
DDL = REPO / "db" / "031_collective_cluster_annual_stats.sql"

ASSET_DIRS: dict[str, str] = {
    "collective_shop": "상업업무_2010_2020",
    "collective_factory": "공장창고_2010_2020",
}


def _find_csvs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.csv"))


def apply_ddl(engine) -> None:
    if not DDL.is_file():
        raise FileNotFoundError(DDL)
    sql = DDL.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(sql))
    log.info("DDL applied: %s", DDL.name)


def _group_annual(df: pd.DataFrame, batch_id: str) -> list[dict]:
    if df.empty or "cluster_key" not in df.columns:
        return []
    records: list[dict] = []
    for (ck, at, cy), grp in df.groupby(["cluster_key", "asset_type", "contract_year"], dropna=True):
        prices = grp["unit_price"].dropna().astype(float).tolist()
        if not prices:
            continue
        st = compute_stats(prices)
        row0 = grp.iloc[0]
        records.append(
            {
                "cluster_key": ck,
                "asset_type": at,
                "contract_year": int(cy),
                "display_label": str(row0.get("display_label") or row0.get("road_name") or ""),
                "addr1": row0.get("addr1"),
                "addr2": row0.get("addr2"),
                "addr3": row0.get("addr3"),
                "addr4": row0.get("addr4"),
                "road_name": row0.get("road_name"),
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
        INSERT INTO collective_cluster_annual_stats (
            cluster_key, asset_type, contract_year, display_label,
            addr1, addr2, addr3, addr4, road_name,
            count, mean, std, ci_lower, ci_upper, median, batch_id
        ) VALUES (
            :cluster_key, :asset_type, :contract_year, :display_label,
            :addr1, :addr2, :addr3, :addr4, :road_name,
            :count, :mean, :std, :ci_lower, :ci_upper, :median, :batch_id
        )
        ON CONFLICT (cluster_key, asset_type, contract_year)
        DO UPDATE SET
            display_label = EXCLUDED.display_label,
            addr1 = EXCLUDED.addr1,
            addr2 = EXCLUDED.addr2,
            addr3 = EXCLUDED.addr3,
            addr4 = EXCLUDED.addr4,
            road_name = EXCLUDED.road_name,
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


def ingest_asset(
    engine,
    asset_type: str,
    root: Path,
    *,
    year_from: int,
    year_to: int,
    batch_id: str,
) -> int:
    files = _find_csvs(root)
    if not files:
        log.warning("no CSV under %s — skip %s", root, asset_type)
        return 0
    total = 0
    for fp in files:
        log.info("[%s] read %s", asset_type, fp.name)
        raw = read_molit_csv(fp)
        df = parse_collective_rows(raw, asset_type=asset_type, source_file=fp.name)
        if df.empty:
            continue
        df = _finalize(df, year_from=year_from, year_to=year_to)
        if df.empty:
            continue
        df = enrich_commercial_road(df)
        records = _group_annual(df, batch_id)
        upsert(records, engine)
        total += len(records)
        log.info("  upserted %s annual rows", len(records))
    return total


def main() -> None:
    p = argparse.ArgumentParser(description="비주거 집합 장기(2010~2020) annual mart ingest")
    p.add_argument("--input-root", type=Path, default=RAW_LONG)
    p.add_argument("--year-from", type=int, default=2010)
    p.add_argument("--year-to", type=int, default=2020)
    p.add_argument("--asset-type", type=str, default=None, choices=list(ASSET_DIRS.keys()))
    p.add_argument("--skip-ddl", action="store_true")
    args = p.parse_args()

    engine = get_collective_engine()
    if not args.skip_ddl:
        apply_ddl(engine)

    batch_id = str(uuid.uuid4())
    types = [args.asset_type] if args.asset_type else list(ASSET_DIRS.keys())
    grand = 0
    for at in types:
        subdir = args.input_root / ASSET_DIRS[at]
        grand += ingest_asset(
            engine,
            at,
            subdir,
            year_from=args.year_from,
            year_to=args.year_to,
            batch_id=batch_id,
        )
    log.info("commercial long-term ingest done total=%s", grand)


if __name__ == "__main__":
    main()
