"""시군구(addr2) 없이 시도 → 읍·면·동(addr3)만 있는 주소 계층 (세종특별자치시 등)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

# API·프론트 공통 토큰 — DB에 저장되지 않음.
FLAT_SIDO_ADDR2_TOKEN = "__FLAT_SIDO__"


def is_flat_sido_addr2(addr2: str | None) -> bool:
    return (addr2 or "").strip() == FLAT_SIDO_ADDR2_TOKEN


def flat_sido_addr2_sql(prefix: str = "") -> str:
    col = f"{prefix}.addr2" if prefix else "addr2"
    return f"({col} IS NULL OR btrim({col}::text) = '')"


def apply_addr2_scope(
    clauses: list[str],
    params: dict,
    *,
    addr1: str | None,
    addr2: str | None,
    col_prefix: str = "",
) -> None:
    """addr2 선택 시 addr1 + (일반 시군구 또는 flat sido) 조건 추가."""
    if not addr2:
        return
    a1 = (addr1 or "").strip()
    if not a1:
        return
    p = f"{col_prefix}." if col_prefix else ""
    params["addr1"] = a1
    clauses.append(f"{p}addr1 = :addr1")
    if is_flat_sido_addr2(addr2):
        clauses.append(flat_sido_addr2_sql(col_prefix))
    else:
        params["addr2"] = addr2.strip()
        clauses.append(f"{p}addr2 = :addr2")


def _table_has_flat_sido(
    conn: Connection,
    *,
    table: str,
    addr1: str,
    asset_type: str | None = None,
    valid_sql: str = "TRUE",
) -> bool:
    clauses = [
        "addr1 = :a1",
        flat_sido_addr2_sql(),
        "addr3 IS NOT NULL",
        "btrim(addr3::text) <> ''",
        valid_sql,
    ]
    params: dict = {"a1": addr1.strip()}
    if asset_type:
        clauses.append("asset_type = :asset_type")
        params["asset_type"] = asset_type
    n = conn.execute(
        text(f"SELECT COUNT(*)::int FROM {table} WHERE {' AND '.join(clauses)}"),
        params,
    ).scalar()
    return int(n or 0) > 0


def list_addr2_for_sido(
    conn: Connection,
    *,
    table: str,
    addr1: str,
    asset_type: str | None = None,
    valid_sql: str = "TRUE",
) -> list[str]:
    """DISTINCT addr2; flat sido 이면 synthetic 토큰 1개 반환."""
    clauses = [
        "addr1 = :a1",
        "addr2 IS NOT NULL",
        "btrim(addr2::text) <> ''",
        valid_sql,
    ]
    params: dict = {"a1": addr1.strip()}
    if asset_type:
        clauses.append("asset_type = :asset_type")
        params["asset_type"] = asset_type
    rows = conn.execute(
        text(
            f"""
            SELECT DISTINCT btrim(addr2::text) AS v
            FROM {table}
            WHERE {' AND '.join(clauses)}
            ORDER BY 1
            """
        ),
        params,
    ).fetchall()
    if rows:
        return [str(r.v).strip() for r in rows if r.v]
    if _table_has_flat_sido(
        conn, table=table, addr1=addr1, asset_type=asset_type, valid_sql=valid_sql
    ):
        return [FLAT_SIDO_ADDR2_TOKEN]
    return []


def region_scope_clauses(
    *,
    addr1: str,
    addr2: str,
    asset_type: str | None = None,
    valid_sql: str = "is_valid = true",
) -> tuple[list[str], dict]:
    """지역 목록 API용 addr1+addr2(+asset_type) WHERE 조각."""
    clauses = [valid_sql]
    params: dict = {}
    if asset_type:
        clauses.append("asset_type = :asset_type")
        params["asset_type"] = asset_type
    apply_addr2_scope(clauses, params, addr1=addr1, addr2=addr2)
    return clauses, params


def detect_region_structure_for_table(
    conn: Connection,
    *,
    table: str,
    addr1: str,
    addr2: str,
    asset_type: str | None = None,
    valid_sql: str = "is_valid = true",
) -> dict:
    """청주·수원(구→동) vs flat sido·일반(읍면동=addr3) 패턴."""
    clauses = ["addr1 = :a1", valid_sql]
    params: dict = {"a1": addr1.strip()}
    if is_flat_sido_addr2(addr2):
        clauses.append(flat_sido_addr2_sql())
    else:
        clauses.append("addr2 = :a2")
        params["a2"] = addr2.strip()
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
            FROM {table}
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
