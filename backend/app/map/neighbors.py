"""region_neighbors 조회 (Selection SSOT)."""

from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

_LOG = logging.getLogger(__name__)

_VALID_LEVELS = frozenset({"eupmyeondong", "beopjungri"})


def normalize_neighbor_level(level: str) -> str:
    lv = (level or "").strip().lower()
    if lv == "beopjungri":
        return "beopjungri"
    if lv in ("eupmyeondong", "emd"):
        return "eupmyeondong"
    raise ValueError(f"unsupported neighbor level: {level}")


def canonicalize_code_for_level(level: str, code: str) -> str:
    """읍면동 그래프는 8자리 emd 기준 (…00 → 8자)."""
    c = (code or "").strip()
    lv = normalize_neighbor_level(level)
    if lv == "eupmyeondong":
        if len(c) >= 10 and c.endswith("00"):
            return c[:8]
        if len(c) >= 8:
            return c[:8]
    return c


def fetch_neighbor_codes(
    db: Session,
    *,
    level: str,
    codes: Iterable[str],
) -> dict[str, list[str]]:
    """
    각 코드 → neighbor 목록.
    테이블이 없거나 비어 있으면 빈 dict에 가깝게 반환.
    """
    lv = normalize_neighbor_level(level)
    canon = []
    seen: set[str] = set()
    for raw in codes:
        c = canonicalize_code_for_level(lv, str(raw))
        if c and c not in seen:
            seen.add(c)
            canon.append(c)
    if not canon:
        return {}

    try:
        stmt = text(
            """
            SELECT code, neighbor_code
            FROM region_neighbors
            WHERE level = :level
              AND code IN :codes
            ORDER BY code, neighbor_code
            """
        ).bindparams(bindparam("codes", expanding=True))
        rows = db.execute(stmt, {"level": lv, "codes": canon}).mappings().all()
    except Exception as exc:
        _LOG.warning("region_neighbors query failed: %s", exc)
        return {c: [] for c in canon}

    out: dict[str, list[str]] = {c: [] for c in canon}
    for row in rows:
        code = str(row["code"])
        nb = str(row["neighbor_code"])
        out.setdefault(code, []).append(nb)
    return out


def union_neighbor_codes(
    db: Session,
    *,
    level: str,
    codes: Iterable[str],
) -> list[str]:
    """선택 집합의 이웃 합집합 (선택 자신 제외)."""
    by_code = fetch_neighbor_codes(db, level=level, codes=codes)
    selected = {canonicalize_code_for_level(level, str(c)) for c in codes if str(c).strip()}
    union: set[str] = set()
    for nbs in by_code.values():
        union.update(nbs)
    union -= selected
    return sorted(union)


def neighbor_edge_count(db: Session, *, level: str | None = None) -> int:
    try:
        if level:
            lv = normalize_neighbor_level(level)
            row = db.execute(
                text("SELECT COUNT(*) AS n FROM region_neighbors WHERE level = :level"),
                {"level": lv},
            ).mappings().first()
        else:
            row = db.execute(text("SELECT COUNT(*) AS n FROM region_neighbors")).mappings().first()
        return int(row["n"]) if row else 0
    except Exception:
        return 0
