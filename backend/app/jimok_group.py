"""지목군(7분류) SSOT — D-026 / docs/LAND_JIMOK_GROUP_DESIGN.md"""

from __future__ import annotations

from typing import Literal

MatrixMode = Literal["category", "group"]

# group_code → UI 라벨 (정렬 순서 = sort_order 계열)
JIMOK_GROUP_ORDER: list[tuple[str, str]] = [
    ("agri", "농경지"),
    ("forest", "산림지"),
    ("dev", "개발지"),
    ("infra", "기반시설"),
    ("water", "수면"),
    ("special", "특수용도"),
    ("other", "기타"),
]

JIMOK_GROUP_LABEL_BY_CODE: dict[str, str] = dict(JIMOK_GROUP_ORDER)
JIMOK_GROUP_CODE_BY_LABEL: dict[str, str] = {lab: code for code, lab in JIMOK_GROUP_ORDER}


def matrix_mode_to_col_axis(mode: MatrixMode | str | None) -> str:
    m = (mode or "category").strip().lower()
    if m == "group":
        return "group"
    return "category"


def display_land_key(raw: str, *, matrix_mode: MatrixMode | str) -> str:
    """mart land_category 키 → UI 표시 문자열."""
    key = (raw or "").strip()
    if matrix_mode_to_col_axis(matrix_mode) != "group" or key in ("", "ALL"):
        return key
    return JIMOK_GROUP_LABEL_BY_CODE.get(key, key)


def normalize_group_key(raw: str) -> str:
    """UI/요청의 지목군 키(코드 또는 라벨) → group_code."""
    t = (raw or "").strip()
    if not t:
        return t
    if t in JIMOK_GROUP_LABEL_BY_CODE:
        return t
    if t in JIMOK_GROUP_CODE_BY_LABEL:
        return JIMOK_GROUP_CODE_BY_LABEL[t]
    return t
