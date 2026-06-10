"""시군구별 주소 깊이(구 → 읍면동) 감지."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from app.flat_sido_region import detect_region_structure_for_table


def detect_region_structure(
    conn: Connection,
    addr1: str,
    addr2: str,
    asset_type: str | None = None,
) -> dict:
    return detect_region_structure_for_table(
        conn,
        table="built_transactions",
        addr1=addr1,
        addr2=addr2,
        asset_type=asset_type,
        valid_sql="is_valid = true",
    )
