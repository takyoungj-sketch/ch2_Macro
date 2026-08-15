"""국토부 주거 전월세 CSV — 헤더명 매핑 (iloc 인덱스 사용 금지)."""

from __future__ import annotations

from typing import Literal

RentAssetType = Literal["apartment", "rowhouse", "officetel", "detached"]

ASSET_DIRS: dict[RentAssetType, str] = {
    "apartment": "아파트_전월세",
    "rowhouse": "연립다세대_전월세",
    "officetel": "오피스텔_전월세",
    "detached": "단독다가구_전월세",
}

FILE_LABEL: dict[RentAssetType, str] = {
    "apartment": "아파트",
    "rowhouse": "연립다세대",
    "officetel": "오피스텔",
    "detached": "단독다가구",
}

HEADER_MAP: dict[str, str] = {
    "시군구": "sigungu",
    "번지": "lot_number",
    "본번": "lot_bun",
    "부번": "lot_ji",
    "단지명": "building_name",
    "건물명": "building_name",
    "전월세구분": "molit_lease_kind",
    "전용면적(㎡)": "exclusive_area",
    "계약면적(㎡)": "contract_area",
    "계약년월": "contract_ym",
    "계약일": "contract_day",
    "보증금(만원)": "deposit_manwon",
    "월세금(만원)": "monthly_rent_manwon",
    "층": "floor",
    "건축년도": "building_year",
    "도로명": "road_name",
    "도로조건": "road_width_label",
    "계약기간": "lease_term_raw",
    "계약구분": "contract_class_raw",
    "갱신요구권 사용": "renewal_right_raw",
    "종전계약 보증금(만원)": "prev_deposit_manwon",
    "종전계약 월세(만원)": "prev_monthly_rent_manwon",
    "주택유형": "housing_subtype",
}


def normalize_header(name: str) -> str:
    t = str(name).strip().lstrip("\ufeff")
    t = t.replace("m²", "㎡").replace("M2", "㎡").replace("m2", "㎡")
    t = t.replace("M²", "㎡")
    return t
