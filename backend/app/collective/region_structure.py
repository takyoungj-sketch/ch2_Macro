"""시군구별 주소 깊이(구 → 읍면동) 감지 — built와 동일 규칙."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from app.flat_sido_region import detect_region_structure_for_table

_TX_TABLES = frozenset({"collective_transactions", "collective_commercial_transactions"})


def detect_region_structure(
    conn: Connection,
    addr1: str,
    addr2: str,
    asset_type: str | None = None,
    *,
    table: str = "collective_transactions",
) -> dict:
    if table not in _TX_TABLES:
        raise ValueError(f"unsupported table: {table}")
    return detect_region_structure_for_table(
        conn,
        table=table,
        addr1=addr1,
        addr2=addr2,
        asset_type=asset_type,
        valid_sql="is_valid = true",
    )
