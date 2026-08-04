"""복합 addr 선택 → 지도(/api/map)용 행정코드 해석."""

from __future__ import annotations

from typing import Any, Literal, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.built.region_structure import detect_region_structure
from app.built.transaction_scope import build_transaction_where, parse_ri_picks
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


def resolve_built_map_codes(
    conn: Connection,
    *,
    asset_type: Optional[str] = None,
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    gu_list: list[str] | None = None,
    leaf_list: list[str] | None = None,
    ri_pick: list[str] | None = None,
) -> dict[str, Any]:
    """
    선택 depth → MapSelectionState 호환 dict.
    ri > leaf > gu > addr2 > addr1.
    """
    a1 = (addr1 or "").strip() or None
    a2 = (addr2 or "").strip() or None
    gus = _norm_list(gu_list)
    leaves = _norm_list(leaf_list)
    ris = parse_ri_picks(ri_pick or [])

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

    if ris:
        level = "beopjungri"
        if a2 and not is_flat_sido_addr2(a2):
            info = detect_region_structure(conn, a1, a2, asset_type)
            if info.get("has_intermediate") or info.get("leaf_level") == "addr4":
                addr3_list = gus
                addr4_list = leaves
            else:
                addr3_list = leaves or gus
        else:
            addr3_list = leaves or gus
    elif leaves:
        level = "eupmyeondong"
        if a2 and not is_flat_sido_addr2(a2):
            info = detect_region_structure(conn, a1, a2, asset_type)
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

    where, params = build_transaction_where(
        conn=conn,
        asset_type=asset_type,
        addr1=a1,
        addr2=a2,
        addr3_list=addr3_list or None,
        addr4_list=addr4_list or None,
        ri_pick=[f"{p.eup}|{p.ri}" for p in ris] if ris else None,
    )
    col = _CODE_COL[level]
    history_ready = bool(
        conn.execute(text("SELECT to_regclass('public.region_code_history')")).scalar()
    )
    from app.region_canonical import (
        canonical_prefix_expr,
        canonical_select_expr,
        resolve_to_canonical,
    )

    # D-028: user-facing map grain is always canonical when history is synced.
    # Built rows often have NULL beopjungri_code with historical eupmyeondong_code.
    # If region_code_history is missing (sync not run), fall back to raw ledger codes
    # so map resolve does not 500.
    if level == "beopjungri":
        if history_ready:
            code_sql = f"({canonical_select_expr('lt')})"
        else:
            code_sql = "NULLIF(btrim(lt.beopjungri_code::text), '')"
        filter_sql = (
            "lt.beopjungri_code IS NOT NULL AND btrim(lt.beopjungri_code::text) <> ''"
        )
    elif level == "eupmyeondong":
        if history_ready:
            code_sql = f"({canonical_prefix_expr('lt', 8)})"
            filter_sql = f"({canonical_prefix_expr('lt', 8)}) IS NOT NULL"
        else:
            code_sql = (
                "CASE WHEN length(btrim(COALESCE("
                "NULLIF(btrim(lt.beopjungri_code::text), ''), "
                "NULLIF(btrim(lt.eupmyeondong_code::text), ''), ''))) >= 8 "
                "THEN left(btrim(COALESCE("
                "NULLIF(btrim(lt.beopjungri_code::text), ''), "
                "NULLIF(btrim(lt.eupmyeondong_code::text), ''), '')), 8) "
                "ELSE NULL END"
            )
            filter_sql = f"({code_sql}) IS NOT NULL"
    elif level == "sigungu":
        if history_ready:
            code_sql = f"({canonical_prefix_expr('lt', 5)})"
            filter_sql = f"({canonical_prefix_expr('lt', 5)}) IS NOT NULL"
        else:
            code_sql = (
                "CASE WHEN length(btrim(COALESCE("
                "NULLIF(btrim(lt.sigungu_code::text), ''), "
                "NULLIF(btrim(lt.beopjungri_code::text), ''), "
                "NULLIF(btrim(lt.eupmyeondong_code::text), ''), ''))) >= 5 "
                "THEN left(btrim(COALESCE("
                "NULLIF(btrim(lt.sigungu_code::text), ''), "
                "NULLIF(btrim(lt.beopjungri_code::text), ''), "
                "NULLIF(btrim(lt.eupmyeondong_code::text), ''), '')), 5) "
                "ELSE NULL END"
            )
            filter_sql = f"({code_sql}) IS NOT NULL"
    else:
        code_sql = f"btrim(lt.{col}::text)"
        filter_sql = f"lt.{col} IS NOT NULL AND btrim(lt.{col}::text) <> ''"

    rows = conn.execute(
        text(
            f"""
            SELECT DISTINCT {code_sql} AS code
            FROM (
              SELECT * FROM built_transactions
              WHERE {where}
            ) lt
            WHERE {filter_sql}
            ORDER BY 1
            """
        ),
        params,
    ).fetchall()
    codes = [str(r[0]).strip() for r in rows if r and r[0]]
    labels: dict[str, str] = {}
    if level == "beopjungri":
        if history_ready:
            codes = resolve_to_canonical(conn, codes)
        # NULL beopjungri 원장 → region_codes로 선택 리의 canonical 코드 보강
        if ris:
            from app.region_canonical import lookup_active_beopjungri_by_ri_picks

            for code, label in lookup_active_beopjungri_by_ri_picks(
                conn,
                sido_name=a1 or "",
                sigungu_name=a2,
                picks=[(p.eup, p.ri) for p in ris],
            ):
                if code not in codes:
                    codes.append(code)
                labels[code] = label
        # 코드만 있는 경우에도 UI name/region_addrs용 라벨 채움
        missing = [c for c in codes if c not in labels]
        if missing:
            rows_lb = conn.execute(
                text(
                    """
                    SELECT btrim(beopjungri_code::text) AS code,
                           btrim(eupmyeondong_name::text) AS eup,
                           btrim(beopjungri_name::text) AS ri
                    FROM region_codes
                    WHERE COALESCE(is_active, TRUE)
                      AND btrim(beopjungri_code::text) = ANY(:codes)
                    """
                ),
                {"codes": missing},
            ).mappings().all()
            for row in rows_lb:
                code = str(row["code"]).strip()
                eup_n = (row.get("eup") or "").strip()
                ri_n = (row.get("ri") or "").strip()
                if code and ri_n:
                    labels[code] = f"{eup_n} {ri_n}".strip()
    elif not codes and level in ("eupmyeondong", "sigungu"):
        # Addr-matched rows may have NULL admin codes — active region_codes by name
        hit = conn.execute(
            text(
                f"""
                SELECT 1 FROM (
                  SELECT * FROM built_transactions WHERE {where}
                ) lt LIMIT 1
                """
            ),
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

    if history_ready and codes:
        codes = resolve_to_canonical(conn, codes)

    if level == "eupmyeondong" and codes:
        rows_lb = conn.execute(
            text(
                """
                SELECT DISTINCT ON (btrim(eupmyeondong_code::text))
                       btrim(eupmyeondong_code::text) AS code,
                       btrim(eupmyeondong_name::text) AS eup
                FROM region_codes
                WHERE COALESCE(is_active, TRUE)
                  AND btrim(eupmyeondong_code::text) = ANY(:codes)
                  AND eupmyeondong_name IS NOT NULL
                  AND btrim(eupmyeondong_name::text) <> ''
                ORDER BY btrim(eupmyeondong_code::text), beopjungri_code
                """
            ),
            {"codes": list(codes)},
        ).mappings().all()
        for row in rows_lb:
            code = str(row["code"]).strip()
            eup = (row.get("eup") or "").strip()
            if code and eup:
                labels[code] = eup

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
        "labels": labels,
        "has_selection": bool(codes),
    }
