"""beopjungri_code 집합 scope + addr 텍스트 fallback + 명시 행정코드 scope."""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.built.filters import apply_addr3_filter, apply_addr4_filter, apply_ri_filter
from app.flat_sido_region import apply_addr2_scope, apply_region_asset_type_filter, is_flat_sido_addr2

AdminCodeLevel = Literal["eupmyeondong", "beopjungri"]


def _norm_codes(codes: list[str] | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in codes or []:
        s = str(raw or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def apply_admin_code_scope(
    clauses: list[str],
    params: dict,
    *,
    codes: list[str] | None,
    level: AdminCodeLevel | str | None,
    col_prefix: str = "",
) -> bool:
    """
    명시 행정코드 목록으로 지역 필터.
    True면 적용됨 — addr 기반 apply_region_scope 를 건너뛰면 됨.
    """
    cleaned = _norm_codes(codes)
    if not cleaned:
        return False
    lv = (level or "").strip().lower()
    p = f"{col_prefix}." if col_prefix else ""
    if lv == "eupmyeondong":
        # 8자 emd (+ 레거시 10자 …00)
        emd = []
        for c in cleaned:
            if len(c) >= 10 and c.endswith("00"):
                emd.append(c[:8])
            elif len(c) >= 8:
                emd.append(c[:8])
            else:
                emd.append(c)
        emd = _norm_codes(emd)
        params["admin_region_codes"] = emd
        clauses.append(
            f"(btrim({p}eupmyeondong_code::text) = ANY(:admin_region_codes) "
            f"OR LEFT(btrim(COALESCE({p}beopjungri_code::text, '')), 8) = ANY(:admin_region_codes))"
        )
        return True
    if lv == "beopjungri":
        params["admin_region_codes"] = cleaned
        clauses.append(f"btrim({p}beopjungri_code::text) = ANY(:admin_region_codes)")
        return True
    return False


def parse_region_addr_keys(raw: list[str] | None) -> list[tuple[str, str, str]]:
    """'시도|시군구|읍면동' 형식 → triples."""
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for item in raw or []:
        s = str(item or "").strip()
        if not s or s in seen:
            continue
        parts = [p.strip() for p in s.split("|")]
        if len(parts) < 3:
            continue
        a1, a2, leaf = parts[0], parts[1], parts[2]
        if not (a1 and a2 and leaf):
            continue
        key = f"{a1}|{a2}|{leaf}"
        if key in seen:
            continue
        seen.add(key)
        out.append((a1, a2, leaf))
    return out


def _leaf_name_variants(leaf: str) -> list[str]:
    """면↔읍 승격 표기 (대소면 ↔ 대소읍)."""
    s = (leaf or "").strip()
    if not s:
        return []
    out = [s]
    if s.endswith("읍") and len(s) >= 2:
        alt = s[:-1] + "면"
        if alt not in out:
            out.append(alt)
    elif s.endswith("면") and len(s) >= 2:
        alt = s[:-1] + "읍"
        if alt not in out:
            out.append(alt)
    return out


def apply_analysis_region_scope(
    clauses: list[str],
    params: dict,
    *,
    codes: list[str] | None = None,
    code_level: AdminCodeLevel | str | None = None,
    addr_keys: list[str] | None = None,
    col_prefix: str = "",
) -> bool:
    """
    교차 시군구 분석 scope.
    - 행정코드 매칭 (매핑된 행)
    - addr1|addr2|leaf 이름 매칭 (코드 NULL 행 포함, 예: 음성 대소읍)
    둘 다 있으면 OR.
    """
    p = f"{col_prefix}." if col_prefix else ""
    parts: list[str] = []

    cleaned = _norm_codes(codes)
    lv = (code_level or "eupmyeondong").strip().lower()
    if cleaned:
        if lv == "beopjungri":
            params["admin_region_codes"] = cleaned
            parts.append(f"btrim({p}beopjungri_code::text) = ANY(:admin_region_codes)")
        else:
            emd = []
            for c in cleaned:
                if len(c) >= 10 and c.endswith("00"):
                    emd.append(c[:8])
                elif len(c) >= 8:
                    emd.append(c[:8])
                else:
                    emd.append(c)
            emd = _norm_codes(emd)
            params["admin_region_codes"] = emd
            parts.append(
                f"(btrim({p}eupmyeondong_code::text) = ANY(:admin_region_codes) "
                f"OR LEFT(btrim(COALESCE({p}beopjungri_code::text, '')), 8) = ANY(:admin_region_codes))"
            )

    triples = parse_region_addr_keys(addr_keys)
    for i, (a1, a2, leaf) in enumerate(triples):
        params[f"ru_a1_{i}"] = a1
        params[f"ru_a2_{i}"] = a2
        leaf_vars = _leaf_name_variants(leaf)
        params[f"ru_leaves_{i}"] = leaf_vars
        parts.append(
            f"({p}addr1 = :ru_a1_{i} AND {p}addr2 = :ru_a2_{i} "
            f"AND ({p}addr3 = ANY(:ru_leaves_{i}) OR {p}addr4 = ANY(:ru_leaves_{i})))"
        )

    if not parts:
        return False
    clauses.append("(" + " OR ".join(parts) + ")")
    return True


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
    apply_region_asset_type_filter(clauses, params, asset_type, col_prefix="t")

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
