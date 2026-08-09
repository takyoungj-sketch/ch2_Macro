"""beopjungri_code 집합 scope + addr 텍스트 fallback + 명시 행정코드 scope."""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.built.filters import apply_addr3_filter, apply_addr4_filter, apply_ri_filter
from app.flat_sido_region import apply_addr2_scope, apply_region_asset_type_filter, flat_sido_addr2_sql, is_flat_sido_addr2

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


def _eupmyeondong_ledger_emd_codes(
    conn: Connection | None,
    canonical_codes: list[str],
) -> list[str]:
    """canonical eup(8자) → ledger 조회용 8자 prefix 집합 (historical 포함)."""
    cleaned = _norm_codes(canonical_codes)
    if not cleaned:
        return []
    ledger = list(cleaned)
    if conn is not None:
        from app.region_canonical import expand_to_ledger_codes

        ledger = expand_to_ledger_codes(conn, cleaned) or cleaned
    emd: set[str] = set()
    for c in ledger:
        cc = str(c).strip()
        if len(cc) >= 8:
            emd.add(cc[:8])
        elif cc:
            emd.add(cc)
    for c in cleaned:
        if len(c) >= 8:
            emd.add(c[:8])
    return _norm_codes(emd)


def apply_admin_code_scope(
    clauses: list[str],
    params: dict,
    *,
    codes: list[str] | None,
    level: AdminCodeLevel | str | None,
    col_prefix: str = "",
    conn: Connection | None = None,
) -> bool:
    """
    명시 행정코드 목록으로 지역 필터.
    True면 적용됨 — addr 기반 apply_region_scope 를 건너뛰면 됨.
    beopjungri: GIS/canonical 입력을 원장 historical 코드로 expand (D-028).
    """
    cleaned = _norm_codes(codes)
    if not cleaned:
        return False
    lv = (level or "").strip().lower()
    p = f"{col_prefix}." if col_prefix else ""
    if lv == "eupmyeondong":
        emd = _eupmyeondong_ledger_emd_codes(conn, cleaned)
        if not emd:
            return False
        params["admin_region_codes"] = emd
        clauses.append(
            f"(btrim({p}eupmyeondong_code::text) = ANY(:admin_region_codes) "
            f"OR LEFT(btrim(COALESCE({p}beopjungri_code::text, '')), 8) = ANY(:admin_region_codes))"
        )
        return True
    if lv == "beopjungri":
        ledger = cleaned
        if conn is not None:
            from app.region_canonical import expand_to_ledger_codes

            ledger = expand_to_ledger_codes(conn, cleaned) or cleaned
        params["admin_region_codes"] = ledger
        # NULL beopjungri 원장(예: 음성 수태리)은 코드 컬럼만으로 못 잡음 →
        # active region_codes 명칭(addr5)으로도 매칭
        clauses.append(
            f"("
            f"btrim({p}beopjungri_code::text) = ANY(:admin_region_codes)"
            f" OR EXISTS ("
            f"  SELECT 1 FROM region_codes _rc_bri"
            f"  WHERE COALESCE(_rc_bri.is_active, TRUE)"
            f"    AND btrim(_rc_bri.beopjungri_code::text) = ANY(:admin_region_codes)"
            f"    AND btrim({p}addr1::text) = btrim(_rc_bri.sido_name::text)"
            f"    AND btrim({p}addr2::text) = btrim(_rc_bri.sigungu_name::text)"
            f"    AND btrim(COALESCE({p}addr5::text, '')) = btrim(_rc_bri.beopjungri_name::text)"
            f")"
            f")"
        )
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
    conn: Connection | None = None,
    emd_code_col: str | None = "eupmyeondong_code",
) -> bool:
    """
    교차 시군구 분석 scope.
    - 행정코드 매칭 (매핑된 행)
    - addr1|addr2|leaf 이름 매칭 (코드 NULL 행 포함, 예: 음성 대소읍)
    둘 다 있으면 OR.
    beopjungri 코드는 canonical → ledger expand (D-028).
    """
    p = f"{col_prefix}." if col_prefix else ""
    parts: list[str] = []

    cleaned = _norm_codes(codes)
    lv = (code_level or "eupmyeondong").strip().lower()
    if cleaned:
        if lv == "beopjungri":
            ledger = cleaned
            if conn is not None:
                from app.region_canonical import expand_to_ledger_codes

                ledger = expand_to_ledger_codes(conn, cleaned) or cleaned
            params["admin_region_codes"] = ledger
            parts.append(
                f"("
                f"btrim({p}beopjungri_code::text) = ANY(:admin_region_codes)"
                f" OR EXISTS ("
                f"  SELECT 1 FROM region_codes _rc_bri"
                f"  WHERE COALESCE(_rc_bri.is_active, TRUE)"
                f"    AND btrim(_rc_bri.beopjungri_code::text) = ANY(:admin_region_codes)"
                f"    AND btrim({p}addr1::text) = btrim(_rc_bri.sido_name::text)"
                f"    AND btrim({p}addr2::text) = btrim(_rc_bri.sigungu_name::text)"
                f"    AND btrim(COALESCE({p}addr5::text, '')) = btrim(_rc_bri.beopjungri_name::text)"
                f")"
                f")"
            )
        else:
            emd = _eupmyeondong_ledger_emd_codes(conn, cleaned)
            if emd:
                params["admin_region_codes"] = emd
                emd_clause = (
                    f" OR btrim(COALESCE({p}{emd_code_col}::text, '')) = ANY(:admin_region_codes)"
                    if emd_code_col
                    else ""
                )
                parts.append(
                    f"(LEFT(btrim(COALESCE({p}beopjungri_code::text, '')), 8) = ANY(:admin_region_codes)"
                    f"{emd_clause})"
                )

    triples = parse_region_addr_keys(addr_keys)
    for i, (a1, a2, leaf) in enumerate(triples):
        params[f"ru_a1_{i}"] = a1
        leaf_vars = _leaf_name_variants(leaf)
        params[f"ru_leaves_{i}"] = leaf_vars
        if is_flat_sido_addr2(a2):
            addr2_clause = flat_sido_addr2_sql(col_prefix.rstrip(".") if col_prefix else "")
        else:
            params[f"ru_a2_{i}"] = a2
            addr2_clause = f"{p}addr2 = :ru_a2_{i}"
        # 읍면동=addr3/addr4, 리=addr5 (Built NULL-code 리 행)
        parts.append(
            f"({p}addr1 = :ru_a1_{i} AND {addr2_clause} "
            f"AND ({p}addr3 = ANY(:ru_leaves_{i}) OR {p}addr4 = ANY(:ru_leaves_{i}) "
            f"OR {p}addr5 = ANY(:ru_leaves_{i})))"
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
