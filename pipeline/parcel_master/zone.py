"""AL_D155 용도지역 라벨 판정.

대분류는 코드(UQA001)가 아니라 라벨 이름이다 (D-047).
농림지역·자연환경보전지역은 세부 없는 최종 용도지역이라 대분류가 아니다.
"""

from __future__ import annotations

import re

ZONE_CODE_RE = re.compile(r"^UQ[ABCD]", re.IGNORECASE)
ZONE_COARSE_LABELS = {
    "도시지역",
    "도시지역기타",
    "비도시지역",
    "관리지역",
    "도시관리계획 입안중",
}
ZONE_FAMILIES = ("주거", "상업", "공업", "녹지", "관리", "농림", "자연환경")
ZONE_SUFFIX_RE = re.compile(r"(지역|지구|구역)$")
ZONE_SOURCE = "al_d155"


def zone_key(label: str) -> str:
    t = re.sub(r"\s+", "", (label or "").strip())
    while ZONE_SUFFIX_RE.search(t):
        t = ZONE_SUFFIX_RE.sub("", t)
    return t


def is_coarse_label(label: str) -> bool:
    return (label or "").strip() in ZONE_COARSE_LABELS


def zone_family(label: str) -> str | None:
    t = zone_key(label)
    for fam in ZONE_FAMILIES:
        if fam in t:
            return fam
    return None


def is_zone_code(code: str) -> bool:
    return bool(ZONE_CODE_RE.match((code or "").strip()))
