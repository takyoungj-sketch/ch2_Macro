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
