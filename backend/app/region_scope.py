"""beopjungri_code 집합 scope + addr 텍스트 fallback."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.built.asset_scope import apply_asset_type_filter
from app.built.filters import apply_addr3_filter, apply_addr4_filter, apply_ri_filter
from app.flat_sido_region import apply_addr2_scope, is_flat_sido_addr2


def expand_beopjungri_codes(
    conn: Connection,
    *,
    table: str,
    addr1: str | None,
    addr2: str | None,
    addr3: str | None = None,
    addr3_list: list[str] | None = None,
    addr4_list: list[str] | None = None,
    ri_list: list | None = None,
    asset_type: str | None = None,
    valid_sql: str | None = "t.is_valid = true",
) -> list[str]:
    """선택 addr → 매핑된 beopjungri_code 목록."""
    if not addr1 or not addr2:
        return []
    params: dict[str, Any] = {"a1": addr1.strip()}
    clauses: list[str] = []
    if valid_sql:
        clauses.append(valid_sql)
    clauses.extend(
        [
            "t.addr1 = :a1",
            "t.beopjungri_code IS NOT NULL",
            "btrim(t.beopjungri_code::text) <> ''",
        ]
    )
    if is_flat_sido_addr2(addr2):
        clauses.append("(t.addr2 IS NULL OR btrim(t.addr2::text) = '')")
    else:
        clauses.append("t.addr2 = :a2")
        params["a2"] = addr2.strip()
    if asset_type and asset_type != "all":
        clauses.append("t.asset_type = :asset_type")
        params["asset_type"] = asset_type

    tmp_clauses = list(clauses)
    tmp_params = dict(params)
    apply_addr3_filter(tmp_clauses, tmp_params, addr3, addr3_list or [])
    apply_addr4_filter(tmp_clauses, tmp_params, None, addr4_list or [])
    apply_ri_filter(tmp_clauses, tmp_params, ri_list or [])

    rows = conn.execute(
        text(
            f"""
            SELECT DISTINCT btrim(t.beopjungri_code::text) AS code
            FROM {table} t
            WHERE {' AND '.join(tmp_clauses)}
            """
        ),
        tmp_params,
    ).fetchall()
    return [str(r.code) for r in rows if r.code]


def apply_region_scope(
    clauses: list[str],
    params: dict,
    *,
    conn: Connection | None,
    table: str,
    addr1: str | None,
    addr2: str | None,
    addr3: str | None = None,
    addr3_list: list[str] | None = None,
    addr4_list: list[str] | None = None,
    ri_list: list | None = None,
    asset_type: str | None = None,
    col_prefix: str = "",
    valid_sql: str | None = "t.is_valid = true",
) -> None:
    """
    1) beopjungri_code 집합 (매핑된 거래)
    2) fallback: addr 텍스트 필터 (미매핑 거래 포함)
    """
    p = f"{col_prefix}." if col_prefix else ""
    codes: list[str] = []
    if conn is not None and addr1 and addr2:
        codes = expand_beopjungri_codes(
            conn,
            table=table,
            addr1=addr1,
            addr2=addr2,
            addr3=addr3,
            addr3_list=addr3_list,
            addr4_list=addr4_list,
            ri_list=ri_list,
            asset_type=asset_type,
            valid_sql=valid_sql,
        )

    addr_clauses: list[str] = []
    addr_params: dict = {}
    if addr1 and addr2:
        apply_addr2_scope(addr_clauses, addr_params, addr1=addr1, addr2=addr2, col_prefix=col_prefix)
    elif addr1:
        addr_clauses.append(f"{p}addr1 = :addr1")
        addr_params["addr1"] = addr1.strip()
    apply_addr3_filter(addr_clauses, addr_params, addr3, addr3_list or [])
    apply_addr4_filter(addr_clauses, addr_params, None, addr4_list or [])
    apply_ri_filter(addr_clauses, addr_params, ri_list or [])
    if col_prefix:
        addr_clauses = [
            c
            if c.startswith(p) or f"{col_prefix}." in c
            else c.replace("addr", f"{p}addr", 1)
            for c in addr_clauses
        ]

    if codes and addr_clauses:
        params["beopjungri_codes"] = codes
        params.update(addr_params)
        clauses.append(
            f"(({p}beopjungri_code = ANY(:beopjungri_codes)) OR "
            f"({p}beopjungri_code IS NULL AND {' AND '.join(addr_clauses)}))"
        )
    elif codes:
        params["beopjungri_codes"] = codes
        clauses.append(f"{p}beopjungri_code = ANY(:beopjungri_codes)")
    elif addr_clauses:
        params.update(addr_params)
        clauses.extend(addr_clauses)
