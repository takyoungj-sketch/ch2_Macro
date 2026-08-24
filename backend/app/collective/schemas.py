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


class CollectiveMapResolveCodesResponse(BaseModel):
    """addr 칩 → /api/map/boundaries 용 행정코드."""

    level: Optional[Literal["sido", "sigungu", "eupmyeondong", "beopjungri"]] = None
    selected_codes: list[str] = Field(default_factory=list)
    context_sido_code: Optional[str] = None
    context_sigungu_code: Optional[str] = None
    labels: dict[str, str] = Field(default_factory=dict)
    has_selection: bool = False


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
    households: Optional[int] = None
    households_flagged: bool = False
    builder_label: Optional[str] = None
    builder_is_joint: bool = False
    asset_type: str
    count: int
    mean: Optional[float] = None
    median: Optional[float] = None
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    is_reliable: bool = False
    analysis: AnalysisFeatures = Field(default_factory=AnalysisFeatures)


class CollectiveBuildingGeocodeRequest(BaseModel):
    """선택 건물 지번 → 지도 라벨용 좌표."""

    addr1: str = Field(..., min_length=1)
    addr2: str = Field(..., min_length=1)
    jibun_address: Optional[str] = None
    road_address: Optional[str] = None
    building_key: Optional[str] = None
    label: Optional[str] = None


class CollectiveBuildingGeocodeResponse(BaseModel):
    ok: bool
    query: str
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    matched_name: Optional[str] = None
    category: Optional[str] = None
    label: Optional[str] = None
    building_key: Optional[str] = None
    error: Optional[str] = None


class CollectiveBuildingMapPointRequest(BaseModel):
    """지도 라벨용 건물 주소 입력."""

    building_key: str = Field(..., min_length=1, max_length=200)
    label: str = Field(..., min_length=1, max_length=200)
    addr1: str = Field(..., min_length=1)
    addr2: str = Field(..., min_length=1)
    jibun_address: Optional[str] = None
    road_address: Optional[str] = None


class CollectiveBuildingMapPointsRequest(BaseModel):
    """선택 지역 건물들의 좌표를 일괄 조회·캐시."""

    buildings: list[CollectiveBuildingMapPointRequest] = Field(..., min_length=1, max_length=100)


class CollectiveBuildingMapPoint(BaseModel):
    building_key: str
    label: str
    longitude: float
    latitude: float


class CollectiveBuildingMapPointsResponse(BaseModel):
    points: list[CollectiveBuildingMapPoint] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)


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
    # lifetime | rolling — 분양권 목록 모드 (혼합 목록에서도 참고)
    presale_stats_mode: Optional[str] = None


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
    median: Optional[float] = None


class YearlyStatsResponse(BaseModel):
    building_key: str
    display_name: str
    points: list[YearlyStatPoint]
    data_source: Literal["mart", "live"] = "live"


class RelatedPresaleCandidate(BaseModel):
    building_key: str
    display_name: str
    addr1: Optional[str] = None
    addr2: Optional[str] = None
    addr3: Optional[str] = None
    addr4: Optional[str] = None
    year_from: int
    year_to: int
    total_count: int
    score: float


class RelatedPresaleResponse(BaseModel):
    source_building_key: str
    source_display_name: str
    source_asset_type: str
    candidates: list[RelatedPresaleCandidate] = Field(default_factory=list)


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
    effect_plain: Optional[str] = None


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
    model_type: Literal["log", "linear"] = "linear"
    exclude_outliers_iqr: bool = False
    outlier_iqr_multiplier: float = 3.0
    experiment: bool = False


class CollectiveRegressionPredictRequest(CollectiveRegressionRequest):
    inputs: CollectiveRegressionPredictInputs = Field(default_factory=CollectiveRegressionPredictInputs)


class CohortRegressionPredictRequest(CollectiveRegressionPredictRequest):
    building_keys: list[str] = Field(..., min_length=1, max_length=10)


class CollectiveRegressionPredictResponse(BaseModel):
    n: int
    model_type: Literal["log", "linear"] = "linear"
    y_hat: float
    pi_lower: float
    pi_upper: float
    ci_lower: float
    ci_upper: float
    unit_price_hat: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)


class ModelMetrics(BaseModel):
    """단일 모델의 원척도(price) 평가지표."""
    model_type: Literal["log", "linear"]
    adj_r_squared: Optional[float] = None
    mape: Optional[float] = None  # %
    rmse: Optional[float] = None  # 만원
    cv_mape: Optional[float] = None  # rolling time-split out-of-sample MAPE (%)
    cv_folds: int = 0
    cv_method: Optional[str] = None


class ModelComparison(BaseModel):
    """로그·선형 모델 비교 + 권장·신뢰등급 (P1-B)."""
    log: Optional[ModelMetrics] = None
    linear: Optional[ModelMetrics] = None
    recommended: Literal["log", "linear"] = "log"
    metric_basis: Literal["cv", "insample"] = "insample"
    confidence_stars: int = 0  # 0~5
    confidence_label: Optional[str] = None


class CollectiveModelCandidate(BaseModel):
    rank: int
    blocks: list[str] = Field(default_factory=list)
    variables: CollectiveRegressionSpec
    model_type: Literal["log", "linear"]
    n: int
    adj_r_squared: Optional[float] = None
    mape: Optional[float] = None
    cv_mape: Optional[float] = None


class CollectiveRegressionResponse(BaseModel):
    building_key: str
    display_name: str
    n: int
    model_type: Literal["log", "linear"] = "linear"
    r_squared: Optional[float] = None
    adj_r_squared: Optional[float] = None
    price_adj_r_squared: Optional[float] = None
    mape: Optional[float] = None  # in-sample or CV, 금액(만원) 원척도
    f_p_value: Optional[float] = None
    significant_count: int = 0
    equation: str = ""
    coefficients: list[RegressionCoeff] = []
    warnings: list[str] = []
    predict_options: Optional[CollectivePredictOptions] = None
    model_comparison: Optional[ModelComparison] = None
    model_candidates: list[CollectiveModelCandidate] = Field(default_factory=list)
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
    model_type: Literal["log", "linear"] = "linear"
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


class DanjiMatchCandidate(BaseModel):
    danji_code: Optional[str] = None
    danji_name: Optional[str] = None
    households: Optional[int] = None
    builder_raw: Optional[str] = None


class DanjiMatchInfo(BaseModel):
    """K-apt 매칭 결과와 그 신뢰도 — 값보다 먼저 노출한다."""

    tier: str
    tier_label: str
    rule: str
    reliability: str
    usable_for_regression: bool = False
    danji_code: Optional[str] = None
    danji_name: Optional[str] = None
    approved_year: Optional[int] = None
    building_year: Optional[int] = None
    year_diff: Optional[int] = None
    note: Optional[str] = None
    candidates: list[DanjiMatchCandidate] = Field(default_factory=list)


class DanjiBuilderInfo(BaseModel):
    """원문(raw)·표기정규화(norm)·기업집단(group) 3단 분리 — 원자료 보존."""

    raw: Optional[str] = None
    norm: Optional[str] = None
    group: Optional[str] = None
    is_joint: bool = False
    is_public: bool = False
    developer_raw: Optional[str] = None


class DanjiBrandInfo(BaseModel):
    name: Optional[str] = None
    confidence: Optional[str] = None
    is_public: bool = False
    detected_from: Optional[str] = None


class DanjiScaleInfo(BaseModel):
    households: Optional[int] = None
    households_sale: Optional[int] = None
    households_rent: Optional[int] = None
    dong_count: Optional[int] = None
    max_floor: Optional[int] = None
    parking_total: Optional[int] = None
    parking_per_household: Optional[float] = None


class DanjiStructureInfo(BaseModel):
    raw: Optional[str] = None
    group: Optional[str] = None


class DanjiClassificationInfo(BaseModel):
    danji_class: Optional[str] = None
    supply_type: Optional[str] = None


class DanjiLandPriceInfo(BaseModel):
    assessed_land_price: Optional[float] = None
    assessed_land_price_year: Optional[int] = None
    representative_pnu: Optional[str] = None
    source: Optional[str] = None


class DanjiQualityFlag(BaseModel):
    """K-apt 원본 이상값 — 값은 지우지 않고 사유만 함께 노출한다(설계 §3.1.1)."""

    code: str
    label: str
    detail: Optional[str] = None
    affected_fields: list[str] = Field(default_factory=list)


class DanjiAttributesResponse(BaseModel):
    building_key: str
    snapshot_ym: Optional[str] = None
    source_label: str
    dictionary_version: Optional[str] = None
    matched: bool = False
    match: DanjiMatchInfo
    builder: Optional[DanjiBuilderInfo] = None
    brand: Optional[DanjiBrandInfo] = None
    scale: Optional[DanjiScaleInfo] = None
    structure: Optional[DanjiStructureInfo] = None
    classification: Optional[DanjiClassificationInfo] = None
    land_price: Optional[DanjiLandPriceInfo] = None
    quality_flags: list[DanjiQualityFlag] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
