"""MOLIT raw base CSV column layouts — 복합부동산 일반 3유형."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BuiltAssetType = Literal["commercial", "factory", "detached"]

MOLIT_CSV_SKIPROWS = 15
CANCEL_REGEX = r"^\d{4,8}$"


@dataclass(frozen=True)
class BuiltMolitSchema:
    asset_type: BuiltAssetType
    cancel_col: int
    type_filter_col: int | None  # iloc; value must equal type_filter_value
    type_filter_value: str | None
    contract_day_fillna: int | None
    columns: dict[str, int]


# 상업업무·공장창고 — 21열 (실측 2026-06)
COMMERCIAL_FACTORY = BuiltMolitSchema(
    asset_type="commercial",
    cancel_col=18,
    type_filter_col=2,
    type_filter_value="일반",
    contract_day_fillna=None,
    columns={
        "sigungu": 1,
        "deal_type_raw": 2,
        "lot_number": 3,
        "road_name": 4,
        "zone_type": 5,
        "building_use": 6,
        "road_width_raw": 7,
        "gross_area": 8,
        "land_area": 9,
        "price": 10,
        "floor": 11,
        "contract_ym": 14,
        "contract_day": 15,
        "building_year": 17,
        "deal_type": 19,
    },
)

DETACHED = BuiltMolitSchema(
    asset_type="detached",
    cancel_col=14,
    type_filter_col=None,
    type_filter_value=None,
    contract_day_fillna=None,
    columns={
        "sigungu": 1,
        "lot_number": 2,
        "building_use": 3,
        "road_width_raw": 4,
        "gross_area": 5,
        "land_area": 6,
        "contract_ym": 7,
        "contract_day": 8,
        "price": 9,
        "building_year": 12,
        "road_name": 13,
        "deal_type": 15,
    },
)

SCHEMAS: dict[BuiltAssetType, BuiltMolitSchema] = {
    "commercial": COMMERCIAL_FACTORY,
    "factory": COMMERCIAL_FACTORY,
    "detached": DETACHED,
}

RAW_BASE_DIRS: dict[BuiltAssetType, str] = {
    "commercial": "상업업무_2021_2026",
    "factory": "공장창고_2021_2026",
    "detached": "단독다가구_2021_2026",
}

FILE_LABEL: dict[BuiltAssetType, str] = {
    "commercial": "상업업무",
    "factory": "공장창고",
    "detached": "단독다가구",
}
