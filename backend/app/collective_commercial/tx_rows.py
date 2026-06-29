"""commercial transaction row serialization."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy.engine import Connection

from app.collective.filters import apply_contract_date_filters, apply_period_filters
from app.collective_commercial.cluster_stats_query import latest_mart_snapshot
from app.v2_stats_windows import period_bounds_for_window


def commercial_tx_row_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    cd = d.get("contract_date")
    if cd is not None and hasattr(cd, "isoformat"):
        d["contract_date"] = cd.isoformat()
    return d


def apply_commercial_tx_period(
    conn: Connection | None,
    clauses: list[str],
    params: dict,
    *,
    window_years: int | None = None,
    contract_year_from: int | None = None,
    contract_year_to: int | None = None,
    contract_date_from: date | None = None,
    contract_date_to: date | None = None,
    col_prefix: str = "",
) -> None:
    """연도·일자 필터 우선; 없으면 mart as_of + window_years 롤링 창."""
    if (
        contract_date_from is not None
        or contract_date_to is not None
        or contract_year_from is not None
        or contract_year_to is not None
    ):
        apply_period_filters(
            clauses,
            params,
            contract_date_from=contract_date_from,
            contract_date_to=contract_date_to,
            contract_year_from=contract_year_from,
            contract_year_to=contract_year_to,
            col_prefix=col_prefix,
        )
        return
    if window_years is not None and conn is not None:
        as_of, _ = latest_mart_snapshot(conn)
        if as_of:
            ps, pe = period_bounds_for_window(as_of, window_years)
            apply_contract_date_filters(
                clauses,
                params,
                contract_date_from=ps,
                contract_date_to=pe,
                col_prefix=col_prefix,
            )
