"""시군구별 주소 깊이 — region_sigungu_meta 우선, 없으면 런타임 감지 fallback."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from app.flat_sido_region import detect_region_structure_for_table
from app.region_catalog import structure_from_meta_or_detect

_TX_TABLES = frozenset({"collective_transactions", "collective_commercial_transactions"})


def _detect_runtime(
    conn: Connection,
    addr1: str,
    addr2: str,
    asset_type: str | None,
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

    def _fn(c: Connection, a1: str, a2: str, at: str | None) -> dict:
        return _detect_runtime(c, a1, a2, at, table=table)

    return structure_from_meta_or_detect(
        conn,
        domain="collective",
        table=table,
        addr1=addr1,
        addr2=addr2,
        asset_type=asset_type,
        detect_fn=_fn,
    )
