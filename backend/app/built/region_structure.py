"""시군구별 주소 깊이 — region_sigungu_meta 우선, 없으면 런타임 감지 fallback."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.flat_sido_region import (
    detect_region_structure_for_table,
    normalize_region_asset_type,
    region_scope_clauses,
)
from app.region_catalog import structure_from_meta_or_detect


def _detect_runtime(
    conn: Connection,
    addr1: str,
    addr2: str,
    asset_type: str | None,
) -> dict:
    return detect_region_structure_for_table(
        conn,
        table="built_transactions",
        addr1=addr1,
        addr2=addr2,
        asset_type=asset_type,
        valid_sql="is_valid = true",
    )


def sigungu_has_addr5(
    conn: Connection,
    addr1: str,
    addr2: str,
    asset_type: str | None = None,
) -> bool:
    """시군구 범위에 addr5(법정리) 거래가 하나라도 있으면 True."""
    clauses, params = region_scope_clauses(
        addr1=addr1,
        addr2=addr2,
        asset_type=asset_type,
        valid_sql="is_valid = true",
    )
    clauses.append("addr5 IS NOT NULL AND btrim(addr5::text) <> ''")
    row = conn.execute(
        text(f"SELECT 1 FROM built_transactions WHERE {' AND '.join(clauses)} LIMIT 1"),
        params,
    ).first()
    return row is not None


def detect_region_structure(
    conn: Connection,
    addr1: str,
    addr2: str,
    asset_type: str | None = None,
) -> dict:
    asset_type = normalize_region_asset_type(asset_type)
    return structure_from_meta_or_detect(
        conn,
        domain="built",
        table="built_transactions",
        addr1=addr1,
        addr2=addr2,
        asset_type=asset_type,
        detect_fn=_detect_runtime,
    )
