"""시군구별 주소 깊이 — region_sigungu_meta 우선, 없으면 런타임 감지 fallback."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from app.flat_sido_region import detect_region_structure_for_table, normalize_region_asset_type
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
