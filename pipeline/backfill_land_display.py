#!/usr/bin/env python3
"""land_transactions 표시 컬럼(lot_display, deal_type, partial) raw JSON 백필 — 전량 clean 재적재 없음."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Iterator

import pandas as pd
from sqlalchemy import text
from tqdm import tqdm

from clean import (
    RAW_FIELD_MAP,
    _derive_lot_display,
    _text_series,
)
from db_utils import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

_DISPLAY_WHERE = """lt.is_valid = true
  AND (
      lt.lot_display IS NULL OR btrim(lt.lot_display::text) = ''
      OR lt.deal_type IS NULL OR btrim(lt.deal_type::text) = ''
  )"""

UPDATE_SQL = """
UPDATE land_transactions AS lt
SET
    lot_display = COALESCE(v.lot_display, lt.lot_display),
    deal_type = COALESCE(v.deal_type, lt.deal_type),
    partial_ownership_label = COALESCE(v.partial_ownership_label, lt.partial_ownership_label),
    is_partial_ownership = v.is_partial_ownership
FROM (VALUES %s) AS v(
    raw_id, lot_display, deal_type, partial_ownership_label, is_partial_ownership
)
WHERE lt.raw_id = v.raw_id
"""


def _records_to_display_updates(records: list[dict]) -> list[tuple]:
    if not records:
        return []
    df = pd.DataFrame(records)
    raw_ids = df["_raw_id"].astype(int).tolist()

    renamed = df.drop(columns=["_raw_id"], errors="ignore").rename(
        columns={k: v for k, v in RAW_FIELD_MAP.items() if k in df.columns}
    )
    if "trade_type" in renamed.columns and "deal_type" not in renamed.columns:
        renamed["deal_type"] = renamed["trade_type"]

    lot = _derive_lot_display(renamed).astype(str).str.strip()
    lot = lot.mask(lot.eq(""), other=pd.NA)

    partial_txt = _text_series(renamed, "partial_ownership_raw")
    partial_label = partial_txt.str.slice(0, 128).mask(partial_txt.eq(""), other=pd.NA)

    deal_txt = renamed.get("deal_type", pd.Series("", index=renamed.index)).fillna("").astype(str)
    is_partial = partial_txt.str.contains("지분", na=False) | deal_txt.str.contains("지분", na=False)

    deal_type = deal_txt.str.strip().str.slice(0, 128).mask(deal_txt.str.strip().eq(""), other=pd.NA)

    out: list[tuple] = []
    for i, raw_id in enumerate(raw_ids):
        ld = lot.iloc[i]
        dt = deal_type.iloc[i]
        pl = partial_label.iloc[i]
        out.append(
            (
                raw_id,
                None if pd.isna(ld) else str(ld),
                None if pd.isna(dt) else str(dt),
                None if pd.isna(pl) else str(pl),
                bool(is_partial.iloc[i]),
            )
        )
    return out


def count_targets(engine, *, year: int | None) -> int:
    year_clause = "AND lt.contract_year = :year" if year is not None else ""
    q = f"""
        SELECT COUNT(*)
        FROM land_transactions lt
        JOIN land_transactions_raw r ON r.id = lt.raw_id
        WHERE {_DISPLAY_WHERE}
        {year_clause}
    """
    params = {"year": year} if year is not None else {}
    with engine.connect() as conn:
        return int(conn.execute(text(q), params).scalar() or 0)


def iter_batches(
    engine,
    *,
    year: int | None,
    batch_size: int,
    last_id: int = 0,
) -> Iterator[list[dict]]:
    year_clause = "AND lt.contract_year = :year" if year is not None else ""
    params: dict = {"batch_size": batch_size, "last_id": last_id}
    if year is not None:
        params["year"] = year

    q = f"""
        SELECT r.id AS raw_id, r.raw_data
        FROM land_transactions_raw r
        JOIN land_transactions lt ON lt.raw_id = r.id
        WHERE r.id > :last_id
          AND {_DISPLAY_WHERE}
          {year_clause}
        ORDER BY r.id
        LIMIT :batch_size
    """
    with engine.connect() as conn:
        while True:
            rows = conn.execute(text(q), params).fetchall()
            if not rows:
                break
            batch: list[dict] = []
            for row in rows:
                rec = {"_raw_id": int(row[0])}
                rec.update(row[1] or {})
                batch.append(rec)
            yield batch
            params["last_id"] = int(rows[-1][0])


def apply_batch(engine, tuples: list[tuple], *, dry_run: bool) -> int:
    if not tuples:
        return 0
    if dry_run:
        return len(tuples)

    import psycopg2
    from psycopg2.extras import execute_values

    url = engine.url
    conn = psycopg2.connect(
        host=url.host,
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        dbname=url.database,
    )
    try:
        with conn, conn.cursor() as cur:
            execute_values(cur, UPDATE_SQL, tuples, page_size=len(tuples))
        return len(tuples)
    finally:
        conn.close()


def run_backfill(
    *,
    year: int | None,
    batch_size: int,
    dry_run: bool,
    max_batches: int | None,
) -> int:
    engine = get_engine()
    total_targets = count_targets(engine, year=year)
    log.info(
        "백필 대상: %d건 (year=%s, batch=%d, dry_run=%s)",
        total_targets,
        year if year is not None else "all",
        batch_size,
        dry_run,
    )
    if total_targets == 0:
        return 0

    updated = 0
    batch_no = 0
    pbar = tqdm(total=total_targets, desc=f"backfill y={year or 'all'}")
    for batch in iter_batches(engine, year=year, batch_size=batch_size):
        batch_no += 1
        tuples = _records_to_display_updates(batch)
        n = apply_batch(engine, tuples, dry_run=dry_run)
        updated += n
        pbar.update(len(batch))
        if max_batches is not None and batch_no >= max_batches:
            log.warning("max_batches=%d 도달 — 중단", max_batches)
            break
    pbar.close()
    log.info("백필 완료: %d건 처리", updated)
    return updated


def main() -> None:
    p = argparse.ArgumentParser(description="land_transactions 표시 컬럼 백필 (raw JSON → UPDATE)")
    p.add_argument("--year", type=int, action="append", help="처리 연도 (복수 가능, 미지정=전체)")
    p.add_argument("--batch-size", type=int, default=5000)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-batches", type=int, default=None, help="테스트용 배치 상한")
    args = p.parse_args()

    years = args.year if args.year else [None]
    grand = 0
    for y in years:
        grand += run_backfill(
            year=y,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            max_batches=args.max_batches,
        )
    log.info("총 처리: %d건", grand)


if __name__ == "__main__":
    main()
