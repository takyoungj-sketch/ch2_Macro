"""집합상가·집합공장 API 스키마."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.collective.schemas import AnalysisExplain, ContinuousRange, ModelComparison, RegressionCoeff
from app.collective.schemas import AnalysisFeatures, FloorIndexCell, FloorIndexDiagnostics

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
    data_source: Literal["mart", "live"] = "live"
    as_of_month: Optional[str] = None
    stats_reference_date: Optional[str] = None
    stats_as_of_label: Optional[str] = None
    window_years: Optional[int] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None


class CommercialTransactionRow(BaseModel):
    id: int
    asset_type: str
    cluster_key: str
    addr3: Optional[str] = None
    addr4: Optional[str] = None
    lot_number: Optional[str] = None
    contract_year: Optional[int] = None
    contract_month: Optional[int] = None
    contract_date: Optional[str] = None
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
    median: Optional[float] = None


class CommercialYearlyStatsResponse(BaseModel):
    cluster_key: str
    display_label: str
    points: list[CommercialYearlyStatPoint]
    data_source: Literal["mart", "live"] = "live"


class CommercialRollingStatPoint(BaseModel):
    bucket_index: int
    period_start: str
    period_end: str
    label: str
    count: int
    mean: Optional[float] = None


class CommercialRollingStatsResponse(BaseModel):
    cluster_key: str
    display_label: str
    window_years: int
    as_of_month: Optional[str] = None
    stats_as_of_label: Optional[str] = None
    points: list[CommercialRollingStatPoint]
    data_source: Literal["mart", "live"] = "live"


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
    model_type: Literal["log", "linear"] = "linear"


class CommercialRegressionResponse(BaseModel):
    cluster_key: str
    display_label: str
    n: int
    model_type: Literal["log", "linear"] = "linear"
    r_squared: Optional[float] = None
    adj_r_squared: Optional[float] = None
    price_adj_r_squared: Optional[float] = None
    mape: Optional[float] = None
    f_p_value: Optional[float] = None
    significant_count: int = 0
    equation: str = ""
    coefficients: list[RegressionCoeff] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    predict_options: Optional["CommercialPredictOptions"] = None
    model_comparison: Optional[ModelComparison] = None
    explain: Optional[AnalysisExplain] = None


class CommercialPredictOptions(BaseModel):
    gross_area: Optional[ContinuousRange] = None
    building_age: Optional[ContinuousRange] = None
    floor: Optional[ContinuousRange] = None
    max_floor: Optional[float] = None
    floor_mode: str = "relative"
    road_code: Optional[ContinuousRange] = None
    zone_types: list[str] = Field(default_factory=list)
    zone_type_reference: Optional[str] = None
    building_uses: list[str] = Field(default_factory=list)
    building_use_reference: Optional[str] = None
    road_width_labels: list[str] = Field(default_factory=list)
    road_width_reference: Optional[str] = None


class CommercialRegressionPredictInputs(BaseModel):
    gross_area: Optional[float] = None
    building_age: Optional[float] = None
    floor: Optional[float] = None
    road_code: Optional[float] = None
    zone_type: Optional[str] = None
    building_use: Optional[str] = None
    road_width_label: Optional[str] = None


class CommercialRegressionPredictRequest(CommercialRegressionRequest):
    inputs: CommercialRegressionPredictInputs = Field(default_factory=CommercialRegressionPredictInputs)


class CommercialRegressionPredictResponse(BaseModel):
    n: int
    model_type: Literal["log", "linear"] = "linear"
    y_hat: float
    pi_lower: float
    pi_upper: float
    ci_lower: float
    ci_upper: float
    unit_price_hat: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)


class CommercialFloorIndexResponse(BaseModel):
    cluster_key: str
    display_label: str
    asset_type: str
    dimension: str
    method: str = "regression_semilog"
    floor_mode: Optional[str] = None
    reference_floor: Optional[str] = None
    regression_reference_floor: Optional[str] = None
    controls: list[str] = Field(default_factory=list)
    n_total: int
    n_regression: Optional[int] = None
    r_squared: Optional[float] = None
    baseline_median: Optional[float] = None
    cells: list[FloorIndexCell] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    explain: Optional[AnalysisExplain] = None
    diagnostics: Optional[FloorIndexDiagnostics] = None
    analysis: AnalysisFeatures = Field(default_factory=AnalysisFeatures)


class CommercialCohortClusterSummary(BaseModel):
    cluster_key: str
    display_label: str
    count: int


class CommercialCohortAnalysisRequest(BaseModel):
    cluster_keys: list[str] = Field(..., min_length=1, max_length=10)
    asset_type: Optional[CommercialAssetType] = None
    contract_year_from: Optional[int] = None
    contract_year_to: Optional[int] = None
    contract_date_from: Optional[date] = None
    contract_date_to: Optional[date] = None
    variables: CommercialRegressionSpec = Field(default_factory=CommercialRegressionSpec)
    model_type: Literal["log", "linear"] = "linear"
    dimension: Literal["floor", "area"] = "floor"
    exclude_outliers_iqr: bool = False
    outlier_iqr_multiplier: float = 3.0
    experiment: bool = False


class CommercialCohortRegressionPredictRequest(CommercialRegressionPredictRequest):
    cluster_keys: list[str] = Field(..., min_length=1, max_length=10)


class CommercialCohortRegressionResponse(CommercialRegressionResponse):
    cluster_keys: list[str] = Field(default_factory=list)
    cohort_clusters: list[CommercialCohortClusterSummary] = Field(default_factory=list)


class CommercialCohortYearlySeries(BaseModel):
    cluster_key: str
    display_label: str
    points: list[CommercialYearlyStatPoint]
    data_source: Literal["mart", "live"] = "live"


class CommercialCohortYearlyStatsResponse(BaseModel):
    cluster_keys: list[str]
    series: list[CommercialCohortYearlySeries]
    data_source: Literal["live"] = "live"


class CommercialCohortHistogramResponse(BaseModel):
    cluster_keys: list[str]
    bins: list[CommercialHistogramBin]
    n: int = 0
    contract_year: Optional[int] = None
    data_source: Literal["live"] = "live"


class CommercialCohortTransactionsRequest(CommercialCohortAnalysisRequest):
    page: int = Field(1, ge=1)
    page_size: int = Field(25, ge=1, le=200)
    contract_year: Optional[int] = None


class CommercialCohortTransactionsResponse(BaseModel):
    cluster_keys: list[str]
    total: int
    items: list[CommercialTransactionRow]
    data_source: Literal["live"] = "live"


class CommercialCohortFloorIndexResponse(BaseModel):
    cluster_keys: list[str]
    cohort_clusters: list[CommercialCohortClusterSummary]
    asset_type: str
    dimension: str
    method: Optional[str] = None
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
    diagnostics: Optional[FloorIndexDiagnostics] = None
