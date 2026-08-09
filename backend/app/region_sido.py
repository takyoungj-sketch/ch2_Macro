"""시도(addr1) 목록 SSOT — region_codes 기준 (원장 DISTINCT 스캔 회피)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.collective.meta_cache import get_ttl_cached

_CACHE_KEY = "ssot:sido_names"
_CACHE_TTL_SEC = 3600.0


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
        return [str(r.sido_name) for r in rows if r.sido_name]

    return get_ttl_cached(_CACHE_KEY, _load, ttl_sec=_CACHE_TTL_SEC)
