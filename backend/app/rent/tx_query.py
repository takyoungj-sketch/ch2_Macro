"""건물 거래 목록 (원장). 마트와 같은 building_key 해석(빈 키→주소 해시)."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.rent.sql_fragments import building_key_sql


def _lease_kind_sql(alias: str = "t") -> str:
    return f"""
        CASE
          WHEN COALESCE({alias}.monthly_rent_manwon, 0) > 0
           AND COALESCE({alias}.deposit_manwon, 0) > 0 THEN 'mixed'
          WHEN COALESCE({alias}.monthly_rent_manwon, 0) > 0 THEN 'monthly'
          ELSE 'jeonse'
        END
    """


def _key_match_sql(alias: str = "t") -> str:
    return f"{building_key_sql(alias)} = :bk"


def _mart_identity(db: Session, building_key: str) -> dict[str, Any] | None:
    row = db.execute(
        text(
            """
            SELECT asset_type, addr1, addr2, addr3, lot_number, road_name
            FROM rent_building_stats
            WHERE building_key = :bk
            ORDER BY as_of_month DESC, window_years DESC
            LIMIT 1
            """
        ),
        {"bk": building_key},
    ).mappings().first()
    if not row:
        return None
    ident = dict(row)
    if not str(ident.get("addr1") or "").strip() or not str(ident.get("addr2") or "").strip():
        return None
    return ident


def _append_filters(
    clauses: list[str],
    params: dict[str, Any],
    *,
    asset_type: Optional[str],
    contract_date_from: Optional[date],
    contract_date_to: Optional[date],
) -> None:
    if asset_type:
        clauses.append("t.asset_type = :at")
        params["at"] = asset_type
    if contract_date_from:
        clauses.append("t.contract_date >= :d0")
        params["d0"] = contract_date_from
    if contract_date_to:
        clauses.append("t.contract_date <= :d1")
        params["d1"] = contract_date_to


def _identity_clauses(ident: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    return (
        [
            "t.is_valid = true",
            "t.asset_type = :at",
            "t.addr1 = :addr1",
            "t.addr2 = :addr2",
            "COALESCE(t.addr3, '') = :addr3",
            "COALESCE(t.lot_number, '') = :lot",
            "COALESCE(t.road_name, '') = :road",
        ],
        {
            "at": ident["asset_type"],
            "addr1": str(ident.get("addr1") or "").strip(),
            "addr2": str(ident.get("addr2") or "").strip(),
            "addr3": str(ident.get("addr3") or "").strip(),
            "lot": str(ident.get("lot_number") or "").strip(),
            "road": str(ident.get("road_name") or "").strip(),
        },
    )


def _run_page(
    db: Session,
    clauses: list[str],
    params: dict[str, Any],
    *,
    page: int,
    page_size: int,
) -> tuple[int, list[dict[str, Any]]]:
    where = " AND ".join(clauses)
    total = db.execute(
        text(f"SELECT COUNT(*) FROM rent_transactions t WHERE {where}"),
        params,
    ).scalar()
    page_params = dict(params)
    page_params.update({"limit": page_size, "offset": (page - 1) * page_size})
    kind = _lease_kind_sql()
    rows = db.execute(
        text(
            f"""
            SELECT
                t.id,
                t.contract_date,
                t.contract_year,
                t.contract_month,
                t.floor,
                t.exclusive_area,
                t.contract_area,
                t.building_year,
                t.deposit_manwon,
                t.monthly_rent_manwon,
                t.deposit_per_m2,
                t.monthly_per_m2,
                ({kind}) AS lease_kind,
                t.display_name,
                t.asset_type
            FROM rent_transactions t
            WHERE {where}
            ORDER BY t.contract_date DESC NULLS LAST, t.id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        page_params,
    ).mappings().all()
    return int(total or 0), [dict(r) for r in rows]


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
    stored: list[str] = ["t.building_key = :bk", "t.is_valid = true"]
    stored_params: dict[str, Any] = {"bk": building_key}
    _append_filters(
        stored,
        stored_params,
        asset_type=asset_type,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
    )
    total, rows = _run_page(db, stored, stored_params, page=page, page_size=page_size)
    if total > 0:
        return total, rows

    ident = _mart_identity(db, building_key)
    if ident:
        if asset_type:
            ident = {**ident, "asset_type": asset_type}
        ident_clauses, ident_params = _identity_clauses(ident)
        _append_filters(
            ident_clauses,
            ident_params,
            asset_type=None,
            contract_date_from=contract_date_from,
            contract_date_to=contract_date_to,
        )
        total, rows = _run_page(db, ident_clauses, ident_params, page=page, page_size=page_size)
        if total > 0:
            return total, rows

    fallback = [_key_match_sql("t"), "t.is_valid = true"]
    fallback_params: dict[str, Any] = {"bk": building_key}
    _append_filters(
        fallback,
        fallback_params,
        asset_type=asset_type,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
    )
    return _run_page(db, fallback, fallback_params, page=page, page_size=page_size)


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
    clauses = [
        f"{building_key_sql('t')} IN :keys",
        "t.is_valid = true",
        "t.deposit_per_m2 IS NOT NULL",
    ]
    params: dict[str, Any] = {"keys": list(building_keys)}
    if asset_type:
        clauses.append("t.asset_type = :at")
        params["at"] = asset_type
    if contract_date_from:
        clauses.append("t.contract_date >= :d0")
        params["d0"] = contract_date_from
    if contract_date_to:
        clauses.append("t.contract_date <= :d1")
        params["d1"] = contract_date_to
    if lease_kind == "jeonse":
        clauses.append("COALESCE(t.monthly_rent_manwon, 0) = 0 AND COALESCE(t.deposit_manwon, 0) > 0")
    elif lease_kind == "mixed":
        clauses.append("COALESCE(t.monthly_rent_manwon, 0) > 0 AND COALESCE(t.deposit_manwon, 0) > 0")
    where = " AND ".join(clauses)
    stmt = text(
        f"""
        SELECT
            {building_key_sql("t")} AS building_key,
            t.display_name,
            t.exclusive_area,
            t.floor,
            t.building_age,
            t.deposit_manwon AS price,
            t.deposit_per_m2 AS unit_price,
            t.housing_subtype
        FROM rent_transactions t
        WHERE {where}
        """
    ).bindparams(bindparam("keys", expanding=True))
    rows = db.execute(stmt, params).mappings().all()
    return [dict(r) for r in rows]
