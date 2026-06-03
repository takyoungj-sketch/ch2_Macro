"""시군구별 주소 깊이(구 → 읍면동) 감지."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection


def detect_region_structure(
    conn: Connection,
    addr1: str,
    addr2: str,
    asset_type: str | None = None,
) -> dict:
    """청주·수원 등 addr3=구, addr4=읍면동 패턴 감지."""
    clauses = ["addr1 = :a1", "addr2 = :a2", "is_valid = true"]
    params: dict = {"a1": addr1, "a2": addr2}
    if asset_type:
        clauses.append("asset_type = :asset_type")
        params["asset_type"] = asset_type
    where = " AND ".join(clauses)
    row = conn.execute(
        text(
            f"""
            SELECT COUNT(*)::int AS total,
                   COUNT(*) FILTER (
                       WHERE addr3 IS NOT NULL
                         AND btrim(addr3::text) <> ''
                         AND addr3 LIKE '%구'
                   )::int AS gu_like,
                   COUNT(*) FILTER (
                       WHERE addr4 IS NOT NULL AND btrim(addr4::text) <> ''
                   )::int AS has_a4
            FROM built_transactions
            WHERE {where}
            """
        ),
        params,
    ).one()
    total = int(row.total or 0)
    if total == 0:
        return {
            "has_intermediate": False,
            "intermediate_label": None,
            "leaf_level": "addr3",
        }
    gu_ratio = int(row.gu_like or 0) / total
    a4_ratio = int(row.has_a4 or 0) / total
    if gu_ratio >= 0.85 and a4_ratio >= 0.25:
        return {
            "has_intermediate": True,
            "intermediate_label": "구",
            "leaf_level": "addr4",
        }
    return {
        "has_intermediate": False,
        "intermediate_label": None,
        "leaf_level": "addr3",
    }
