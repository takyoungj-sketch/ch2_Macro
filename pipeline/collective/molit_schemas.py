"""MOLIT raw Excel column layouts per collective asset type."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AssetType = Literal["apartment", "rowhouse", "officetel"]


@dataclass(frozen=True)
class MolitSchema:
    asset_type: AssetType
    building_name_field: str  # logical name in extracted frame
    cancel_col: int
    cancel_regex: str
    contract_day_fillna: int | None  # None = do not fill; 1 for rowhouse/officetel
    columns: dict[str, int]  # logical name -> iloc index


APARTMENT = MolitSchema(
    asset_type="apartment",
    building_name_field="building_name",
    cancel_col=16,
    cancel_regex=r"^\d{4,8}$",
    contract_day_fillna=None,
    columns={
        "sigungu": 1,
        "lot_number": 2,
        "building_name": 5,
        "exclusive_area": 6,
        "contract_ym": 7,
        "contract_day": 8,
        "price": 9,
        "dong": 10,
        "floor": 11,
        "building_year": 14,
        "road_name": 15,
    },
)

ROWHOUSE = MolitSchema(
    asset_type="rowhouse",
    building_name_field="building_name",
    cancel_col=16,
    cancel_regex=r"^\d{8}$",
    contract_day_fillna=1,
    columns={
        "sigungu": 1,
        "lot_number": 2,
        "building_name": 5,
        "exclusive_area": 6,
        "contract_ym": 8,
        "contract_day": 9,
        "price": 10,
        "floor": 11,
        "building_year": 14,
        "road_name": 15,
        "housing_subtype": 20,
    },
)

OFFICETEL = MolitSchema(
    asset_type="officetel",
    building_name_field="building_name",
    cancel_col=15,
    cancel_regex=r"^\d{4,8}$",
    contract_day_fillna=1,
    columns={
        "sigungu": 1,
        "lot_number": 2,
        "building_name": 5,
        "exclusive_area": 6,
        "contract_ym": 7,
        "contract_day": 8,
        "price": 9,
        "floor": 10,
        "building_year": 13,
        "road_name": 14,
    },
)

SCHEMAS: dict[AssetType, MolitSchema] = {
    "apartment": APARTMENT,
    "rowhouse": ROWHOUSE,
    "officetel": OFFICETEL,
}

REFINED_COL_MAP = {
    "주소1": "addr1",
    "주1": "addr1",
    "주소2": "addr2",
    "주2": "addr2",
    "주소3": "addr3",
    "주3": "addr3",
    "주소4": "addr4",
    "주4": "addr4",
    "주소5": "addr5",
    "주5": "addr5",
    "번지": "lot_number",
    "도로명": "road_name",
    "단지명": "building_name",
    "건물명": "building_name",
    "주택유형": "housing_subtype",
    "계약일자": "contract_date_label",
    "거래금액": "price",
    "면적규모": "area_bucket",
    "연식규모": "age_bucket",
    "전용면적": "exclusive_area",
    "연식": "building_age",
    "층": "floor",
    "동": "dong",
    "단가": "unit_price",
    "건축년도": "building_year",
}
