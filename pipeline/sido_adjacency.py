"""
행안부 법정 시도 코드(앞 2자리) 기준 **육상 인접** 근사 맵.

Twin Region 읍면동 후보는 `allowed_twin_sidoes(앵커_시도)` 에 포함된 시도에 한정한다.
제주(50)는 육상 이웃 시도가 없어 **같은 제주(50) 내** 읍면동만 후보가 된다.

표에 없는 시도 코드는 **해당 시도 단독**(자기 시도만)으로 폴백한다.
전북특별자치(52)·강원특별자치(51) 등은 각각 45·42와 동일 인접으로 둔다(데이터 코드 호환).
"""

from __future__ import annotations

from typing import FrozenSet

# 양방향으로 점검된 대표 인접 (누락 시 allowed_twin_sidoes 가 보수적으로 동작)
_SIDO_ADJ: dict[str, frozenset[str]] = {
    "11": frozenset({"41"}),  # 서울
    "26": frozenset({"31", "48"}),  # 부산
    "27": frozenset({"47"}),  # 대구
    "28": frozenset({"41"}),  # 인천
    "29": frozenset({"46"}),  # 광주
    "30": frozenset({"36", "43", "44"}),  # 대전
    "31": frozenset({"26", "47", "48"}),  # 울산
    "36": frozenset({"30", "43", "44"}),  # 세종
    "41": frozenset({"11", "28", "42", "43", "44", "47"}),  # 경기
    "42": frozenset({"41", "43", "47"}),  # 강원
    "43": frozenset({"30", "36", "41", "42", "44", "47"}),  # 충북
    "44": frozenset({"30", "36", "41", "43", "45", "46", "47"}),  # 충남
    "45": frozenset({"43", "44", "46", "47"}),  # 전북
    "46": frozenset({"29", "44", "45", "48"}),  # 전남
    "47": frozenset({"27", "31", "41", "42", "43", "44", "45", "48"}),  # 경북
    "48": frozenset({"26", "31", "46", "47"}),  # 경남
    "50": frozenset(),  # 제주 — 육상 이웃 없음
}

for _alias, _base in (("52", "45"), ("51", "42")):
    if _base in _SIDO_ADJ:
        _SIDO_ADJ[_alias] = _SIDO_ADJ[_base]


def allowed_twin_sidoes(anchor_sido: str) -> FrozenSet[str]:
    """앵커 시도 + 육상 인접 시도 집합(2자리 문자열)."""
    s = (anchor_sido or "").strip()
    if len(s) >= 2:
        s = s[:2]
    n = _SIDO_ADJ.get(s)
    if n is None:
        return frozenset({s})
    return n | frozenset({s})
