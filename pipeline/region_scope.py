"""생활권(권역) 기반 Twin 후보 scope (D-023b Phase 1 · D-029 Phase B).

Twin 후보군을 사람이 하드코딩한 "육상 인접"이 아니라 **생활권(권역)** 으로 묶는다.
Hybrid Twin이 토지·집합·인구·가격 다중 신호로 이미 걸러주므로, scope는
"설명 가능한 Comparable 범위"를 정하는 UX 파라미터 역할만 한다.

scope:
  - adjacent : 앵커 시도 + 육상 인접 시도 (legacy, sido_adjacency 재사용)
  - region   : 앵커가 속한 생활권(권역) 시도 집합 (**기본**)
  - national : 전국 (제한 없음 → None)

권역은 1차로 `region_scope_master` 테이블 SSOT. 없으면 REGION_GROUPS fallback.
"""

from __future__ import annotations

from typing import FrozenSet, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from sido_adjacency import allowed_twin_sidoes

SCOPES = ("adjacent", "region", "national")
DEFAULT_SCOPE = "region"
SCHEME_VERSION = "7region-v1"

# Bootstrap fallback — DB 미적재·조회 실패 시
REGION_GROUPS: dict[str, frozenset[str]] = {
    "수도권": frozenset({"11", "28", "41"}),
    "충청권": frozenset({"30", "36", "43", "44"}),
    "호남권": frozenset({"12", "45", "52", "29", "46"}),
    "대경권": frozenset({"27", "47"}),
    "동남권": frozenset({"26", "31", "48"}),
    "강원권": frozenset({"42", "51"}),
    "제주권": frozenset({"50"}),
}

_SCOPE_ID_BY_LABEL: dict[str, str] = {
    "수도권": "capital",
    "충청권": "chungcheong",
    "호남권": "honam",
    "대경권": "daegyeong",
    "동남권": "dongnam",
    "강원권": "gangwon",
    "제주권": "jeju",
}

_SIDO_TO_REGION: dict[str, str] = {}
for _name, _codes in REGION_GROUPS.items():
    for _c in _codes:
        _SIDO_TO_REGION[_c] = _name

# scope_id → 시도 집합 (런타임 갱신)
_SCOPE_SIDOES: dict[str, frozenset[str]] = {
    _SCOPE_ID_BY_LABEL[name]: codes for name, codes in REGION_GROUPS.items()
}
_SIDO_TO_SCOPE_ID: dict[str, str] = {
    sido: _SCOPE_ID_BY_LABEL[region_name]
    for region_name, codes in REGION_GROUPS.items()
    for sido in codes
}


def _apply_scope_rows(rows: list[dict]) -> None:
    global _SCOPE_SIDOES, _SIDO_TO_SCOPE_ID, _SIDO_TO_REGION
    by_scope: dict[str, set[str]] = {}
    sido_to_scope: dict[str, str] = {}
    sido_to_label: dict[str, str] = {}
    for r in rows:
        sido = str(r["sido_code"]).strip()[:2]
        scope_id = str(r["scope_id"]).strip()
        label = str(r.get("scope_label") or scope_id)
        by_scope.setdefault(scope_id, set()).add(sido)
        sido_to_scope[sido] = scope_id
        sido_to_label[sido] = label
    if not by_scope:
        return
    _SCOPE_SIDOES = {k: frozenset(v) for k, v in by_scope.items()}
    _SIDO_TO_SCOPE_ID = sido_to_scope
    _SIDO_TO_REGION = sido_to_label


def refresh_region_scope_from_db(engine: Engine, *, scheme_version: str = SCHEME_VERSION) -> bool:
    """region_scope_master 로드. 성공 시 True."""
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT to_regclass('public.region_scope_master') IS NOT NULL")
            ).scalar()
            if not exists:
                return False
            rows = conn.execute(
                text(
                    """
                    SELECT sido_code, scope_id, scope_label
                    FROM region_scope_master
                    WHERE scheme_version = :sv
                    """
                ),
                {"sv": scheme_version},
            ).mappings().all()
        if rows:
            _apply_scope_rows([dict(r) for r in rows])
            return True
    except Exception:
        pass
    return False


def ensure_region_scope_master(engine: Engine, *, ddl_path: str | None = None) -> None:
    """DDL 적용 후 테이블에서 scope 갱신 (없으면 fallback 유지)."""
    if ddl_path:
        from db_utils import execute_sql_file

        execute_sql_file(engine, ddl_path)
    refresh_region_scope_from_db(engine)


def region_name_of(sido: str) -> Optional[str]:
    """시도 2자리 → 권역명. 미등록 코드 → None."""
    s = (sido or "").strip()[:2]
    return _SIDO_TO_REGION.get(s)


def region_sidoes(sido: str) -> FrozenSet[str]:
    """앵커가 속한 권역의 시도 집합. 미등록 코드 → 자기 시도 단독."""
    s = (sido or "").strip()[:2]
    scope_id = _SIDO_TO_SCOPE_ID.get(s)
    if scope_id and scope_id in _SCOPE_SIDOES:
        return _SCOPE_SIDOES[scope_id]
    return frozenset({s})


def candidate_scope_sidoes(anchor_sido: str, scope: str) -> Optional[FrozenSet[str]]:
    """scope별 후보 시도 집합. national → None(전국, 제한 없음).

    region/미지정은 권역, adjacent는 육상 인접으로 폴백.
    """
    s = (anchor_sido or "").strip()[:2]
    if scope == "national":
        return None
    if scope == "adjacent":
        return allowed_twin_sidoes(s)
    return region_sidoes(s)
