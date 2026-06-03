"""집합부동산 WHERE 절 helpers."""

from __future__ import annotations

from typing import Optional


def apply_region_filters(
    clauses: list[str],
    params: dict,
    *,
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3: Optional[str] = None,
    addr3_list: list[str] | None = None,
) -> None:
    if addr1:
        clauses.append("addr1 = :addr1")
        params["addr1"] = addr1
    if addr2:
        clauses.append("addr2 = :addr2")
        params["addr2"] = addr2
    if addr3_list:
        clauses.append("addr3 = ANY(:addr3_list)")
        params["addr3_list"] = addr3_list
    elif addr3:
        clauses.append("addr3 = :addr3")
        params["addr3"] = addr3


def apply_year_filters(
    clauses: list[str],
    params: dict,
    *,
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
) -> None:
    if contract_year_from is not None:
        clauses.append("contract_year >= :cy_from")
        params["cy_from"] = contract_year_from
    if contract_year_to is not None:
        clauses.append("contract_year <= :cy_to")
        params["cy_to"] = contract_year_to
