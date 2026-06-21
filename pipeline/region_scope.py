"""생활권(권역) 기반 Twin 후보 scope (D-023b Phase 1).

Twin 후보군을 사람이 하드코딩한 "육상 인접"이 아니라 **생활권(권역)** 으로 묶는다.
Hybrid Twin이 토지·집합·인구·가격 다중 신호로 이미 걸러주므로, scope는
"설명 가능한 Comparable 범위"를 정하는 UX 파라미터 역할만 한다.

scope:
  - adjacent : 앵커 시도 + 육상 인접 시도 (legacy, sido_adjacency 재사용)
  - region   : 앵커가 속한 생활권(권역) 시도 집합 (**기본**)
  - national : 전국 (제한 없음 → None)

권역은 1차로 손정의(행정 시도 기반). 장기적으로는 실제 Twin 연결 그래프에서
생활권 클러스터를 오프라인 재도출해 승격할 수 있다(순환 회피 위해 라이브 대체는 보류).

특별자치 코드 호환: 강원특별(51)→강원권, 전북특별(52)→호남권, 세종(36)→충청권.
"""

from __future__ import annotations

from typing import FrozenSet, Optional

from sido_adjacency import allowed_twin_sidoes

SCOPES = ("adjacent", "region", "national")
DEFAULT_SCOPE = "region"

# 생활권(권역) → 행정 시도(2자리) 집합
REGION_GROUPS: dict[str, frozenset[str]] = {
    "수도권": frozenset({"11", "28", "41"}),  # 서울·인천·경기 (서울↔인천 단절 해결)
    "충청권": frozenset({"30", "36", "43", "44"}),  # 대전·세종·충북·충남
    "호남권": frozenset({"29", "45", "46", "52"}),  # 광주·전북·전남(+전북특별)
    "대경권": frozenset({"27", "47"}),  # 대구·경북
    "동남권": frozenset({"26", "31", "48"}),  # 부산·울산·경남
    "강원권": frozenset({"42", "51"}),  # 강원(+강원특별)
    "제주권": frozenset({"50"}),  # 제주
}

_SIDO_TO_REGION: dict[str, str] = {}
for _name, _codes in REGION_GROUPS.items():
    for _c in _codes:
        _SIDO_TO_REGION[_c] = _name


def region_name_of(sido: str) -> Optional[str]:
    """시도 2자리 → 권역명. 미등록 코드 → None."""
    s = (sido or "").strip()[:2]
    return _SIDO_TO_REGION.get(s)


def region_sidoes(sido: str) -> FrozenSet[str]:
    """앵커가 속한 권역의 시도 집합. 미등록 코드 → 자기 시도 단독."""
    name = region_name_of(sido)
    if name is None:
        return frozenset({(sido or "").strip()[:2]})
    return REGION_GROUPS[name]


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
