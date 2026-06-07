"""집합부동산 WHERE 절 helpers."""

from __future__ import annotations

from typing import Optional


def _col(name: str, prefix: str = "") -> str:
    return f"{prefix}.{name}" if prefix else name


def apply_region_filters(
    clauses: list[str],
    params: dict,
    *,
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3: Optional[str] = None,
    addr3_list: list[str] | None = None,
    addr4_list: list[str] | None = None,
    col_prefix: str = "",
) -> None:
    if addr1:
        clauses.append(f"{_col('addr1', col_prefix)} = :addr1")
        params["addr1"] = addr1
    if addr2:
        clauses.append(f"{_col('addr2', col_prefix)} = :addr2")
        params["addr2"] = addr2
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
