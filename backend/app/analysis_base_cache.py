"""Paid/free analysis base-row cache helpers.

The paid UI is two-step:
1) choose region(s) and show the basic statistics,
2) re-analyze the same base rows with additional paid filters.

This module stores the transaction ids selected in step 1 so step 2 does not
need to re-expand/scan the whole region range again.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session


BASE_CACHE_TTL_HOURS = 4


def _paid_ui_chip_year_bounds() -> tuple[int, int]:
    """
    유료 필터 칩 연도 구간과 동일해야 함 (`frontend/constants/paidFilters.ts` 의 getPaidYearButtonYears).
    당해 기준 CY-5 … CY (올해 포함 6개년).
    """

    cy = date.today().year
    return cy - 5, cy


def _expanded_row_cache_bounds(year_from_basic: int, year_to_basic: int) -> tuple[int, int]:
    """
    기본 통계 사전집계 창 ∪ 유료 칩 가능 구간 을 포함.
    그렇지 않으면 기본통계 창이 일부 연도만 되어도 칩으로 21 등을 선택해도 캐시 row_ids 에 해당 연도가 없어 필터 결과가 빈다.
    """
    yf_chip, yt_chip = _paid_ui_chip_year_bounds()
    return min(int(year_from_basic), yf_chip), max(int(year_to_basic), yt_chip)


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
    """
    선택 지역 후보 거래 id 캐시.
    저장 구간은 (기본통계 연도 ∪ 유료 필터 칩 구간 CY-5…CY) 로 넓히며,
    두 번째 단계 필터 연도 선택이 가능한 모든 칩값을 커버한다.
    """

    codes = sorted({str(c).strip() for c in region_codes if str(c).strip()})
    if not codes:
        return None

    yf, yt = _expanded_row_cache_bounds(year_from, year_to)

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
        {"codes": codes, "yf": int(yf), "yt": int(yt)},
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
            "yf": int(yf),
            "yt": int(yt),
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
