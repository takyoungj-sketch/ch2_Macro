"""지도 인접 추가 — region_codes 마스터로 VWorld 코드 ↔ 명칭 정합."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection


def lookup_region_code(
    conn: Connection,
    *,
    code: str | None = None,
    addr1: str | None = None,
    addr2: str | None = None,
    leaf: str | None = None,
    level: str = "eupmyeondong",
    eup: str | None = None,
) -> dict[str, Any]:
    lv = (level or "eupmyeondong").strip().lower()
    raw = (code or "").strip()
    a1 = (addr1 or "").strip()
    a2 = (addr2 or "").strip()
    name = (leaf or "").strip()
    eup_name = (eup or "").strip()

    row = None
    if raw:
        if lv == "beopjungri":
            row = conn.execute(
                text(
                    """
                    SELECT btrim(beopjungri_code::text) AS code,
                           sido_name AS addr1, sigungu_name AS addr2,
                           beopjungri_name AS leaf
                    FROM region_codes
                    WHERE COALESCE(is_active, TRUE)
                      AND (
                        btrim(beopjungri_code::text) = :c
                        OR btrim(beopjungri_code::text) = :c10
                      )
                    ORDER BY is_active DESC
                    LIMIT 1
                    """
                ),
                {"c": raw, "c10": raw[:10] if len(raw) >= 10 else raw.ljust(10, "0")[:10]},
            ).mappings().first()
        else:
            emd = raw[:8] if len(raw) >= 8 else raw
            row = conn.execute(
                text(
                    """
                    SELECT btrim(eupmyeondong_code::text) AS code,
                           sido_name AS addr1, sigungu_name AS addr2,
                           eupmyeondong_name AS leaf
                    FROM region_codes
                    WHERE COALESCE(is_active, TRUE)
                      AND (
                        btrim(eupmyeondong_code::text) = :emd
                        OR LEFT(btrim(beopjungri_code::text), 8) = :emd
                      )
                    ORDER BY is_active DESC
                    LIMIT 1
                    """
                ),
                {"emd": emd},
            ).mappings().first()

    if row is None and a1 and name:
        if lv == "beopjungri":
            params: dict[str, Any] = {"a1": a1, "leaf": name}
            extra = ""
            if a2:
                extra += " AND btrim(sigungu_name::text) = :a2"
                params["a2"] = a2
            if eup_name:
                extra += " AND btrim(eupmyeondong_name::text) = :eup"
                params["eup"] = eup_name
            row = conn.execute(
                text(
                    f"""
                    SELECT btrim(beopjungri_code::text) AS code,
                           sido_name AS addr1, sigungu_name AS addr2,
                           beopjungri_name AS leaf
                    FROM region_codes
                    WHERE COALESCE(is_active, TRUE)
                      AND btrim(sido_name::text) = :a1
                      AND btrim(beopjungri_name::text) = :leaf
                      {extra}
                    ORDER BY is_active DESC
                    LIMIT 1
                    """
                ),
                params,
            ).mappings().first()
        else:
            params = {"a1": a1, "leaf": name}
            extra = ""
            if a2:
                extra += " AND btrim(sigungu_name::text) = :a2"
                params["a2"] = a2
            row = conn.execute(
                text(
                    f"""
                    SELECT btrim(eupmyeondong_code::text) AS code,
                           sido_name AS addr1, sigungu_name AS addr2,
                           eupmyeondong_name AS leaf
                    FROM region_codes
                    WHERE COALESCE(is_active, TRUE)
                      AND btrim(sido_name::text) = :a1
                      AND btrim(eupmyeondong_name::text) = :leaf
                      {extra}
                    ORDER BY is_active DESC
                    LIMIT 1
                    """
                ),
                params,
            ).mappings().first()

    if not row:
        return {
            "code": raw or None,
            "level": lv,
            "addr1": a1 or None,
            "addr2": a2 or None,
            "leaf": name or None,
        }
    return {
        "code": (str(row["code"]).strip() if row.get("code") else raw) or None,
        "level": lv,
        "addr1": (str(row["addr1"]).strip() if row.get("addr1") else a1) or None,
        "addr2": (str(row["addr2"]).strip() if row.get("addr2") else a2) or None,
        "leaf": (str(row["leaf"]).strip() if row.get("leaf") else name) or None,
    }
