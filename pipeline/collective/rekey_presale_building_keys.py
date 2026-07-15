# -*- coding: utf-8 -*-
"""분양권 building_key 재생성 — 이름 정규화만 적용, 원본 building_name/display_name 유지."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from collective.building_keys import attach_building_identity  # noqa: E402
from collective.db_utils import get_collective_engine  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _rekey_fast(conn, *, dry_run: bool) -> tuple[int, int]:
    log.info("loading 분양권 rows…")
    df = pd.read_sql(
        text(
            """
            SELECT id, building_key AS old_key,
                   building_name, display_name,
                   addr1, addr2, addr3, addr4, lot_number, road_name
            FROM collective_transactions
            WHERE asset_type = 'presale'
            """
        ),
        conn,
    )
    log.info("loaded %s", len(df))
    out = attach_building_identity(df, "presale")
    mask = out["building_key"] != out["old_key"]
    changed_df = out.loc[mask, ["id", "building_key", "old_key", "building_name"]].copy()
    log.info("keys to update=%s / %s", len(changed_df), len(df))

    for r in changed_df.head(8).itertuples(index=False):
        log.info(
            "eg id=%s name=%r %s… → %s…",
            r.id,
            r.building_name,
            str(r.old_key)[:12],
            str(r.building_key)[:12],
        )

    if dry_run or changed_df.empty:
        return len(df), len(changed_df)

    tmp = "_presale_rekey_map"
    conn.execute(text(f"DROP TABLE IF EXISTS {tmp}"))
    conn.execute(
        text(
            f"""
            CREATE TEMP TABLE {tmp} (
              id bigint PRIMARY KEY,
              building_key text NOT NULL
            )
            """
        )
    )
    # batch insert
    payload = [
        {"id": int(i), "building_key": k}
        for i, k in changed_df[["id", "building_key"]].itertuples(index=False, name=None)
    ]
    for i in range(0, len(payload), 2000):
        chunk = payload[i : i + 2000]
        conn.execute(
            text(f"INSERT INTO {tmp} (id, building_key) VALUES (:id, :building_key)"),
            chunk,
        )
    result = conn.execute(
        text(
            f"""
            UPDATE collective_transactions t
            SET building_key = m.building_key
            FROM {tmp} m
            WHERE t.id = m.id AND t.asset_type = 'presale'
            """
        )
    )
    log.info("updated rows=%s", result.rowcount)
    return len(df), len(changed_df)


def _purge_presale_marts(conn) -> None:
    for table in (
        "collective_building_stats",
        "collective_building_annual_stats",
        "collective_building_rolling_stats",
    ):
        r = conn.execute(text(f"DELETE FROM {table} WHERE asset_type = 'presale'"))
        log.info("purged %s 분양권 rowcount=%s", table, r.rowcount)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--purge-presale-marts",
        action="store_true",
        help="재키 후 분양권 mart 삭제(목록·연도는 live로 조회)",
    )
    args = p.parse_args()

    eng = get_collective_engine()
    with eng.begin() as conn:
        total, changed = _rekey_fast(conn, dry_run=args.dry_run)
        log.info("presale_total=%s keys_changed=%s", total, changed)
        if not args.dry_run and args.purge_presale_marts:
            _purge_presale_marts(conn)


if __name__ == "__main__":
    main()
