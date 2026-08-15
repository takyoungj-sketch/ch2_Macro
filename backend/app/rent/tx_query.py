"""건물 거래 목록 (원장)."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session


def _lease_kind_sql(alias: str = "t") -> str:
    return f"""
        CASE
          WHEN COALESCE({alias}.monthly_rent_manwon, 0) > 0
           AND COALESCE({alias}.deposit_manwon, 0) > 0 THEN 'mixed'
          WHEN COALESCE({alias}.monthly_rent_manwon, 0) > 0 THEN 'monthly'
          ELSE 'jeonse'
        END
    """


def list_building_transactions(
    db: Session,
    *,
    building_key: str,
    asset_type: Optional[str] = None,
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[int, list[dict[str, Any]]]:
    clauses = ["building_key = :bk", "is_valid = true"]
    params: dict[str, Any] = {"bk": building_key}
    if asset_type:
        clauses.append("asset_type = :at")
        params["at"] = asset_type
    if contract_date_from:
        clauses.append("contract_date >= :d0")
        params["d0"] = contract_date_from
    if contract_date_to:
        clauses.append("contract_date <= :d1")
        params["d1"] = contract_date_to
    where = " AND ".join(clauses)
    total = db.execute(text(f"SELECT COUNT(*) FROM rent_transactions WHERE {where}"), params).scalar()
    params.update({"limit": page_size, "offset": (page - 1) * page_size})
    kind = _lease_kind_sql()
    rows = db.execute(
        text(
            f"""
            SELECT
                id,
                contract_date,
                contract_year,
                contract_month,
                floor,
                exclusive_area,
                contract_area,
                building_year,
                deposit_manwon,
                monthly_rent_manwon,
                deposit_per_m2,
                monthly_per_m2,
                ({kind}) AS lease_kind,
                display_name,
                asset_type
            FROM rent_transactions t
            WHERE {where}
            ORDER BY contract_date DESC NULLS LAST, id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    return int(total or 0), [dict(r) for r in rows]


def fetch_regression_rows(
    db: Session,
    *,
    building_keys: list[str],
    asset_type: Optional[str] = None,
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    lease_kind: str = "jeonse",
) -> list[dict[str, Any]]:
    if not building_keys:
        return []
    clauses = ["building_key IN :keys", "is_valid = true", "deposit_per_m2 IS NOT NULL"]
    params: dict[str, Any] = {"keys": list(building_keys)}
    if asset_type:
        clauses.append("asset_type = :at")
        params["at"] = asset_type
    if contract_date_from:
        clauses.append("contract_date >= :d0")
        params["d0"] = contract_date_from
    if contract_date_to:
        clauses.append("contract_date <= :d1")
        params["d1"] = contract_date_to
    if lease_kind == "jeonse":
        clauses.append("COALESCE(monthly_rent_manwon, 0) = 0 AND COALESCE(deposit_manwon, 0) > 0")
    elif lease_kind == "mixed":
        clauses.append("COALESCE(monthly_rent_manwon, 0) > 0 AND COALESCE(deposit_manwon, 0) > 0")
    where = " AND ".join(clauses)
    stmt = text(
        f"""
        SELECT
            building_key,
            display_name,
            exclusive_area,
            floor,
            building_age,
            deposit_manwon AS price,
            deposit_per_m2 AS unit_price,
            housing_subtype
        FROM rent_transactions
        WHERE {where}
        """
    ).bindparams(bindparam("keys", expanding=True))
    rows = db.execute(stmt, params).mappings().all()
    return [dict(r) for r in rows]
