"""시도(addr1) 목록 SSOT — region_codes 기준 (원장 DISTINCT 스캔 회피)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.collective.meta_cache import get_ttl_cached

_CACHE_KEY = "ssot:sido_names"
_CACHE_TTL_SEC = 3600.0

# 2026-07-01 전남광주 통합 — region_codes·UI 선택에서 제외 (원장 addr1 레거시 문자열은 별도)
RETIRED_SIDO_CODES = frozenset({"29", "46"})
RETIRED_SIDO_NAMES = frozenset({"광주광역시", "전라남도"})


def is_retired_sido_code(code: str | None) -> bool:
    return (code or "").strip() in RETIRED_SIDO_CODES


def is_retired_sido_name(name: str | None) -> bool:
    return (name or "").strip() in RETIRED_SIDO_NAMES


def filter_active_sido_names(names: list[str]) -> list[str]:
    return [n for n in names if not is_retired_sido_name(n)]


def _canonical_sido_sql(p: str) -> str:
    from app.region_canonical import canonical_prefix_coalesce_sql  # noqa: PLC0415

    return canonical_prefix_coalesce_sql(
        f"{p}beopjungri_code", f"{p}eupmyeondong_code", f"{p}sigungu_code", f"{p}sido_code", 2
    )


def _retired_rows_canonical_sido(conn: Connection, table: str) -> dict[str, list[str]]:
    """원장에 남은 레거시 시도명 행 → {canonical 시도코드: [레거시 addr1]}. 1시간 TTL.

    레거시 addr1(``RETIRED_SIDO_NAMES``)과 현행 시도의 연결은 **이름 별칭이 아니라 행의
    행정코드**(region_code_history 경유 ``canonical_prefix_coalesce_sql``)로 판정한다.
    원장 addr1 은 UPDATE 하지 않는다 (B-02).
    """

    def _load() -> dict[str, list[str]]:
        names = sorted(RETIRED_SIDO_NAMES)
        binds = ", ".join(f":rn{i}" for i in range(len(names)))
        try:
            if not conn.execute(text("SELECT to_regclass('public.region_code_history')")).scalar():
                return {}
            # 실패해도 바깥 트랜잭션을 깨지 않도록 savepoint 안에서 조회
            with conn.begin_nested():
                rows = conn.execute(
                    text(
                        f"""
                        SELECT DISTINCT btrim(addr1::text) AS a1,
                               ({_canonical_sido_sql('')}) AS sido
                        FROM {table}
                        WHERE addr1 IN ({binds})
                        """
                    ),
                    {f"rn{i}": n for i, n in enumerate(names)},
                ).fetchall()
        except Exception:
            return {}
        out: dict[str, set[str]] = {}
        for r in rows:
            if r.a1 and r.sido:
                out.setdefault(str(r.sido).strip(), set()).add(str(r.a1).strip())
        return {k: sorted(v) for k, v in out.items()}

    return get_ttl_cached(f"ssot:retired_sido_rows:{table}", _load, ttl_sec=_CACHE_TTL_SEC)


def active_sido_code(conn: Connection, name: str) -> str | None:
    """활성 region_codes 시도명 → 2자리 코드. 1시간 TTL."""
    a1 = (name or "").strip()
    if not a1:
        return None

    def _load() -> str | None:
        try:
            row = conn.execute(
                text(
                    """
                    SELECT btrim(sido_code::text) AS code
                    FROM region_codes
                    WHERE COALESCE(is_active, true)
                      AND btrim(sido_name::text) = :a1
                      AND sido_code IS NOT NULL
                    ORDER BY sido_code
                    LIMIT 1
                    """
                ),
                {"a1": a1},
            ).first()
        except Exception:
            return None
        return str(row.code).strip() if row and row.code else None

    return get_ttl_cached(f"ssot:active_sido_code:{a1}", _load, ttl_sec=_CACHE_TTL_SEC)


def legacy_sido_names_for(
    conn: Connection | None, *, table: str, addr1: str | None
) -> tuple[str | None, list[str]]:
    """현행 시도 addr1 에 행정코드로 연결되는 레거시 시도명 (없으면 빈 목록)."""
    a1 = (addr1 or "").strip()
    if conn is None or not a1 or is_retired_sido_name(a1):
        return None, []
    code = active_sido_code(conn, a1)
    if not code:
        return None, []
    legacy = [n for n in _retired_rows_canonical_sido(conn, table).get(code, []) if n != a1]
    return code, legacy


def addr1_scope_sql(
    conn: Connection | None,
    params: dict,
    *,
    addr1: str,
    table: str,
    col_prefix: str = "",
    key: str = "addr1",
) -> str:
    """시도(addr1) 조건 — 현행 시도면 같은 canonical 시도코드의 레거시 시도명 행도 포함.

    - 옛 이름 단독 조회(``addr1=광주광역시``)는 기존과 동일한 ``addr1 = :addr1``.
    - 현행 시도(``전남광주통합특별시``)는 ``addr1 IN (레거시)`` **이면서** 행 코드의
      canonical 시도가 일치하는 행만 추가한다. 레거시 행이 없는 시도는 기존 조건 그대로.
    """
    p = f"{col_prefix}." if col_prefix else ""
    a1 = (addr1 or "").strip()
    params[key] = a1
    base = f"{p}addr1 = :{key}"
    code, legacy = legacy_sido_names_for(conn, table=table, addr1=a1)
    if not code or not legacy:
        return base
    binds = []
    for i, n in enumerate(legacy):
        k = f"{key}_legacy{i}"
        params[k] = n
        binds.append(f":{k}")
    params[f"{key}_sido"] = code
    return (
        f"({base} OR ({p}addr1 IN ({', '.join(binds)}) "
        f"AND ({_canonical_sido_sql(p)}) = :{key}_sido))"
    )


def list_sido_names(conn: Connection) -> list[str]:
    """활성 region_codes 에서 시도명 목록 (sido_code 순)."""

    def _load() -> list[str]:
        rows = conn.execute(
            text(
                """
                SELECT sido_name
                FROM (
                    SELECT DISTINCT ON (sido_code)
                           sido_code,
                           btrim(sido_name::text) AS sido_name
                    FROM region_codes
                    WHERE COALESCE(is_active, true)
                      AND sido_name IS NOT NULL
                      AND btrim(sido_name::text) <> ''
                    ORDER BY sido_code, sido_name
                ) sub
                ORDER BY sido_code
                """
            )
        ).fetchall()
        return filter_active_sido_names([str(r.sido_name) for r in rows if r.sido_name])

    return get_ttl_cached(_CACHE_KEY, _load, ttl_sec=_CACHE_TTL_SEC)
