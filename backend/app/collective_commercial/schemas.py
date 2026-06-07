"""집합상가·집합공장 API 스키마."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.collective.schemas import AnalysisExplain, RegressionCoeff
from app.collective.schemas import AnalysisFeatures, FloorIndexCell

CommercialAssetType = Literal["collective_shop", "collective_factory"]


class CommercialFilterMeta(BaseModel):
    asset_types: list[str]
    contract_years: list[int]
    addr1_list: list[str]


class CommercialClusterRow(BaseModel):
    cluster_key: str
    display_label: str
    asset_type: str
    road_name: Optional[str] = None
    addr3: Optional[str] = None
    addr4: Optional[str] = None
    zone_type: Optional[str] = None
    building_use: Optional[str] = None
    building_year: Optional[int] = None
    area_bucket_label: Optional[str] = None
    confidence_tier: Optional[str] = None
    resolution_mode: Optional[str] = None
    count: int
    mean: Optional[float] = None
    median: Optional[float] = None
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    is_reliable: bool = False


class CommercialAddressRow(BaseModel):
    lot_number: str
    addr3: Optional[str] = None
    addr4: Optional[str] = None
    count: int
    mean: Optional[float] = None
    median: Optional[float] = None
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    is_reliable: bool = False


class CommercialAddressListResponse(BaseModel):
    cluster_key: str
    road_name: Optional[str] = None
    total: int
    items: list[CommercialAddressRow]


class CommercialClusterListResponse(BaseModel):
    total: int
    items: list[CommercialClusterRow]


class CommercialTransactionRow(BaseModel):
    id: int
    asset_type: str
    cluster_key: str
    addr3: Optional[str] = None
    addr4: Optional[str] = None
    lot_number: Optional[str] = None
    contract_year: Optional[int] = None
    contract_month: Optional[int] = None
    price: float
    gross_area: Optional[float] = None
    land_area: Optional[float] = None
    unit_price: Optional[float] = None
    floor: Optional[float] = None
    building_year: Optional[int] = None
    building_age: Optional[float] = None
    zone_type: Optional[str] = None
    building_use: Optional[str] = None
    area_bucket_label: Optional[str] = None
    road_name: Optional[str] = None
    road_code: Optional[float] = None
    road_width_label: Optional[str] = None


class CommercialTransactionListResponse(BaseModel):
    total: int
    items: list[CommercialTransactionRow]


class CommercialYearlyStatPoint(BaseModel):
    year: int
    count: int
    mean: Optional[float] = None


class CommercialYearlyStatsResponse(BaseModel):
    cluster_key: str
    display_label: str
    points: list[CommercialYearlyStatPoint]


class CommercialHistogramBin(BaseModel):
    lo: float
    hi: float
    count: int


class CommercialHistogramResponse(BaseModel):
    cluster_key: str
    bins: list[CommercialHistogramBin]
    n: int = 0
    contract_year: Optional[int] = None
    unit: str = "만원/㎡"


class CommercialRegressionSpec(BaseModel):
    gross_area: bool = True
    land_area: bool = False
    building_age: bool = True
    floor: bool = True
    zone_type: bool = True
    building_use: bool = True
    road_width: bool = True
    road_code: bool = False
    addr4: bool = False
    floor_mode: Literal["linear", "dummy", "grouped", "relative"] = "relative"


class CommercialRegressionRequest(BaseModel):
    addr1: Optional[str] = None
    addr2: Optional[str] = None
    addr3_list: list[str] = Field(default_factory=list)
    addr4_list: list[str] = Field(default_factory=list)
    contract_year_from: Optional[int] = None
    contract_year_to: Optional[int] = None
    variables: CommercialRegressionSpec = Field(default_factory=CommercialRegressionSpec)
    exclude_outliers_iqr: bool = False
    outlier_iqr_multiplier: float = 3.0
    experiment: bool = False


class CommercialRegressionResponse(BaseModel):
    cluster_key: str
    display_label: str
    n: int
    r_squared: Optional[float] = None
    adj_r_squared: Optional[float] = None
    coefficients: list[RegressionCoeff] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    explain: Optional[AnalysisExplain] = None


class CommercialFloorIndexResponse(BaseModel):
    cluster_key: str
    display_label: str
    asset_type: str
    dimension: str
    method: str = "simple_median"
    reference_floor: Optional[str] = None
    controls: list[str] = Field(default_factory=list)
    n_total: int
    n_regression: Optional[int] = None
    r_squared: Optional[float] = None
    baseline_median: Optional[float] = None
    cells: list[FloorIndexCell] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    explain: Optional[AnalysisExplain] = None
    analysis: AnalysisFeatures = Field(default_factory=AnalysisFeatures)
