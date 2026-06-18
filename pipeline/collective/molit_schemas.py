"""MOLIT raw Excel column layouts per collective asset type."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AssetType = Literal["apartment", "rowhouse", "officetel", "presale"]


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
        "buyer_type": 12,
        "seller_type": 13,
        "deal_type": 17,
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
        "land_area": 7,
        "contract_ym": 8,
        "contract_day": 9,
        "price": 10,
        "floor": 11,
        "building_year": 14,
        "road_name": 15,
        "housing_subtype": 20,
        "buyer_type": 12,
        "seller_type": 13,
        "deal_type": 17,
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
        "buyer_type": 11,
        "seller_type": 12,
        "deal_type": 16,
    },
)

# 분양입주권 CSV: 15열 — col7·8 매수자/매도자, 해제 col12
PRESALE = MolitSchema(
    asset_type="presale",
    building_name_field="building_name",
    cancel_col=12,
    cancel_regex=r"^\d{4,8}$",
    contract_day_fillna=1,
    columns={
        "sigungu": 1,
        "lot_number": 2,
        "building_name": 3,
        "exclusive_area": 4,
        "price": 5,
        "floor": 6,
        "contract_ym": 9,
        "contract_day": 10,
        "housing_subtype": 11,
        "buyer_type": 7,
        "seller_type": 8,
        "deal_type": 14,
    },
)

SCHEMAS: dict[AssetType, MolitSchema] = {
    "apartment": APARTMENT,
    "rowhouse": ROWHOUSE,
    "officetel": OFFICETEL,
    "presale": PRESALE,
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
    "분양권/입주권": "housing_subtype",
    "권리구분": "housing_subtype",
    "계약일자": "contract_date_label",
    "거래금액": "price",
    "면적규모": "area_bucket",
    "연식규모": "age_bucket",
    "전용면적": "exclusive_area",
    "대지권면적": "land_area",
    "대지면적": "land_area",
    "연식": "building_age",
    "층": "floor",
    "동": "dong",
    "단가": "unit_price",
    "건축년도": "building_year",
}
