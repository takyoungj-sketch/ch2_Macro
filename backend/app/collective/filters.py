"""집합부동산 WHERE 절 helpers."""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.engine import Connection

from app.flat_sido_region import apply_addr2_scope
from app.region_scope import apply_region_scope


def _col(name: str, prefix: str = "") -> str:
    return f"{prefix}.{name}" if prefix else name


def apply_region_filters(
    clauses: list[str],
    params: dict,
    *,
    conn: Connection | None = None,
    table: str = "collective_transactions",
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3: Optional[str] = None,
    addr3_list: list[str] | None = None,
    addr4_list: list[str] | None = None,
    asset_type: Optional[str] = None,
    col_prefix: str = "",
    valid_sql: str | None = "t.is_valid = true",
) -> None:
    if conn is not None and addr1 and addr2:
        apply_region_scope(
            clauses,
            params,
            conn=conn,
            table=table,
            addr1=addr1,
            addr2=addr2,
            addr3=addr3,
            addr3_list=addr3_list,
            addr4_list=addr4_list,
            asset_type=asset_type,
            col_prefix=col_prefix,
            valid_sql=valid_sql,
        )
        return

    if addr1 and addr2:
        apply_addr2_scope(clauses, params, addr1=addr1, addr2=addr2, col_prefix=col_prefix)
    elif addr1:
        p = f"{col_prefix}." if col_prefix else ""
        clauses.append(f"{p}addr1 = :addr1")
        params["addr1"] = addr1.strip()
    if addr4_list:
        clauses.append(f"{_col('addr4', col_prefix)} = ANY(:addr4_list)")
        params["addr4_list"] = addr4_list
    elif addr3_list:
        clauses.append(f"{_col('addr3', col_prefix)} = ANY(:addr3_list)")
        params["addr3_list"] = addr3_list
    elif addr3:
        clauses.append(f"{_col('addr3', col_prefix)} = :addr3")
        params["addr3"] = addr3


def apply_year_filters(
    clauses: list[str],
    params: dict,
    *,
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    col_prefix: str = "",
) -> None:
    if contract_year_from is not None:
        clauses.append(f"{_col('contract_year', col_prefix)} >= :cy_from")
        params["cy_from"] = contract_year_from
    if contract_year_to is not None:
        clauses.append(f"{_col('contract_year', col_prefix)} <= :cy_to")
        params["cy_to"] = contract_year_to


def apply_contract_date_filters(
    clauses: list[str],
    params: dict,
    *,
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    col_prefix: str = "",
) -> None:
    if contract_date_from is None and contract_date_to is None:
        return
    clauses.append(f"{_col('contract_date', col_prefix)} IS NOT NULL")
    if contract_date_from is not None:
        clauses.append(f"{_col('contract_date', col_prefix)} >= :cd_from")
        params["cd_from"] = contract_date_from
    if contract_date_to is not None:
        clauses.append(f"{_col('contract_date', col_prefix)} <= :cd_to")
        params["cd_to"] = contract_date_to


def apply_period_filters(
    clauses: list[str],
    params: dict,
    *,
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    col_prefix: str = "",
) -> None:
    """contract_date 구간이 있으면 연도 필터 대신 일자 구간 적용 (토지 롤링 창과 동일)."""
    if contract_date_from is not None or contract_date_to is not None:
        apply_contract_date_filters(
            clauses,
            params,
            contract_date_from=contract_date_from,
            contract_date_to=contract_date_to,
            col_prefix=col_prefix,
        )
        return
    apply_year_filters(
        clauses,
        params,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
        col_prefix=col_prefix,
    )
