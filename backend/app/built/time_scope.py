"""as_of_month + window_years — contract_date 롤링 창 (토지 V2·집합과 동일)."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.engine import Connection


def last_day_of_month(d: date) -> date:
    last = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last)


def parse_as_of_month(s: str) -> date:
    parts = s.strip().split("-")
    if len(parts) < 2:
        raise ValueError(f"as_of_month 형식 오류: {s}")
    y, m = int(parts[0]), int(parts[1])
    return date(y, m, 1)


def period_bounds_for_window(as_of_month: date, window_years: int) -> tuple[date, date]:
    if as_of_month.day != 1:
        raise ValueError(f"as_of_month 는 해당 월 1일이어야 합니다: {as_of_month}")
    period_end = last_day_of_month(as_of_month)
    anchor = date(period_end.year - window_years, period_end.month, period_end.day)
    try:
        anchor = date(anchor.year, anchor.month, min(anchor.day, calendar.monthrange(anchor.year, anchor.month)[1]))
    except ValueError:
        anchor = date(anchor.year, anchor.month, calendar.monthrange(anchor.year, anchor.month)[1])
    period_start = anchor + timedelta(days=1)
    return period_start, period_end


def default_as_of_month(today: date | None = None) -> date:
    today = today or date.today()
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    return last_prev.replace(day=1)


def resolve_latest_as_of(conn: Connection) -> date:
    row = conn.execute(
        text(
            """
            SELECT MAX(contract_date) AS max_d FROM built_transactions
            WHERE is_valid = true AND contract_date IS NOT NULL
            """
        )
    ).one()
    if row.max_d:
        d = row.max_d if isinstance(row.max_d, date) else row.max_d.date()
        return date(d.year, d.month, 1)
    return default_as_of_month()


def apply_contract_date_window(
    clauses: list[str],
    params: dict,
    *,
    as_of_month: date | None,
    window_years: int | None,
    col_prefix: str = "",
) -> None:
    if as_of_month is None or window_years is None:
        return
    start, end = period_bounds_for_window(as_of_month, window_years)
    p = f"{col_prefix}." if col_prefix else ""
    # contract_date 미적재 원장(Phase A ingest) — contract_year 로 롤링 창 근사
    clauses.append(
        f"(({p}contract_date >= :cd_start AND {p}contract_date <= :cd_end)"
        f" OR ({p}contract_date IS NULL AND {p}contract_year >= :cy_start"
        f" AND {p}contract_year <= :cy_end))"
    )
    params["cd_start"] = start
    params["cd_end"] = end
    params["cy_start"] = start.year
    params["cy_end"] = end.year
