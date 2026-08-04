"""Twin Pooling 인접성(시도 레벨) hard gate.

SSOT: `pipeline/sido_adjacency.py` — 이 표는 그 파일의 값 복제본이다. backend는
pipeline 패키지를 import하지 않는 관례(배포·의존성 경계 분리)를 따르므로 별도로
유지한다. **표를 바꾸면 두 파일을 함께 수정한다.**

Twin 후보(v21)는 이미 candidate scope에서 이 표와 동일한 시도 인접 규칙으로
좁혀져 생성되므로, 여기서의 재검증은 "이상치 방어용 안전장치"에 가깝다 — GIS
경계(위상 그래프 `region_neighbors`) 기준의 엄격한 인접이 아니라 "같은 권역
(인접 시도)"이라는 느슨한 기준을 쓴다. 엄격한 읍면동/법정리 경계 인접을
기준으로 하면 Twin이 찾아주는 '멀지만 비슷한 지역'을 대부분 걸러내 버려서
Pooling의 취지(표본 확대)와 충돌한다.
"""

from __future__ import annotations

_SIDO_ADJ: dict[str, frozenset[str]] = {
    "11": frozenset({"41"}),  # 서울
    "26": frozenset({"31", "48"}),  # 부산
    "27": frozenset({"47"}),  # 대구
    "28": frozenset({"41"}),  # 인천
    "12": frozenset({"44", "45", "48"}),  # 전남광주통합 (구 광주·전남)
    "29": frozenset({"46"}),  # 광주 (레거시)
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


def allowed_twin_sidoes(anchor_sido: str) -> frozenset[str]:
    """앵커 시도 + 육상 인접 시도 집합(2자리 문자열)."""
    s = (anchor_sido or "").strip()[:2]
    if not s:
        return frozenset()
    neighbors = _SIDO_ADJ.get(s)
    if neighbors is None:
        return frozenset({s})
    return neighbors | frozenset({s})


def is_adjacent_region(anchor_codes: tuple[str, ...], twin_code: str) -> bool:
    """twin_code의 시도가 anchor 지역 중 하나와 같거나 인접 시도인지 확인한다."""
    twin_sido = (twin_code or "").strip()[:2]
    if not twin_sido:
        return False
    for anchor in anchor_codes:
        anchor_sido = (anchor or "").strip()[:2]
        if anchor_sido and twin_sido in allowed_twin_sidoes(anchor_sido):
            return True
    return False
