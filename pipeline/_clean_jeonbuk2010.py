# -*- coding: utf-8 -*-
"""Clean only unprocessed Jeonbuk 2010/2011 historical raw (source_year batch)."""
from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import text

from clean import (
    build_region_lookup,
    clean_dataframe,
    map_beopjungri_codes,
    upsert_transactions,
    _make_hash,
)
from db_utils import get_engine

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def fetch_jeonbuk_2010_2011_raw() -> pd.DataFrame:
    engine = get_engine()
    query = """
        SELECT r.id AS raw_id, r.source_year, r.source_month, r.raw_data
        FROM land_transactions_raw r
        WHERE r.source_year IN (2010, 2011)
          AND r.source_month = 6
          AND r.raw_data->>'sigungu_name' LIKE '전북%'
          AND NOT EXISTS (SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id)
        ORDER BY r.id
    """
    with engine.connect() as conn:
        rows = conn.execute(text(query)).fetchall()
    if not rows:
        return pd.DataFrame()
    records = []
    for row in rows:
        record = {"_raw_id": row[0], "_source_year": row[1], "_source_month": row[2]}
        record.update(row[3])
        records.append(record)
    return pd.DataFrame(records)


def main() -> None:
    df = fetch_jeonbuk_2010_2011_raw()
    if df.empty:
        log.info("처리할 전북 2010/2011 raw 없음")
        return
    log.info("정제 시작: %d건", len(df))
    cleaned = clean_dataframe(df)
    engine = get_engine()
    lookup = build_region_lookup(engine)
    meta = map_beopjungri_codes(cleaned, lookup)
    cleaned["beopjungri_code"] = meta["beopjungri_code"].values
    cleaned["needs_review"] = meta["needs_review"].values
    cleaned["mapping_notes"] = meta["mapping_notes"].values
    cleaned["transaction_hash"] = cleaned.apply(_make_hash, axis=1)
    cleaned["sido_code"] = cleaned["beopjungri_code"].astype(str).str[:2]
    cleaned["sigungu_code"] = cleaned["beopjungri_code"].astype(str).str[:5]
    ok = cleaned["beopjungri_code"].astype(str).str.startswith("52").sum()
    log.info("mapped to sido 52: %d / %d", ok, len(cleaned))
    bc_empty = cleaned["beopjungri_code"].fillna("").astype(str).str.strip().eq("")
    cleaned.loc[bc_empty, "needs_review"] = True
    cleaned.loc[bc_empty, "is_valid"] = False
    idx_no_note = bc_empty & cleaned["mapping_notes"].fillna("").astype(str).str.strip().eq("")
    cleaned.loc[idx_no_note, "mapping_notes"] = "no_beopjungri_code"
    valid = cleaned[cleaned["is_valid"] == True]
    log.info("유효 데이터: %d건 / 전체 %d건", len(valid), len(cleaned))
    upsert_transactions(cleaned)


if __name__ == "__main__":
    main()
