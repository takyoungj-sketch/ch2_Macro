from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class LeaseMetric(BaseModel):
    n: int = 0
    mean: Optional[float] = None
    median: Optional[float] = None
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None


class MixedLeaseMetric(BaseModel):
    n: int = 0
    deposit: LeaseMetric = Field(default_factory=LeaseMetric)
    monthly: LeaseMetric = Field(default_factory=LeaseMetric)


class RentConversionRate(BaseModel):
    asset_type: str
    r_selected: Optional[float] = None
    method_selected: str = "mean_simple"
    gate_passed: bool = False
    n_buildings: int = 0
    n_jeonse: int = 0
    n_mixed: int = 0
    r_mean_simple: Optional[float] = None
    r_mean_weighted: Optional[float] = None
    r_ols_origin: Optional[float] = None
    r_ols_weighted: Optional[float] = None
    scope: str = "sigungu"
    addr3: str = ""
    fallback: bool = False


class RentConversionCompareRow(BaseModel):
    addr1: str
    addr2: str
    asset_type: str
    window_years: int
    n_buildings: int = 0
    n_jeonse: int = 0
    n_mixed: int = 0
    r_mean_simple: Optional[float] = None
    r_mean_weighted: Optional[float] = None
    r_ols_origin: Optional[float] = None
    r_ols_weighted: Optional[float] = None
    r_selected: Optional[float] = None
    method_selected: str = "mean_simple"
    gate_passed: bool = False


class RentConversionCompareResponse(BaseModel):
    as_of_month: Optional[date] = None
    items: list[RentConversionCompareRow] = Field(default_factory=list)


class RentBuildingRow(BaseModel):
    building_key: str
    asset_type: str
    display_name: str
    jibun_address: str = ""
    road_address: str = ""
    building_year: Optional[int] = None
    addr3: str = ""
    jeonse: LeaseMetric
    mixed: MixedLeaseMetric
    monthly: LeaseMetric
    jeonse_equiv: LeaseMetric = Field(default_factory=LeaseMetric)
    monthly_equiv: LeaseMetric = Field(default_factory=LeaseMetric)


class RentBuildingListResponse(BaseModel):
    items: list[RentBuildingRow]
    total: int
    as_of_month: Optional[date] = None
    window_years: int
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    stats_as_of_label: str = ""
    unit: str = "만원/㎡"
    conversion_rates: list[RentConversionRate] = Field(default_factory=list)
    conversion_applied: bool = False
    conversion_method: str = "mean_simple"
    conversion_scope: str = "sigungu"
    conversion_fallback: bool = False


class RentRollingPoint(BaseModel):
    bucket_index: int
    period_start: date
    period_end: date
    label: str
    jeonse: LeaseMetric
    mixed: MixedLeaseMetric
    monthly: LeaseMetric


class RentRollingResponse(BaseModel):
    building_key: str
    asset_type: str
    window_years: int
    points: list[RentRollingPoint]


class RentRegionOption(BaseModel):
    name: str
    count: int = 0
    parent: Optional[str] = None


class RentRegionStructure(BaseModel):
    has_intermediate: bool = False
    intermediate_label: Optional[str] = None
    leaf_level: str = "addr3"


class RentFilterMeta(BaseModel):
    addr1: list[str]
    as_of_month: Optional[date] = None
    window_years: list[int] = Field(default_factory=lambda: [3, 5, 7])
    asset_types: list[str] = Field(
        default_factory=lambda: ["apartment", "rowhouse", "officetel", "detached"]
    )


class RentTransactionRow(BaseModel):
    id: int
    contract_date: Optional[date] = None
    contract_year: Optional[int] = None
    contract_month: Optional[int] = None
    floor: Optional[float] = None
    exclusive_area: Optional[float] = None
    contract_area: Optional[float] = None
    building_year: Optional[int] = None
    deposit_manwon: Optional[float] = None
    monthly_rent_manwon: Optional[float] = None
    deposit_per_m2: Optional[float] = None
    monthly_per_m2: Optional[float] = None
    lease_kind: str = "jeonse"
    display_name: str = ""
    asset_type: str = ""


class RentTransactionListResponse(BaseModel):
    total: int
    items: list[RentTransactionRow] = Field(default_factory=list)


class RentMapResolveCodesResponse(BaseModel):
    level: Optional[str] = None
    selected_codes: list[str] = Field(default_factory=list)
    context_sido_code: Optional[str] = None
    context_sigungu_code: Optional[str] = None
    labels: dict[str, str] = Field(default_factory=dict)
    has_selection: bool = False


class RentBuildingGeocodeRequest(BaseModel):
    addr1: str
    addr2: str
    jibun_address: Optional[str] = None
    road_address: Optional[str] = None
    building_key: Optional[str] = None
    label: Optional[str] = None


class RentBuildingGeocodeResponse(BaseModel):
    ok: bool
    query: str = ""
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    matched_name: Optional[str] = None
    category: Optional[str] = None
    label: Optional[str] = None
    building_key: Optional[str] = None
    error: Optional[str] = None


class RentBuildingMapPointIn(BaseModel):
    building_key: str
    label: str = ""
    addr1: str
    addr2: str
    jibun_address: Optional[str] = None
    road_address: Optional[str] = None


class RentBuildingMapPointsRequest(BaseModel):
    buildings: list[RentBuildingMapPointIn] = Field(default_factory=list)


class RentBuildingMapPointOut(BaseModel):
    building_key: str
    label: str = ""
    longitude: float
    latitude: float


class RentBuildingMapPointsResponse(BaseModel):
    points: list[RentBuildingMapPointOut] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)


class SangkwonPolygonFeature(BaseModel):
    sec_seq: int
    sec_nm: str
    sido: str = ""
    buld_nm: str = ""
    geometry: dict = Field(default_factory=dict)


class SangkwonPolygonsResponse(BaseModel):
    type: str = "FeatureCollection"
    features: list[dict] = Field(default_factory=list)
    latest_year: Optional[int] = None
    source_file: str = ""


class SangkwonAnnualCellRow(BaseModel):
    metric: str
    group: str = ""
    group_label: str = ""
    values: dict[str, Optional[float]] = Field(default_factory=dict)


class SangkwonAnnualResponse(BaseModel):
    year: Optional[int] = None
    sec_nm: str
    sido: str = ""
    rows: list[SangkwonAnnualCellRow] = Field(default_factory=list)
    source_file: str = ""
    latest_year: Optional[int] = None
    latest_quarter: Optional[int] = None


class SangkwonSeriesPoint(BaseModel):
    year: int
    value: Optional[float] = None


class SangkwonSeriesItem(BaseModel):
    asset_kind: str
    metric: str
    floor_label: str = ""
    points: list[SangkwonSeriesPoint] = Field(default_factory=list)


class SangkwonSeriesResponse(BaseModel):
    sec_nm: str
    sido: str = ""
    from_year: int = 2019
    years: list[int] = Field(default_factory=list)
    series: list[SangkwonSeriesItem] = Field(default_factory=list)
    floor_labels: list[str] = Field(default_factory=list)
    source_file: str = ""
    break_note: str = ""
