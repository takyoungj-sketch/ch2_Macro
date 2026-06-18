"""region_codes + 거래 집계 기반 캐스케이드 카탈로그."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.flat_sido_region import FLAT_SIDO_ADDR2_TOKEN, is_flat_sido_addr2
from app.stats_utils import MIN_RELIABLE_COUNT

MIN_LEAF_COUNT = MIN_RELIABLE_COUNT


def _asset_clause(asset_type: str | None, *, prefix: str = "t") -> tuple[str, dict]:
    if not asset_type:
        return "", {}
    return f" AND {prefix}.asset_type = :asset_type", {"asset_type": asset_type}


def fetch_sigungu_meta(
    conn: Connection,
    *,
    domain: str,
    addr1: str,
    addr2: str,
    asset_type: str | None,
) -> dict | None:
    if not conn.execute(
        text("SELECT to_regclass('public.region_sigungu_meta') IS NOT NULL")
    ).scalar():
        return None
    token = FLAT_SIDO_ADDR2_TOKEN if is_flat_sido_addr2(addr2) else addr2.strip()
    params: dict[str, Any] = {
        "domain": domain,
        "a1": addr1.strip(),
        "token": token,
    }
    asset_sql = ""
    if asset_type:
        asset_sql = " AND (asset_type IS NULL OR asset_type = :asset_type)"
        params["asset_type"] = asset_type
    row = conn.execute(
        text(
            f"""
            SELECT structure_type, leaf_level, has_ri, tx_count, mapped_tx_count,
                   intermediate_label
            FROM (
                SELECT structure_type, leaf_level, has_ri, tx_count, mapped_tx_count,
                       CASE WHEN structure_type = 'GU' THEN '구' ELSE NULL END AS intermediate_label
                FROM region_sigungu_meta
                WHERE asset_domain = :domain
                  AND sido_name = :a1
                  AND addr2_token = :token
                  {asset_sql}
                ORDER BY CASE WHEN asset_type IS NOT NULL THEN 0 ELSE 1 END, tx_count DESC
                LIMIT 1
            ) sub
            """
        ),
        params,
    ).mappings().first()
    if row:
        return dict(row)
    return None


def structure_from_meta_or_detect(
    conn: Connection,
    *,
    domain: str,
    table: str,
    addr1: str,
    addr2: str,
    asset_type: str | None,
    detect_fn,
) -> dict:
    meta = fetch_sigungu_meta(conn, domain=domain, addr1=addr1, addr2=addr2, asset_type=asset_type)
    if meta:
        st = meta["structure_type"]
        return {
            "has_intermediate": st == "GU",
            "intermediate_label": meta.get("intermediate_label"),
            "leaf_level": meta["leaf_level"],
            "has_ri": bool(meta.get("has_ri")),
            "tx_count": int(meta.get("tx_count") or 0),
        }
    info = detect_fn(conn, addr1, addr2, asset_type)
    info["has_ri"] = False
    info["tx_count"] = 0
    return info


def _tx_join(table: str, asset_type: str | None) -> tuple[str, dict]:
    clause, params = _asset_clause(asset_type, prefix="t")
    return (
        f"""
        FROM region_codes rc
        LEFT JOIN {table} t
          ON t.beopjungri_code = rc.beopjungri_code
         AND t.is_valid = true
         {clause}
        WHERE COALESCE(rc.is_active, true)
        """,
        params,
    )


def list_gu_options(
    conn: Connection,
    *,
    table: str,
    addr1: str,
    addr2: str,
    asset_type: str | None,
) -> list[dict]:
    """구-동 구조: addr3(구) 목록 + 건수."""
    params: dict[str, Any] = {"a1": addr1.strip()}
    addr2_sql = ""
    if not is_flat_sido_addr2(addr2):
        addr2_sql = " AND t.addr2 = :a2"
        params["a2"] = addr2.strip()
    ac, ap = _asset_clause(asset_type)
    params.update(ap)
    rows = conn.execute(
        text(
            f"""
            SELECT t.addr3 AS name, COUNT(*)::int AS count
            FROM {table} t
            WHERE t.addr1 = :a1
              AND t.is_valid = true
              {addr2_sql}
              {ac}
              AND t.addr3 IS NOT NULL AND btrim(t.addr3::text) <> ''
              AND t.addr3 LIKE '%구'
            GROUP BY t.addr3
            ORDER BY count DESC, t.addr3
            """
        ),
        params,
    ).mappings().all()
    return [_option_row(r, check_density=False) for r in rows]


def list_leaf_options(
    conn: Connection,
    *,
    table: str,
    addr1: str,
    addr2: str,
    gu_list: list[str],
    asset_type: str | None,
    leaf_level: str,
) -> list[dict]:
    """읍면동(leaf) 목록."""
    params: dict[str, Any] = {"a1": addr1.strip()}
    addr2_sql = ""
    if not is_flat_sido_addr2(addr2):
        addr2_sql = "AND t.addr2 = :a2"
        params["a2"] = addr2.strip()
    gu_sql = ""
    if gu_list:
        gu_sql = "AND t.addr3 = ANY(:gu_list)"
        params["gu_list"] = gu_list
    ac, ap = _asset_clause(asset_type)
    params.update(ap)

    if leaf_level == "addr4":
        rows = conn.execute(
            text(
                f"""
                SELECT addr4 AS name, addr3 AS parent, COUNT(*)::int AS count
                FROM {table} t
                WHERE t.is_valid = true
                  AND t.addr1 = :a1
                  {addr2_sql}
                  {gu_sql}
                  {ac}
                  AND addr4 IS NOT NULL AND btrim(addr4::text) <> ''
                GROUP BY addr4, addr3
                ORDER BY addr3, count DESC, addr4
                """
            ),
            params,
        ).mappings().all()
    else:
        rows = conn.execute(
            text(
                f"""
                SELECT addr3 AS name, NULL::text AS parent, COUNT(*)::int AS count
                FROM {table} t
                WHERE t.is_valid = true
                  AND t.addr1 = :a1
                  {addr2_sql}
                  {ac}
                  AND addr3 IS NOT NULL AND btrim(addr3::text) <> ''
                GROUP BY addr3
                ORDER BY count DESC, addr3
                """
            ),
            params,
        ).mappings().all()
    return [_option_row(r, parent=r.get("parent")) for r in rows]


def list_ri_options(
    conn: Connection,
    *,
    table: str,
    addr1: str,
    addr2: str,
    gu_list: list[str],
    leaf_list: list[str],
    leaf_level: str,
    asset_type: str | None,
) -> list[dict]:
    params: dict[str, Any] = {"a1": addr1.strip()}
    addr2_sql = ""
    if not is_flat_sido_addr2(addr2):
        addr2_sql = "AND t.addr2 = :a2"
        params["a2"] = addr2.strip()
    ac, ap = _asset_clause(asset_type)
    params.update(ap)

    if leaf_level == "addr4" and leaf_list:
        params["leaf_list"] = leaf_list
        leaf_sql = "AND addr4 = ANY(:leaf_list)"
        if gu_list:
            params["gu_list"] = gu_list
            leaf_sql += " AND addr3 = ANY(:gu_list)"
    elif leaf_list:
        params["leaf_list"] = leaf_list
        leaf_sql = "AND addr3 = ANY(:leaf_list)"
    else:
        return []

    rows = conn.execute(
        text(
            f"""
            SELECT
                addr5 AS name,
                COALESCE(NULLIF(btrim(addr4::text), ''), NULLIF(btrim(addr3::text), '')) AS parent,
                COUNT(*)::int AS count
            FROM {table} t
            WHERE t.is_valid = true
              AND t.addr1 = :a1
              {addr2_sql}
              {ac}
              {leaf_sql}
              AND addr5 IS NOT NULL AND btrim(addr5::text) <> ''
            GROUP BY addr5,
                COALESCE(NULLIF(btrim(addr4::text), ''), NULLIF(btrim(addr3::text), ''))
            ORDER BY parent, count DESC, addr5
            """
        ),
        params,
    ).mappings().all()
    return [_option_row(r, parent=r.get("parent")) for r in rows]


def _option_row(row: dict, *, parent: str | None = None, check_density: bool = True) -> dict:
    count = int(row.get("count") or 0)
    return {
        "name": row["name"],
        "count": count,
        "parent": parent if parent is not None else row.get("parent"),
        "disabled": check_density and count < MIN_LEAF_COUNT,
        "min_reliable_count": MIN_LEAF_COUNT,
    }
