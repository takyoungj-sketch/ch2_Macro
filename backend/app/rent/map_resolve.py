"""임대 지역 선택 → /api/map 행정코드."""

from __future__ import annotations

from typing import Any, Literal, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from app.flat_sido_region import is_flat_sido_addr2

MapAdminLevel = Literal["sido", "sigungu", "eupmyeondong"]


def majority_emd_codes(counted: list[tuple[str, int]]) -> list[str]:
    """법정동 오분류 소수 건이 다른 읍면동 전체를 선택으로 그리지 않게 한다."""
    if not counted:
        return []
    top = max(n for _c, n in counted)
    floor = max(5, int(top * 0.1))
    kept = [c for c, n in counted if n == top or n >= floor]
    return kept or [counted[0][0]]


def _lookup_emd_codes_by_name(
    conn: Connection,
    codes: list[str],
    leaves: list[str],
) -> set[str]:
    if not codes or not leaves:
        return set()
    sql = text(
        """
        SELECT DISTINCT btrim(eupmyeondong_code::text)
        FROM region_codes
        WHERE eupmyeondong_name IN :leaves
          AND btrim(eupmyeondong_code::text) IN :codes
        """
    ).bindparams(
        bindparam("leaves", expanding=True),
        bindparam("codes", expanding=True),
    )
    try:
        rows = conn.execute(sql, {"leaves": leaves, "codes": codes})
    except Exception:
        return set()
    return {str(r[0]).strip() for r in rows if r and r[0]}


def emd_codes_for_leaf_names(
    conn: Connection,
    codes: list[str],
    leaves: list[str],
    counted: list[tuple[str, int]],
) -> list[str]:
    named = _lookup_emd_codes_by_name(conn, codes, leaves)
    if named:
        hit = [c for c in codes if c in named]
        if hit:
            return hit
    return majority_emd_codes(counted)


def _norm(values: list[str] | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values or []:
        s = str(raw or "").strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def resolve_rent_map_codes(
    conn: Connection,
    *,
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    gu_list: list[str] | None = None,
    leaf_list: list[str] | None = None,
) -> dict[str, Any]:
    empty = {
        "level": None,
        "selected_codes": [],
        "context_sido_code": None,
        "context_sigungu_code": None,
        "labels": {},
        "has_selection": False,
    }
    a1 = (addr1 or "").strip()
    a2 = (addr2 or "").strip()
    gus = _norm(gu_list)
    leaves = _norm(leaf_list)
    if not a1:
        return empty

    # 마트에는 sido/eupmyeondong 컬럼이 없고 sigungu_code·beopjungri_code만 있다.
    # 청주 등: gu=addr3(구), leaf=addr4(동). 일반: leaf=addr3(동).
    expand_keys: list[str] = []
    if leaves:
        level: MapAdminLevel = "eupmyeondong"
        col_expr = "LEFT(btrim(beopjungri_code::text), 8)"
        col_ok = "beopjungri_code IS NOT NULL AND length(btrim(beopjungri_code::text)) >= 8"
    elif gus or a2:
        level = "sigungu"
        col_expr = "btrim(sigungu_code::text)"
        col_ok = "sigungu_code IS NOT NULL AND btrim(sigungu_code::text) <> ''"
    else:
        level = "sido"
        col_expr = "LEFT(btrim(COALESCE(sigungu_code, beopjungri_code)::text), 2)"
        col_ok = (
            "(sigungu_code IS NOT NULL AND btrim(sigungu_code::text) <> '')"
            " OR (beopjungri_code IS NOT NULL AND btrim(beopjungri_code::text) <> '')"
        )

    clauses = [col_ok, "addr1 = :a1"]
    params: dict[str, Any] = {"a1": a1}
    if a2 and not is_flat_sido_addr2(a2):
        clauses.append("addr2 = :a2")
        params["a2"] = a2
    if gus:
        clauses.append("addr3 IN :gus")
        params["gus"] = gus
        expand_keys.append("gus")
    if leaves:
        if gus:
            clauses.append("addr4 IN :leaves")
        else:
            clauses.append("addr3 IN :leaves")
        params["leaves"] = leaves
        expand_keys.append("leaves")

    sql = text(
        f"""
        SELECT {col_expr} AS code, COUNT(*)::int AS n
        FROM rent_building_stats
        WHERE {" AND ".join(clauses)}
        GROUP BY 1
        ORDER BY 2 DESC, 1
        """
    )
    if expand_keys:
        sql = sql.bindparams(*[bindparam(k, expanding=True) for k in expand_keys])
    counted = [
        (str(r[0]).strip(), int(r[1]))
        for r in conn.execute(sql, params)
        if r and r[0]
    ]
    codes = [c for c, _n in counted]
    if level == "eupmyeondong" and leaves and codes:
        codes = emd_codes_for_leaf_names(conn, codes, leaves, counted)
    ctx_sido = codes[0][:2] if codes else None
    ctx_sigungu = codes[0][:5] if codes and level != "sido" else None
    return {
        "level": level if codes else None,
        "selected_codes": codes,
        "context_sido_code": ctx_sido,
        "context_sigungu_code": ctx_sigungu,
        "labels": {},
        "has_selection": bool(codes),
    }
