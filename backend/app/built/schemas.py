"""복합부동산 API 스키마."""

from __future__ import annotations

import math
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.ai.schemas import AnalysisExplain
from app.collective.schemas import ModelComparison, ModelMetrics

# 단일 / 통합(all) / 복수("commercial,factory")
AssetType = str
ResponseScale = Literal["linear", "log"]
AdminLevel = Literal["sigungu", "gu", "eupmyeondong", "beopjungri"]


class BuiltTransactionRow(BaseModel):
    id: int
    asset_type: str
    addr1: Optional[str] = None
    addr2: Optional[str] = None
    addr3: Optional[str] = None
    addr4: Optional[str] = None
    addr5: Optional[str] = None
    lot_number: Optional[str] = None
    display_address: Optional[str] = None
    road_name: Optional[str] = None
    trade_year_label: Optional[str] = None
    contract_year: Optional[int] = None
    contract_month: Optional[int] = None
    contract_date: Optional[str] = None
    zone_type: Optional[str] = None
    building_use: Optional[str] = None
    building_scale: Optional[float] = None
    land_scale: Optional[float] = None
    age_bucket: Optional[float] = None
    price: float
    gross_area: Optional[float] = None
    land_area: Optional[float] = None
    building_age: Optional[float] = None
    building_year: Optional[int] = None
    road_code: Optional[float] = None
    road_width_label: Optional[str] = None
    deal_type: Optional[str] = None
    buyer_type: Optional[str] = None
    seller_type: Optional[str] = None


class BuiltTransactionListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[BuiltTransactionRow]


class BuiltFilterMetaResponse(BaseModel):
    asset_types: list[str]
    contract_years: list[int]
    zone_types: list[str]
    building_uses: list[str]
    road_width_labels: list[str] = Field(default_factory=list)
    addr1_list: list[str]
    as_of_month: Optional[str] = None
    default_window_years: int = 3


class BuiltScopeStatsRow(BaseModel):
    asset_type: str
    addr1: str
    addr2: str
    as_of_month: str
    window_years: int
    tx_count: int
    median_price: Optional[float] = None
    mean_price: Optional[float] = None


class CategoryCountOption(BaseModel):
    name: str
    count: int


class NumericRangeHint(BaseModel):
    name: str
    min: Optional[float] = None
    max: Optional[float] = None


class ScopeSampleFilterResponse(BaseModel):
    total: int
    zone_types: list[CategoryCountOption] = Field(default_factory=list)
    building_uses: list[CategoryCountOption] = Field(default_factory=list)
    road_width_labels: list[CategoryCountOption] = Field(default_factory=list)
    continuous: list[NumericRangeHint] = Field(default_factory=list)


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


class BuiltMapResolveCodesResponse(BaseModel):
    """addr 칩 → /api/map/boundaries 용 행정코드."""

    level: Optional[Literal["sido", "sigungu", "eupmyeondong", "beopjungri"]] = None
    selected_codes: list[str] = Field(default_factory=list)
    context_sido_code: Optional[str] = None
    context_sigungu_code: Optional[str] = None
    labels: dict[str, str] = Field(default_factory=dict)
    has_selection: bool = False


class RiPick(BaseModel):
    """상위 읍·면 + 리(addr5)."""

    eup: str
    ri: str


RegionCodeLevel = Literal["eupmyeondong", "beopjungri"]


class RegressionVariableSpec(BaseModel):
    gross_area: bool = True
    land_area: bool = True
    building_age: bool = True
    road_width_dummy: bool = True
    road_code: bool = False
    zone_type_dummy: bool = True
    building_use_dummy: bool = True
    asset_type_dummy: bool = True
    region_leaf_dummy: bool = False


class RegressionRunRequest(BaseModel):
    asset_type: AssetType = "commercial"
    addr1: Optional[str] = None
    addr2: Optional[str] = None
    addr3: Optional[str] = None  # 하위 호환 — addr3_list 우선
    addr3_list: list[str] = Field(default_factory=list)
    addr4_list: list[str] = Field(default_factory=list)
    ri_list: list[RiPick] = Field(default_factory=list)
    # 교차 시군구 인접 복수: 명시 행정코드 (있으면 addr leaf 필터보다 우선)
    region_codes: list[str] = Field(default_factory=list)
    region_code_level: Optional[RegionCodeLevel] = None
    # '시도|시군구|읍면동' — 코드 NULL 원장 행 포함용
    region_addrs: list[str] = Field(default_factory=list)
    contract_year_from: Optional[int] = None
    contract_year_to: Optional[int] = None
    as_of_month: Optional[str] = None
    window_years: Optional[int] = None
    zone_types: list[str] = Field(default_factory=list)
    building_uses: list[str] = Field(default_factory=list)
    road_width_labels: list[str] = Field(default_factory=list)
    gross_area_min: Optional[float] = None
    gross_area_max: Optional[float] = None
    land_area_min: Optional[float] = None
    land_area_max: Optional[float] = None
    building_age_min: Optional[float] = None
    building_age_max: Optional[float] = None
    road_code_min: Optional[float] = None
    road_code_max: Optional[float] = None
    variables: RegressionVariableSpec = Field(default_factory=RegressionVariableSpec)
    response_scale: ResponseScale = "linear"
    compare_admin_levels: bool = True  # 하위 호환 — 엔진이 선택 깊이로 자동 결정
    leaf_level: Optional[Literal["addr3", "addr4"]] = None
    exclude_outliers_iqr: bool = False
    outlier_iqr_multiplier: float = 3.0

    @field_validator("outlier_iqr_multiplier")
    @classmethod
    def _check_iqr_multiplier(cls, v: float) -> float:
        for allowed in (1.5, 2.0, 3.0):
            if math.isclose(float(v), allowed, rel_tol=0, abs_tol=1e-9):
                return allowed
        raise ValueError("outlier_iqr_multiplier는 1.5, 2, 3 중 하나여야 합니다.")


class RegressionCoeff(BaseModel):
    name: str
    estimate: float
    std_err: Optional[float] = None
    t_value: Optional[float] = None
    p_value: Optional[float] = None


class VifEntry(BaseModel):
    """연속 독립변수 VIF (더미 제외)."""

    name: str
    vif: Optional[float] = None


class ContinuousRange(BaseModel):
    name: str
    min: Optional[float] = None
    max: Optional[float] = None


class PredictOptions(BaseModel):
    """예측 입력 폼용 — 해당 scope 모형 기준."""

    zone_types: list[str] = Field(default_factory=list)
    building_uses: list[str] = Field(default_factory=list)
    road_width_labels: list[str] = Field(default_factory=list)
    asset_types: list[str] = Field(default_factory=list)
    zone_reference: Optional[str] = None
    building_use_reference: Optional[str] = None
    road_width_reference: Optional[str] = None
    asset_type_reference: Optional[str] = None
    region_leaves: list[str] = Field(default_factory=list)
    region_reference: Optional[str] = None
    continuous: list[ContinuousRange] = Field(default_factory=list)


class RegressionLevelResult(BaseModel):
    admin_level: AdminLevel
    scope_label: Optional[str] = None
    n: int
    r_squared: Optional[float] = None
    adj_r_squared: Optional[float] = None
    f_statistic: Optional[float] = None
    f_p_value: Optional[float] = None
    significant_count: int = 0
    equation: str
    coefficients: list[RegressionCoeff]
    vif: list[VifEntry] = Field(default_factory=list)
    vif_warning: Optional[str] = None
    predict_options: Optional[PredictOptions] = None
    warning: Optional[str] = None
    mape: Optional[float] = None  # in-sample MAPE (%), 원척도 금액(만원)


class CorrelationPoint(BaseModel):
    x: float
    y: float


class CorrelationSeries(BaseModel):
    variable: str
    label: str
    pearson_r: Optional[float] = None
    points: list[CorrelationPoint]
    y_axis_label: Optional[str] = None


class PartialRegressionSeries(BaseModel):
    """Added-variable plot — 모형 통제변수 제거 후 잔차 vs 잔차."""

    variable: str
    label: str
    points: list[CorrelationPoint]
    beta: Optional[float] = None
    p_value: Optional[float] = None
    partial_r_squared: Optional[float] = None
    x_axis_label: Optional[str] = None
    y_axis_label: Optional[str] = None


class RegressionRunResponse(BaseModel):
    primary: RegressionLevelResult
    comparisons: list[RegressionLevelResult] = Field(default_factory=list)
    focus_admin_level: Optional[AdminLevel] = None
    focus_scope_label: Optional[str] = None
    correlations: list[CorrelationSeries] = Field(default_factory=list)
    partial_regressions: list[PartialRegressionSeries] = Field(default_factory=list)
    correlation_admin_level: Optional[AdminLevel] = None
    correlation_scope_label: Optional[str] = None
    correlation_n: Optional[int] = None
    explain: Optional[AnalysisExplain] = None


class RegressionPredictRequest(RegressionRunRequest):
    admin_level: AdminLevel
    gross_area: Optional[float] = None
    land_area: Optional[float] = None
    building_age: Optional[float] = None
    road_code: Optional[float] = None
    road_width_label: Optional[str] = None
    zone_type: Optional[str] = None
    building_use: Optional[str] = None
    predict_asset_type: Optional[str] = None
    region_leaf: Optional[str] = None


class RegressionPredictResponse(BaseModel):
    admin_level: AdminLevel
    scope_label: Optional[str] = None
    n: int
    y_hat: float
    pi_lower: float
    pi_upper: float
    ci_lower: float
    ci_upper: float
    response_scale: ResponseScale = "linear"
    warnings: list[str] = Field(default_factory=list)
    explain: Optional[AnalysisExplain] = None


class RegressionSelectionRequest(RegressionRunRequest):
    """Group Forward / Best Subset — 후보 블록·랭킹 옵션."""

    candidate_blocks: list[str] = Field(default_factory=list)
    max_candidates: int = 5
    ranking_metric: Literal["aic", "bic", "mape", "adj_r2"] = "aic"


class ExcludedBlockReason(BaseModel):
    code: str
    message: str
    metric_value: Optional[float] = None


class ExcludedBlock(BaseModel):
    block_id: str
    label: str
    reasons: list[ExcludedBlockReason]


class ForwardStepInfo(BaseModel):
    added_block: str
    block_label: str
    aic_before: float
    aic_after: float


class RegressionSuggestResponse(BaseModel):
    recommended_blocks: list[str]
    recommended_variables: RegressionVariableSpec
    response_scale: ResponseScale
    model_comparison: Optional[ModelComparison] = None
    metrics: ModelMetrics
    excluded: list[ExcludedBlock]
    forward_steps: list[ForwardStepInfo] = Field(default_factory=list)
    n: int
    scope_label: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    explain: Optional[AnalysisExplain] = None


class ModelCandidate(BaseModel):
    rank: int
    blocks: list[str]
    variables: RegressionVariableSpec
    response_scale: ResponseScale
    metrics: ModelMetrics
    model_comparison: Optional[ModelComparison] = None
    aic: Optional[float] = None
    bic: Optional[float] = None


class RegressionCompareResponse(BaseModel):
    candidates_by_aic: list[ModelCandidate]
    candidates_by_bic: list[ModelCandidate]
    candidates_by_mape: list[ModelCandidate]
    n: int
    scope_label: Optional[str] = None
    total_subsets: int = 0
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)
    explain: Optional[AnalysisExplain] = None
