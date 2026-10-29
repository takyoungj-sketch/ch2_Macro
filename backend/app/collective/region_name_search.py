"""읍·면·동 이름 검색. region_codes에서 읽고, 시군구 토큰은 집합 지역 목록과 맞춘다."""

from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.flat_sido_region import FLAT_SIDO_ADDR2_TOKEN, list_addr2_for_sido
from app.region_sido import is_retired_sido_name


class RegionNameHit(BaseModel):
    addr1: str
    addr2: str
    gu: str = ""
    leaf: str
    label: str


def map_sigungu_to_addr2(sigungu: str, sido: str, tokens: list[str]) -> tuple[str, str]:
    """region_codes 시군구명을 화면의 addr2와 구 이름으로 나눈다."""
    name = (sigungu or "").strip()
    token_set = [t for t in tokens if (t or "").strip()]
    if FLAT_SIDO_ADDR2_TOKEN in token_set and (not name or name == (sido or "").strip()):
        return FLAT_SIDO_ADDR2_TOKEN, ""
    if name in token_set:
        return name, ""
    prefixed = [t for t in token_set if name.startswith(t + " ")]
    if prefixed:
        token = max(prefixed, key=len)
        return token, name[len(token) :].strip()
    if name:
        return name, ""
    if FLAT_SIDO_ADDR2_TOKEN in token_set:
        return FLAT_SIDO_ADDR2_TOKEN, ""
    return name, ""


def search_region_names(
    conn: Connection,
    query: str,
    *,
    table: str,
    asset_type: str | None = None,
    limit: int = 25,
) -> list[dict[str, str]]:
    q = " ".join((query or "").split())
    if len(q) < 2:
        return []
    safe = q.replace("\\", "").replace("%", "").replace("_", "")
    if len(safe) < 2:
        return []
    rows = conn.execute(
        text(
            """
            SELECT sido, sigungu, eup
            FROM (
                SELECT DISTINCT
                    btrim(sido_name::text) AS sido,
                    btrim(sigungu_name::text) AS sigungu,
                    btrim(eupmyeondong_name::text) AS eup
                FROM region_codes
                WHERE COALESCE(is_active, TRUE)
                  AND btrim(COALESCE(eupmyeondong_name::text, '')) <> ''
                  AND (
                    btrim(eupmyeondong_name::text) LIKE :pat
                    OR btrim(sigungu_name::text) LIKE :pat
                    OR btrim(sido_name::text) LIKE :pat
                  )
            ) names
            ORDER BY
                CASE WHEN eup = :exact THEN 0 ELSE 1 END,
                CASE WHEN eup LIKE :prefix THEN 0 ELSE 1 END,
                sido, sigungu, eup
            LIMIT :lim
            """
        ),
        {"pat": f"%{safe}%", "exact": safe, "prefix": f"{safe}%", "lim": int(limit)},
    ).mappings().all()
    token_cache: dict[str, list[str]] = {}
    out: list[dict[str, str]] = []
    for row in rows:
        sido = str(row["sido"] or "").strip()
        if not sido or is_retired_sido_name(sido):
            continue
        sigungu = str(row["sigungu"] or "").strip()
        eup = str(row["eup"] or "").strip()
        if sido not in token_cache:
            token_cache[sido] = list_addr2_for_sido(
                conn,
                table=table,
                addr1=sido,
                asset_type=asset_type,
                valid_sql="is_valid = true",
            )
        addr2, gu = map_sigungu_to_addr2(sigungu, sido, token_cache[sido])
        place = " ".join(part for part in (sido, sigungu, eup) if part)
        out.append(
            {
                "addr1": sido,
                "addr2": addr2,
                "gu": gu,
                "leaf": eup,
                "label": place,
            }
        )
    return out
