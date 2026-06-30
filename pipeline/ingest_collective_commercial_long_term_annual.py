#!/usr/bin/env python3
"""
장기(2010~2020) 집합상가·집합공장 CSV → collective_commercial_cluster_annual_stats 보강.

원본: raw/raw long term/상업업무_2010_2020/, 공장창고_2010_2020/
유형=집합 행만 추출 (molit_raw.refine_collective_molit_dataframe).
2021~ 구간은 collective_commercial_transactions annual build — 여기서는 contract_year < 2021 만 upsert.
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
sys.path.insert(0, str(REPO / "pipeline" / "collective_commercial"))

from collective.db_utils import get_collective_engine  # noqa: E402
from collective_commercial.cluster_keys import (  # noqa: E402
    area_bucket_label,
    confidence_tier,
    derive_building_year,
    make_road_cluster_key,
    make_road_display_label,
)
from collective_commercial.molit_raw import CollectiveMolitAsset, refine_collective_molit_file  # noqa: E402
from stats import compute_stats  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RAW_LONG = REPO / "raw" / "raw long term"

ASSET_DIRS: dict[CollectiveMolitAsset, str] = {
    "collective_shop": "상업업무_2010_2020",
    "collective_factory": "공장창고_2010_2020",
}


def _find_csvs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.csv"))


def _int_small(val) -> int | None:
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    try:
        n = int(round(float(val)))
        if -32768 <= n <= 32767:
            return n
    except (TypeError, ValueError):
        pass
    return None


def _enrich_cluster_keys(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    derived_by = [
        derive_building_year(cy, age)
        for cy, age in zip(out["contract_year"], out.get("building_age", pd.Series([None] * len(out))))
    ]
    out["building_year"] = [
        _int_small(b) if _int_small(b) is not None else _int_small(d)
        for b, d in zip(out["building_year"], derived_by)
    ]
    out["area_bucket_label"] = [
        area_bucket_label(at, ga) for at, ga in zip(out["asset_type"], out["gross_area"])
    ]
    keys, labels = [], []
    for row in out.itertuples(index=False):
        ck = make_road_cluster_key(
            asset_type=row.asset_type,
            addr1=getattr(row, "addr1", None),
            addr2=getattr(row, "addr2", None),
            addr3=getattr(row, "addr3", None),
            addr4=getattr(row, "addr4", None),
            road_name=getattr(row, "road_name", None),
        )
        keys.append(ck)
        labels.append(
            make_road_display_label(
                road_name=getattr(row, "road_name", None),
                addr3=getattr(row, "addr3", None),
                addr4=getattr(row, "addr4", None),
            )
        )
    out["cluster_key"] = keys
    out["display_label"] = labels
    out["resolution_mode"] = "road"
    return out


def _group_annual(df: pd.DataFrame, batch_id: str) -> list[dict]:
    if df.empty or "cluster_key" not in df.columns:
        return []
    records: list[dict] = []
    for (ck, cy), grp in df.groupby(["cluster_key", "contract_year"], dropna=True):
        prices = grp["unit_price"].dropna().astype(float).tolist()
        if not prices:
            continue
        st = compute_stats(prices)
        row0 = grp.iloc[0]
        records.append(
            {
                "cluster_key": ck,
                "asset_type": row0["asset_type"],
                "contract_year": int(cy),
                "display_label": str(row0.get("display_label") or ""),
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
        INSERT INTO collective_commercial_cluster_annual_stats (
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
    asset_type: CollectiveMolitAsset,
    root: Path,
    *,
    year_to: int,
    batch_id: str,
    limit_files: int | None = None,
) -> int:
    files = _find_csvs(root)
    if not files:
        log.warning("no CSV under %s — skip %s", root, asset_type)
        return 0
    if limit_files is not None:
        files = files[:limit_files]
    total = 0
    for fp in files:
        log.info("[%s] read %s", asset_type, fp.name)
        df = refine_collective_molit_file(fp, asset_type=asset_type)
        if df.empty:
            log.info("  no collective rows — skip")
            continue
        df = _enrich_cluster_keys(df)
        df = df[df["contract_year"].notna() & (df["contract_year"] <= year_to)]
        records = _group_annual(df, batch_id)
        upsert(records, engine)
        total += len(records)
        log.info("  upserted %s annual rows (from %s tx rows)", len(records), len(df))
    return total


def main() -> None:
    p = argparse.ArgumentParser(description="집합상가·공장 2010~2020 annual mart backfill")
    p.add_argument("--input-root", type=Path, default=RAW_LONG)
    p.add_argument("--year-to", type=int, default=2020)
    p.add_argument("--asset-type", type=str, default=None, choices=list(ASSET_DIRS.keys()))
    p.add_argument("--limit-files", type=int, default=None, help="smoke: process first N CSV per asset")
    args = p.parse_args()

    engine = get_collective_engine()
    batch_id = str(uuid.uuid4())
    types: list[CollectiveMolitAsset] = (
        [args.asset_type] if args.asset_type else list(ASSET_DIRS.keys())  # type: ignore[list-item]
    )
    grand = 0
    for at in types:
        subdir = args.input_root / ASSET_DIRS[at]
        grand += ingest_asset(
            engine,
            at,
            subdir,
            year_to=args.year_to,
            batch_id=batch_id,
            limit_files=args.limit_files,
        )
    log.info("commercial long-term ingest done total=%s", grand)


if __name__ == "__main__":
    main()
