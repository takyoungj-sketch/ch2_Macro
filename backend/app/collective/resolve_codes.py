"""집합 addr 선택 → 지도(/api/map)용 행정코드 해석."""

from __future__ import annotations

from typing import Any, Literal, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.collective.asset_scope import apply_collective_asset_filter
from app.collective.filters import apply_region_filters
from app.collective.region_structure import detect_region_structure
from app.flat_sido_region import is_flat_sido_addr2

MapAdminLevel = Literal["sido", "sigungu", "eupmyeondong", "beopjungri"]

_CODE_COL: dict[MapAdminLevel, str] = {
    "sido": "sido_code",
    "sigungu": "sigungu_code",
    "eupmyeondong": "eupmyeondong_code",
    "beopjungri": "beopjungri_code",
}


def _norm_list(values: list[str] | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values or []:
        s = str(raw or "").strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def resolve_collective_map_codes(
    conn: Connection,
    *,
    asset_type: Optional[str] = None,
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    gu_list: list[str] | None = None,
    leaf_list: list[str] | None = None,
    table: str = "collective_transactions",
) -> dict[str, Any]:
    """선택 depth → MapSelectionState 호환 dict. leaf > gu > addr2 > addr1."""
    if table not in ("collective_transactions", "collective_commercial_transactions"):
        raise ValueError(f"unsupported table: {table}")

    a1 = (addr1 or "").strip() or None
    a2 = (addr2 or "").strip() or None
    gus = _norm_list(gu_list)
    leaves = _norm_list(leaf_list)

    empty = {
        "level": None,
        "selected_codes": [],
        "context_sido_code": None,
        "context_sigungu_code": None,
        "labels": {},
        "has_selection": False,
    }
    if not a1:
        return empty

    addr3_list: list[str] = []
    addr4_list: list[str] = []
    level: MapAdminLevel

    if leaves:
        level = "eupmyeondong"
        if a2 and not is_flat_sido_addr2(a2):
            info = detect_region_structure(conn, a1, a2, asset_type, table=table)
            if info.get("has_intermediate") or info.get("leaf_level") == "addr4":
                addr3_list = gus
                addr4_list = leaves
            else:
                addr3_list = leaves
        else:
            addr3_list = leaves
    elif gus:
        level = "sigungu"
        addr3_list = gus
    elif a2:
        level = "sigungu"
    else:
        level = "sido"

    clauses = ["is_valid = true"]
    params: dict[str, Any] = {}
    apply_collective_asset_filter(clauses, params, asset_type)

    apply_region_filters(
        clauses,
        params,
        conn=conn,
        table=table,
        addr1=a1,
        addr2=a2,
        addr3_list=addr3_list or None,
        addr4_list=addr4_list or None,
        asset_type=asset_type if asset_type and asset_type != "all" else None,
        valid_sql="is_valid = true",
    )

    col = _CODE_COL[level]
    where = " AND ".join(clauses)
    from app.region_canonical import (
        canonical_prefix_expr,
        canonical_select_expr,
        resolve_to_canonical,
    )

    # D-028: user-facing map grain is always canonical (hist eup with NULL beopjungri)
    if level == "beopjungri":
        code_sql = f"({canonical_select_expr('t')})"
        filter_sql = (
            "t.beopjungri_code IS NOT NULL AND btrim(t.beopjungri_code::text) <> ''"
        )
    elif level == "eupmyeondong":
        code_sql = f"({canonical_prefix_expr('t', 8)})"
        filter_sql = f"({canonical_prefix_expr('t', 8)}) IS NOT NULL"
    elif level == "sigungu":
        code_sql = f"({canonical_prefix_expr('t', 5)})"
        filter_sql = f"({canonical_prefix_expr('t', 5)}) IS NOT NULL"
    else:
        code_sql = f"btrim(t.{col}::text)"
        filter_sql = f"t.{col} IS NOT NULL AND btrim(t.{col}::text) <> ''"

    rows = conn.execute(
        text(
            f"""
            SELECT DISTINCT {code_sql} AS code
            FROM {table} t
            WHERE {where}
              AND {filter_sql}
            ORDER BY 1
            """
        ),
        params,
    ).fetchall()
    codes = [str(r[0]).strip() for r in rows if r and r[0]]
    if level == "beopjungri" and codes:
        codes = resolve_to_canonical(conn, codes)
    elif not codes and level in ("eupmyeondong", "sigungu"):
        hit = conn.execute(
            text(f"SELECT 1 FROM {table} t WHERE {where} LIMIT 1"),
            params,
        ).first()
        if hit:
            from app.region_canonical import lookup_active_admin_codes_by_name

            codes = lookup_active_admin_codes_by_name(
                conn,
                level=level,
                sido_name=a1 or "",
                sigungu_name=a2,
                names=addr4_list or addr3_list or leaves,
            )

    ctx_sido = codes[0][:2] if codes else None
    ctx_sigungu: str | None = None
    if level in ("eupmyeondong", "beopjungri") and codes:
        ctx_sigungu = codes[0][:5]
    elif level == "sigungu" and codes:
        ctx_sigungu = codes[0][:5]

    return {
        "level": level if codes else None,
        "selected_codes": codes,
        "context_sido_code": ctx_sido,
        "context_sigungu_code": ctx_sigungu,
        "labels": {},
        "has_selection": bool(codes),
    }
