"""PNU 유일 K-apt 승격 — 주소 규칙(A~F)이 못 붙인 뒤에만 탄다.

대전·충북 pnu_new 22단지 이름 확인 결과:
- 채움(약칭·연식 맞음)
- 재건축(같은 필지·다른 건물) — 붙이지 않음
- 묶음(K-apt가 1·2 / A·B 를 한 코드로 둠) — D/F 백로그와 같음, 목록 안 채움

지역회귀 hard 표본은 계속 A·B·C 만. 이 규칙은 목록 세대수·시공사 채움용(tier P).
"""

from __future__ import annotations

import re
import unicodedata

REBUILD_YEAR_GAP = 15

# K-apt 단지명이 1·2 / A·B / 2.3차 / 25,26,27차 를 한 코드로 묶은 경우
_BUNDLE_KAPT = re.compile(r"\d+\s*,\s*\d+|A\s*,\s*B|\d+\s*\.\s*\d+")
# 실거래 동 범위 — 푸르지오캐슬(301~302)처럼 단지 일부가 이름에 있음
_DONG_RANGE = re.compile(r"\d{3}\s*[~\-～]\s*\d{3}")

# 1,2 / A,B 패턴에 안 걸리는 우산 이름. 실거래는 한쪽(2단지)만.
_UMBRELLA_SLICES: tuple[tuple[str, str], ...] = (
    ("문화마을2단지", "문화마을금호어울림"),
)


def _compact(value: object) -> str:
    t = unicodedata.normalize("NFC", str(value or ""))
    return re.sub(r"\s+", "", t)


def kapt_name_is_bundle(kapt_name: object) -> bool:
    return bool(_BUNDLE_KAPT.search(_compact(kapt_name)))


def tx_name_has_dong_range(tx_name: object) -> bool:
    return bool(_DONG_RANGE.search(str(tx_name or "")))


def tx_is_umbrella_slice(tx_name: object, kapt_name: object) -> bool:
    tx = _compact(tx_name)
    kapt = _compact(kapt_name)
    for tx_frag, kapt_frag in _UMBRELLA_SLICES:
        if _compact(tx_frag) in tx and _compact(kapt_frag) in kapt:
            return True
    return False


def pnu_unique_skip_reason(
    *,
    tx_name: object,
    kapt_name: object,
    approved_year: int | None,
    building_year: int | None,
) -> str | None:
    """None 이면 채움. 'rebuild' | 'bundle' 이면 속성을 붙이지 않는다."""
    if (
        approved_year is not None
        and building_year is not None
        and abs(int(approved_year) - int(building_year)) >= REBUILD_YEAR_GAP
    ):
        return "rebuild"
    if kapt_name_is_bundle(kapt_name):
        return "bundle"
    if tx_name_has_dong_range(tx_name):
        return "bundle"
    if tx_is_umbrella_slice(tx_name, kapt_name):
        return "bundle"
    return None
