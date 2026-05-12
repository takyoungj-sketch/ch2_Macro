"""Paid/free analysis base-row cache helpers.

The paid UI is two-step:
1) choose region(s) and show the basic statistics,
2) re-analyze the same base rows with additional paid filters.

This module stores the transaction ids selected in step 1 so step 2 does not
need to re-expand/scan the whole region range again.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session


BASE_CACHE_TTL_HOURS = 4


def ensure_analysis_base_cache_table(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS analysis_base_cache (
                cache_key TEXT PRIMARY KEY,
                region_codes TEXT[] NOT NULL,
                row_ids BIGINT[] NOT NULL,
                year_from SMALLINT NOT NULL,
                year_to SMALLINT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                expires_at TIMESTAMP NOT NULL
            )
            """
        )
    )


def create_analysis_base_cache(
    db: Session,
    *,
    region_codes: list[str],
    year_from: int,
    year_to: int,
) -> str | None:
    """Create a cache entry for valid transaction ids in a selected region/year window."""

    codes = sorted({str(c).strip() for c in region_codes if str(c).strip()})
    if not codes:
        return None

    ensure_analysis_base_cache_table(db)
    row_ids = db.execute(
        text(
            """
            SELECT COALESCE(array_agg(id ORDER BY id), ARRAY[]::bigint[]) AS ids
            FROM land_transactions
            WHERE is_valid IS TRUE
              AND is_cancelled = FALSE
              AND unit_price_per_sqm IS NOT NULL
              AND contract_year >= :yf
              AND contract_year <= :yt
              AND btrim(cast(beopjungri_code AS text)) = ANY(:codes)
            """
        ),
        {"codes": codes, "yf": int(year_from), "yt": int(year_to)},
    ).scalar()

    if not row_ids:
        return None

    cache_key = uuid.uuid4().hex
    db.execute(
        text(
            """
            INSERT INTO analysis_base_cache (
                cache_key, region_codes, row_ids, year_from, year_to, expires_at
            ) VALUES (
                :key, :codes, :row_ids, :yf, :yt,
                NOW() + make_interval(hours => :ttl_hours)
            )
            """
        ),
        {
            "key": cache_key,
            "codes": codes,
            "row_ids": list(row_ids),
            "yf": int(year_from),
            "yt": int(year_to),
            "ttl_hours": BASE_CACHE_TTL_HOURS,
        },
    )
    db.commit()
    return cache_key


def has_valid_analysis_base_cache(db: Session, cache_key: str | None) -> bool:
    key = (cache_key or "").strip()
    if not key:
        return False
    ensure_analysis_base_cache_table(db)
    row = db.execute(
        text(
            """
            SELECT 1
            FROM analysis_base_cache
            WHERE cache_key = :key
              AND expires_at > NOW()
              AND cardinality(row_ids) > 0
            LIMIT 1
            """
        ),
        {"key": key},
    ).fetchone()
    return row is not None
