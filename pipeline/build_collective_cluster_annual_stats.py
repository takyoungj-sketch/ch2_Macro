#!/usr/bin/env python3
"""collective_commercial_transactions → collective_cluster_annual_stats (2021~)."""

from __future__ import annotations

import argparse
import gc
import logging
import sys
import uuid
from pathlib import Path

from sqlalchemy import text
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from collective.db_utils import get_collective_engine  # noqa: E402
from stats import compute_stats  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DDL = REPO / "db" / "031_collective_cluster_annual_stats.sql"

ANNUAL_SQL = """
SELECT
    t.cluster_key,
    t.asset_type,
    MAX(c.display_label) AS display_label,
    MAX(t.addr1) AS addr1,
    MAX(t.addr2) AS addr2,
    MAX(t.addr3) AS addr3,
    MAX(t.addr4) AS addr4,
    MAX(c.road_name) AS road_name,
    t.contract_year,
    array_agg(t.unit_price ORDER BY t.unit_price) AS prices
FROM collective_commercial_transactions t
JOIN commercial_clusters c ON c.id = t.cluster_id
WHERE t.is_valid = true
  AND t.unit_price IS NOT NULL
  AND t.unit_price > 0
  AND t.contract_year IS NOT NULL
  AND t.contract_year >= 2021
  {addr1_clause}
GROUP BY t.cluster_key, t.asset_type, t.contract_year
"""


def apply_ddl(engine) -> None:
    if not DDL.is_file():
        raise FileNotFoundError(DDL)
    sql = DDL.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(sql))
    log.info("DDL applied: %s", DDL.name)


def _distinct_addr1(conn) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT addr1
            FROM collective_commercial_transactions
            WHERE addr1 IS NOT NULL
            ORDER BY addr1
            """
        )
    ).scalars().all()
    return list(rows)


def upsert_annual(records: list[dict], engine) -> None:
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
        WHERE EXCLUDED.contract_year >= 2021
        """
    )
    with engine.begin() as conn:
        for rec in records:
            if int(rec["contract_year"]) < 2021:
                continue
            conn.execute(sql, rec)


def build_annual(engine, *, addr1_filter: str | None, batch_id: str) -> int:
    total = 0
    with engine.connect() as conn:
        addr1_list = [addr1_filter] if addr1_filter else _distinct_addr1(conn)

    for addr1 in tqdm(addr1_list, desc="cluster annual"):
        addr1_clause = "AND t.addr1 = :addr1" if addr1 else ""
        sql = ANNUAL_SQL.format(addr1_clause=addr1_clause)
        params = {}
        if addr1:
            params["addr1"] = addr1
        with engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        records: list[dict] = []
        for row in rows:
            prices = [float(x) for x in (row["prices"] or []) if x is not None]
            if not prices:
                continue
            st = compute_stats(prices)
            records.append(
                {
                    "cluster_key": row["cluster_key"],
                    "asset_type": row["asset_type"],
                    "contract_year": int(row["contract_year"]),
                    "display_label": row["display_label"] or "",
                    "addr1": row.get("addr1"),
                    "addr2": row.get("addr2"),
                    "addr3": row.get("addr3"),
                    "addr4": row.get("addr4"),
                    "road_name": row.get("road_name"),
                    "count": st["count"],
                    "mean": st["mean"],
                    "std": st["std"],
                    "ci_lower": st["ci_lower"],
                    "ci_upper": st["ci_upper"],
                    "median": st["median"],
                    "batch_id": batch_id,
                }
            )
        upsert_annual(records, engine)
        total += len(records)
        del rows, records
        gc.collect()
    return total


def main() -> None:
    p = argparse.ArgumentParser(description="비주거 집합 cluster annual stats (2021~)")
    p.add_argument("--addr1", type=str, default=None, help="시도(addr1) 한정 스모크")
    p.add_argument("--skip-ddl", action="store_true")
    args = p.parse_args()

    engine = get_collective_engine()
    if not args.skip_ddl:
        apply_ddl(engine)

    with engine.connect() as conn:
        tx_n = conn.execute(text("SELECT COUNT(*) FROM collective_commercial_transactions")).scalar()
    log.info("collective_commercial_transactions rows=%s", tx_n)
    if not tx_n:
        raise SystemExit("collective_commercial_transactions empty — import_refined 먼저 실행")

    batch_id = str(uuid.uuid4())
    annual_n = build_annual(engine, addr1_filter=args.addr1, batch_id=batch_id)
    log.info("collective_cluster_annual_stats upserted ~%s rows (batch %s)", annual_n, batch_id)

    with engine.connect() as conn:
        ccas = conn.execute(text("SELECT COUNT(*) FROM collective_cluster_annual_stats")).scalar()
    log.info("totals: collective_cluster_annual_stats=%s", ccas)


if __name__ == "__main__":
    main()
