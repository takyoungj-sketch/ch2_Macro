"""집합부동산 API 스키마."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

AssetType = Literal["apartment", "rowhouse", "officetel", "presale"]


class CollectiveFilterMeta(BaseModel):
    asset_types: list[str]
    contract_years: list[int]
    addr1_list: list[str]


class RegionStructureResponse(BaseModel):
    has_intermediate: bool
    intermediate_label: Optional[str] = None
    leaf_level: str = "addr3"
    has_ri: bool = False
    tx_count: int = 0


class RegionOption(BaseModel):
    name: str
    count: int
    parent: Optional[str] = None
    disabled: bool = False
    min_reliable_count: int = 15


class AnalysisFeatures(BaseModel):
    """고급 분석(효용지수·회귀) 활성화 여부 — 선택 연도 구간 기준."""

    floor_index: bool = False
    regression: bool = False
    count_total: int = 0
    count_recent: int = 0
    messages: list[str] = []


class BuildingStatsRow(BaseModel):
    building_key: str
    display_name: str
    address: str = ""
    jibun_address: str = ""
    road_address: str = ""
    building_year: Optional[int] = None
    asset_type: str
    count: int
    mean: Optional[float] = None
    median: Optional[float] = None
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    is_reliable: bool = False
    analysis: AnalysisFeatures = Field(default_factory=AnalysisFeatures)


class BuildingListResponse(BaseModel):
    total: int
    items: list[BuildingStatsRow]
    data_source: Literal["mart", "live"] = "live"
    as_of_month: Optional[str] = None
    stats_reference_date: Optional[str] = None
    stats_as_of_label: Optional[str] = None
    window_years: Optional[int] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None


class CollectiveTransactionRow(BaseModel):
    id: int
    asset_type: str
    building_key: str
    display_name: str
    addr1: Optional[str] = None
    addr2: Optional[str] = None
    addr3: Optional[str] = None
    contract_year: Optional[int] = None
    contract_month: Optional[int] = None
    contract_date: Optional[str] = None
    exclusive_area: Optional[float] = None
    land_area: Optional[float] = None
    price: float
    unit_price: Optional[float] = None
    floor: Optional[float] = None
    dong: Optional[str] = None
    housing_subtype: Optional[str] = None
    building_age: Optional[float] = None
    buyer_type: Optional[str] = None
    seller_type: Optional[str] = None
    deal_type: Optional[str] = None
    road_name: Optional[str] = None


class TransactionListResponse(BaseModel):
    total: int
    items: list[CollectiveTransactionRow]


class YearlyStatPoint(BaseModel):
    year: int
    count: int
    mean: Optional[float] = None


class YearlyStatsResponse(BaseModel):
    building_key: str
    display_name: str
    points: list[YearlyStatPoint]
    data_source: Literal["mart", "live"] = "live"


class RollingStatPoint(BaseModel):
    bucket_index: int
    period_start: str
    period_end: str
    label: str
    count: int
    mean: Optional[float] = None


class RollingStatsResponse(BaseModel):
    building_key: str
    display_name: str
    window_years: int
    as_of_month: Optional[str] = None
    points: list[RollingStatPoint]
    data_source: Literal["mart", "live"] = "live"


class HistogramBin(BaseModel):
    lo: float
    hi: float
    count: int


class HistogramResponse(BaseModel):
    building_key: str
    bins: list[HistogramBin]
    n: int = 0
    contract_year: Optional[int] = None
    unit: str = "만원/㎡"


class FloorIndexCell(BaseModel):
    label: str
    floor: Optional[float] = None
    dong: Optional[str] = None
    area: Optional[float] = None
    count: int
    mean_unit_price: Optional[float] = None
    index: Optional[float] = None
    is_reliable: bool = False
    is_reference: bool = False
    gamma: Optional[float] = None
    p_value: Optional[float] = None
    index_lo: Optional[float] = None
    index_hi: Optional[float] = None


class FloorIndexDiagnostics(BaseModel):
    """효용지수 회귀 공선성 진단 (P1-A)."""
    max_vif: Optional[float] = None
    max_vif_term: Optional[str] = None
    condition_number: Optional[float] = None
    vifs: dict[str, float] = Field(default_factory=dict)


class AnalysisExplainPreset(BaseModel):
    id: str
    question: str
    answer: str


class AnalysisExplain(BaseModel):
    """분석 탭 설명 — 정적 spec + 이번 실행 결과 힌트(AI 연동용 fact)."""

    spec_id: str
    spec_version: str = "1"
    title: str
    summary: str
    formula: Optional[str] = None
    index_rule: Optional[str] = None
    reference: Optional[str] = None
    floor_groups: list[str] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    interpretation: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    interpretation_hints: list[str] = Field(default_factory=list)
    presets: list[AnalysisExplainPreset] = Field(default_factory=list)


class FloorIndexResponse(BaseModel):
    building_key: str
    display_name: str
    asset_type: str
    dimension: str
    method: Optional[str] = None
    reference_floor: Optional[str] = None
    controls: list[str] = Field(default_factory=list)
    n_total: int
    n_regression: Optional[int] = None
    r_squared: Optional[float] = None
    baseline_median: Optional[float] = None
    cells: list[FloorIndexCell] = []
    warnings: list[str] = Field(default_factory=list)
    explain: Optional[AnalysisExplain] = None
    analysis: AnalysisFeatures = Field(default_factory=AnalysisFeatures)
    diagnostics: Optional[FloorIndexDiagnostics] = None


class CollectiveRegressionSpec(BaseModel):
    exclusive_area: bool = True
    building_age: bool = True
    floor: bool = True
    dong: bool = True
    housing_subtype: bool = False
    floor_mode: Literal["linear", "dummy", "grouped", "relative"] = "relative"


class RegressionCoeff(BaseModel):
    name: str
    label: str
    coef: float
    se: Optional[float] = None
    t: Optional[float] = None
    p: Optional[float] = None


class ContinuousRange(BaseModel):
    name: str
    min: Optional[float] = None
    max: Optional[float] = None


class BuildingFeOption(BaseModel):
    building_key: str
    display_name: str
    count: int
    is_reference: bool = False
    has_fe: bool = False


class CollectivePredictOptions(BaseModel):
    exclusive_area: Optional[ContinuousRange] = None
    building_age: Optional[ContinuousRange] = None
    floor: Optional[ContinuousRange] = None
    max_floor: Optional[float] = None
    floor_mode: str = "relative"
    dongs: list[str] = Field(default_factory=list)
    dong_reference: Optional[str] = None
    housing_subtypes: list[str] = Field(default_factory=list)
    housing_subtype_reference: Optional[str] = None
    buildings: list[BuildingFeOption] = Field(default_factory=list)


class CollectiveRegressionPredictInputs(BaseModel):
    exclusive_area: Optional[float] = None
    building_age: Optional[float] = None
    floor: Optional[float] = None
    dong: Optional[str] = None
    housing_subtype: Optional[str] = None
    building_key: Optional[str] = None


class CollectiveRegressionRequest(BaseModel):
    asset_type: AssetType
    contract_year_from: Optional[int] = None
    contract_year_to: Optional[int] = None
    contract_date_from: Optional[date] = None
    contract_date_to: Optional[date] = None
    variables: CollectiveRegressionSpec = Field(default_factory=CollectiveRegressionSpec)
    exclude_outliers_iqr: bool = False
    outlier_iqr_multiplier: float = 3.0
    experiment: bool = False


class CollectiveRegressionPredictRequest(CollectiveRegressionRequest):
    inputs: CollectiveRegressionPredictInputs = Field(default_factory=CollectiveRegressionPredictInputs)


class CohortRegressionPredictRequest(CollectiveRegressionPredictRequest):
    building_keys: list[str] = Field(..., min_length=1, max_length=10)


class CollectiveRegressionPredictResponse(BaseModel):
    n: int
    y_hat: float
    pi_lower: float
    pi_upper: float
    ci_lower: float
    ci_upper: float
    unit_price_hat: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)


class CollectiveRegressionResponse(BaseModel):
    building_key: str
    display_name: str
    n: int
    r_squared: Optional[float] = None
    adj_r_squared: Optional[float] = None
    coefficients: list[RegressionCoeff] = []
    warnings: list[str] = []
    predict_options: Optional[CollectivePredictOptions] = None
    explain: Optional[AnalysisExplain] = None


class CohortBuildingSummary(BaseModel):
    building_key: str
    display_name: str
    count: int


class CohortAnalysisRequest(BaseModel):
    building_keys: list[str] = Field(..., min_length=1, max_length=10)
    asset_type: Optional[AssetType] = None
    contract_year_from: Optional[int] = None
    contract_year_to: Optional[int] = None
    contract_date_from: Optional[date] = None
    contract_date_to: Optional[date] = None
    variables: CollectiveRegressionSpec = Field(default_factory=CollectiveRegressionSpec)
    dimension: Literal["floor", "dong", "area", "rights"] = "floor"
    exclude_outliers_iqr: bool = False
    outlier_iqr_multiplier: float = 3.0
    experiment: bool = False


class CohortFloorIndexResponse(BaseModel):
    building_keys: list[str]
    cohort_buildings: list[CohortBuildingSummary]
    asset_type: str
    dimension: str
    method: Optional[str] = None
    reference_floor: Optional[str] = None
    controls: list[str] = Field(default_factory=list)
    n_total: int
    n_regression: Optional[int] = None
    r_squared: Optional[float] = None
    baseline_median: Optional[float] = None
    cells: list[FloorIndexCell] = []
    warnings: list[str] = Field(default_factory=list)
    explain: Optional[AnalysisExplain] = None
    analysis: AnalysisFeatures = Field(default_factory=AnalysisFeatures)
    diagnostics: Optional[FloorIndexDiagnostics] = None


class CohortRegressionResponse(CollectiveRegressionResponse):
    building_keys: list[str] = Field(default_factory=list)
    cohort_buildings: list[CohortBuildingSummary] = Field(default_factory=list)


class CohortYearlyStatsResponse(BaseModel):
    building_keys: list[str]
    series: list[YearlyStatsResponse]
    data_source: Literal["live"] = "live"


class CohortHistogramResponse(BaseModel):
    building_keys: list[str]
    bins: list[HistogramBin]
    n: int = 0
    contract_year: Optional[int] = None
    data_source: Literal["live"] = "live"


class CohortTransactionsRequest(CohortAnalysisRequest):
    page: int = Field(1, ge=1)
    page_size: int = Field(25, ge=1, le=200)
    contract_year: Optional[int] = None


class CohortTransactionsResponse(BaseModel):
    building_keys: list[str]
    total: int
    items: list[CollectiveTransactionRow]
    data_source: Literal["live"] = "live"
