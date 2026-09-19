"""복합부동산 API 스키마."""

from __future__ import annotations

import math
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.ai.schemas import AnalysisExplain
from app.collective.schemas import ModelComparison, ModelMetrics
from app.recommendation.models import (
    AnalysisRegionUnitHint,
    AnalysisScope,
    CoefficientNarrative,
    DiagnosticCheckItem,
    RecommendationConclusion,
    TerminationInfo,
)
from app.recommendation.twin_structure import TwinExperimentStep

# 단일 / 통합(all) / 복수("commercial,factory")
AssetType = str
ResponseScale = Literal["linear", "log", "loglog"]
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
    is_partial_ownership: bool = False
    partial_ownership_label: Optional[str] = None
    structure_group: Optional[str] = None
    recovered_lot: Optional[str] = None
    match_tier: Optional[str] = None
    match_rule: Optional[str] = None
    zone_type_ledger: Optional[str] = None
    zone_source: Optional[str] = None


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
    partial_tx_count: int = 0


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
    structure_dummy: bool = True
    asset_type_dummy: bool = True
    # 읍·면·동 초점에서는 addr3/addr4, 법정리 초점에서는 addr5 기준
    region_leaf_dummy: bool = False
    # 지역 프로필 공변량 (쌍둥이 로직 보강 · 기본 off)
    region_population: bool = False
    region_land_p50: bool = False
    region_apt_p50: bool = False
    region_apt_n: bool = False
    region_comm_p50: bool = False
    region_comm_n: bool = False


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
    # 시점 보정 (D-075) — **기본 off, 제품 경로에서 쓰지 않는다.**
    # 켜면 시군구 지수로 거래가를 기준시점 수준으로 환산한 뒤 적합한다. 5년 창 실측에서
    # adj R²·MAPE 개선 근거가 없는데 가격 수준은 20~37% 움직였고, 그 이동은 CV로 검증할
    # 방법이 없다. 창을 늘리거나 시도 단위로 지수 잡음을 줄인 뒤 재검토한다.
    time_adjust: bool = False
    include_partial: bool = False  # D-049 분석 기본 제외. 목록과 분리.
    enrich: bool = False  # D-051. 기본 끄기. 켜면 표시 용도지역=필터.
    # R0 analysis_scope — 프론트 analysisUnits 미러 (필터 로직에는 미사용)
    anchor_region_code: Optional[str] = None
    region_unit_hints: list[AnalysisRegionUnitHint] = Field(default_factory=list)

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


class FunnelReason(BaseModel):
    code: str
    label: str
    n: int


class FunnelStep(BaseModel):
    """조회 표본 → 적합 표본. drop 은 펼치면 사유별 건수."""

    code: str
    label: str
    n: int
    kind: Literal["remain", "drop"] = "remain"
    note: Optional[str] = None
    reasons: list[FunnelReason] = Field(default_factory=list)


class SampleBreakdown(BaseModel):
    n_pool: int
    n_fit: int
    funnel: list[FunnelStep] = Field(default_factory=list)


class PredictOptions(BaseModel):
    """예측 입력 폼용 — 해당 scope 모형 기준."""

    zone_types: list[str] = Field(default_factory=list)
    building_uses: list[str] = Field(default_factory=list)
    structure_groups: list[str] = Field(default_factory=list)
    road_width_labels: list[str] = Field(default_factory=list)
    asset_types: list[str] = Field(default_factory=list)
    zone_reference: Optional[str] = None
    building_use_reference: Optional[str] = None
    structure_reference: Optional[str] = None
    road_width_reference: Optional[str] = None
    asset_type_reference: Optional[str] = None
    region_leaves: list[str] = Field(default_factory=list)
    region_reference: Optional[str] = None
    continuous: list[ContinuousRange] = Field(default_factory=list)


class CorrelationPoint(BaseModel):
    x: float
    y: float


class ResidualGroup(BaseModel):
    """한 집단(용도지역 하나, 연식 구간 하나 등)의 잔차 요약."""

    label: str
    n: int
    bias_pct: float  # 중위 부호 오차. 양수 = 모형이 과소평가
    # 그 집단 중위 − 나머지 표본 중위. **화면에서 읽어야 할 숫자.** 전체가 공통으로 가진
    # 치우침이 빠져 있어 「이 집단만 다르게 틀리는 정도」를 나타낸다.
    excess_bias_pct: float = 0.0
    mape_pct: float  # 평균 절대 오차 = 그 집단의 MAPE (화면 상단 MAPE와 같은 정의)
    p_value: Optional[float] = None  # 그 집단 vs 나머지 Mann–Whitney (양측)
    # p < 0.05. False면 나머지와 다르게 틀린다고 볼 근거가 없다는 뜻.
    significant: bool = False


class ResidualGroupSet(BaseModel):
    """한 축(지역·용도지역·연식 구간 …)의 집단별 편향."""

    key: str
    label: str
    groups: list[ResidualGroup] = Field(default_factory=list)
    omitted_n: int = 0  # 최소 건수 미달·분류 불가·상한 초과로 표에서 빠진 건수
    trimmed: bool = False


class ResidualScaleBin(BaseModel):
    """적합값 분위별 오차 산포 — 이분산을 숫자로 확인하는 쪽."""

    label: str
    n: int
    fitted_median: float
    abs_pct_median: float
    spread_pct: float


class InfluentialTransaction(BaseModel):
    """Cook 거리 상위 거래 — 「이 몇 건이 결과를 끌고 있다」."""

    rank: int
    label: str
    contract_year: Optional[int] = None
    zone_type: Optional[str] = None
    price: float
    predicted: float
    error_pct: Optional[float] = None
    gross_area: Optional[float] = None
    land_area: Optional[float] = None
    building_age: Optional[float] = None
    cooks_d: float
    leverage: Optional[float] = None


class CoefficientShift(BaseModel):
    """영향 상위 거래를 뺀 재적합에서의 계수 변화.

    변화 크기는 **표준오차 배수**(`shift_se`)로 잰다. 계수 스케일이 서로 다르고 0 근처
    계수는 백분율이 폭발한다. 1 SE를 넘으면 소수 거래가 계수를 실질적으로 끌고 있다는 뜻.
    """

    name: str
    before: float
    after: float
    shift_se: Optional[float] = None
    shift_pct: Optional[float] = None


class ResidualDiagnostics(BaseModel):
    """잔차 진단 (P5). 초점 모형에만 붙는다 — 상위 비교에는 이 화면이 없다."""

    n: int
    residual_definition: str
    bias_pct: float  # 중위 오차% — 치우침은 이걸로 읽는다
    mean_bias_pct: Optional[float] = None  # 평균 오차% (참고). 작은 거래 쪽으로 끌린다
    bias_note: Optional[str] = None
    points: list[CorrelationPoint] = Field(default_factory=list)  # x=예측금액, y=오차%
    scale_bins: list[ResidualScaleBin] = Field(default_factory=list)
    het_p_value: Optional[float] = None
    het_note: Optional[str] = None
    groups: list[ResidualGroupSet] = Field(default_factory=list)
    influential: list[InfluentialTransaction] = Field(default_factory=list)
    refit_shifts: list[CoefficientShift] = Field(default_factory=list)
    refit_note: Optional[str] = None
    warning: Optional[str] = None


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
    sample: Optional[SampleBreakdown] = None
    residuals: Optional[ResidualDiagnostics] = None  # 초점 모형만 (P5)


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
    analysis_scope: Optional[AnalysisScope] = None
    explain: Optional[AnalysisExplain] = None
    include_partial: bool = False
    partial_tx_count: int = 0
    partial_n_note: Optional[str] = None


class RegressionScopeResponse(BaseModel):
    analysis_scope: AnalysisScope


class RecommendationSatisfaction(BaseModel):
    grade: str = "pending"
    stars: int = Field(default=0, ge=0, le=5)
    # 등급 판정에 쓴 CV — 탐색·확인 중 나쁜 쪽 (D-074)
    cv_mape: Optional[float] = None
    label_ko: Optional[str] = None
    # 어느 쪽이 나빴는지: "search" | "confirm"
    grade_basis: Optional[str] = None


class RecommendationStage1(BaseModel):
    candidates_explanatory: list[ModelCandidate] = Field(default_factory=list)
    candidates_predictive: list[ModelCandidate] = Field(default_factory=list)
    primary: ModelCandidate
    alternate: Optional[ModelCandidate] = None
    selection_n: int = 0
    fit_n: int = 0
    candidate_pool: list[str] = Field(default_factory=list)
    satisfaction: RecommendationSatisfaction = Field(default_factory=RecommendationSatisfaction)
    total_subsets: int = 0
    truncated: bool = False
    # 1위 모형만 마지막 연도를 떼어 다시 잰 CV. 탐색 CV는 수백 조합의 최소값이라
    # 낙관적이므로, 고를 때 쓴 지표와 보고하는 지표를 분리한다.
    primary_confirm_cv_mape: Optional[float] = None
    primary_confirm_cv_folds: int = 0
    primary_confirm_note: Optional[str] = None
    # 안정성 진단 (D-074). 순위에는 쓰지 않는다. extreme_rate가 높으면 학습 범위를
    # 크게 벗어난 예측이 많다는 뜻이고, median과 평균이 크게 벌어지면 소수 관측이
    # 지표를 끌고 있다는 뜻이다.
    primary_cv_extreme_rate: Optional[float] = None
    primary_cv_median_ape: Optional[float] = None


class RecommendationPoolCandidate(BaseModel):
    candidate_id: str
    label: str
    n: int
    region_codes: list[str] = Field(default_factory=list)
    adj_r_squared: Optional[float] = None
    mape: Optional[float] = None
    cv_mape: Optional[float] = None
    cv_mape_delta: Optional[float] = None
    confirm_cv_mape: Optional[float] = None
    blocks: list[str] = Field(default_factory=list)
    response_scale: Optional[ResponseScale] = None
    variables: Optional[RegressionVariableSpec] = None
    prefix_k: int = 0
    key_coefficients: dict[str, float] = Field(default_factory=dict)
    structure_score: Optional[float] = None


class TwinValidationVerdict(BaseModel):
    """Local vs Twin 접두 실험 판정. 탐색 CV로 고르고 확인 CV로 권고."""

    verdict: Literal["improved", "tie", "worse", "skipped"]
    label_ko: str
    summary_ko: str
    epsilon_pp: float = 0.5
    practical_band_pp: Optional[float] = None
    local_cv_mape: Optional[float] = None
    compared_cv_mape: Optional[float] = None
    cv_mape_delta: Optional[float] = None
    local_confirm_cv_mape: Optional[float] = None
    compared_confirm_cv_mape: Optional[float] = None
    compared_candidate_id: Optional[str] = None
    twin_adopt_recommended: bool = False
    confirm_skipped_reason: Optional[str] = None


class RecommendationStage2(BaseModel):
    ran: bool = False
    skipped_reason: Optional[str] = None
    pools: list[RecommendationPoolCandidate] = Field(default_factory=list)
    primary: Optional[RecommendationPoolCandidate] = None
    local_cv_mape: Optional[float] = None
    twin_gates: list[TwinGateResult] = Field(default_factory=list)
    decision: str = "local"
    decision_reason: Optional[str] = None
    twin_validation: Optional[TwinValidationVerdict] = None
    fixed_blocks: list[str] = Field(default_factory=list)
    fixed_response_scale: ResponseScale = "linear"
    recommended_blocks: list[str] = Field(default_factory=list)
    # Lab: Stage2 탐색 풀에 올린 region_* (coverage 전·후 포함 후보 기록)
    region_candidate_blocks: list[str] = Field(default_factory=list)
    region_feature_tier: Optional[str] = None
    local_search_cv_mape: Optional[float] = None
    local_confirm_cv_mape: Optional[float] = None
    region_effect: Optional[str] = None
    twin_experiments: list[TwinExperimentStep] = Field(default_factory=list)
    # Twin1 예측용: Local 식 + region_leaf · 쌍둥이 1위 표본 (채택 여부와 무관)
    inspect_pool: Optional[RecommendationPoolCandidate] = None
    # Twin 실험2: Local + Twin 1위 표본에서 예측형 식을 다시 고름 (확인용)
    research: Optional[RecommendationPoolCandidate] = None
    research_ran: bool = False
    research_skipped_reason: Optional[str] = None


class RegressionRecommendResponse(BaseModel):
    analysis_scope: AnalysisScope
    stage1: RecommendationStage1
    stage2: Optional[RecommendationStage2] = None
    termination: TerminationInfo
    conclusion: RecommendationConclusion
    diagnostics_checklist: list[DiagnosticCheckItem] = Field(default_factory=list)
    coefficient_narratives: list[CoefficientNarrative] = Field(default_factory=list)
    narrative_hints: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
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
    structure_group: Optional[str] = None
    predict_asset_type: Optional[str] = None
    region_leaf: Optional[str] = None


class ContinuousExtrapolation(BaseModel):
    name: str
    label: str
    min: float
    max: float
    value: float
    level: int = 0
    bound_ratio: float = 1.0


class RegressionPredictResponse(BaseModel):
    admin_level: AdminLevel
    scope_label: Optional[str] = None
    n: int
    y_hat: float
    pi_lower: float
    pi_upper: float
    ci_lower: float
    ci_upper: float
    # log 계열에서 점추정·평균CI에 곱한 Duan smearing 계수 (D-074). 선형이면 None.
    duan_factor: Optional[float] = None
    # 추정값의 기준시점 (D-075). 시점 보정을 못 했으면 None — 창 기간의 명목 평균 수준.
    price_base_year: Optional[int] = None
    response_scale: ResponseScale = "linear"
    extrapolation_level: int = 0
    y_hat_suppressed: bool = False
    continuous_assessments: list[ContinuousExtrapolation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    explain: Optional[AnalysisExplain] = None


class RegressionSelectionRequest(RegressionRunRequest):
    """Group Forward / Best Subset — 후보 블록·랭킹 옵션."""

    candidate_blocks: list[str] = Field(default_factory=list)
    max_candidates: int = 5
    ranking_metric: Literal["aic", "bic", "mape", "adj_r2"] = "aic"
    profile_version: Optional[str] = None
    profile_as_of_month: Optional[str] = None
    profile_window_years: Optional[int] = None
    profile_twin_neighbors: list[dict[str, object]] = Field(default_factory=list)
    run_stage2: bool = False
    run_stage2_research: bool = False
    # Lab/실험: 지역 프로필 공변량을 후보 풀에 추가 (제품 기본 경로 off)
    include_region_features: bool = False
    # include_region_features 시 후보 세트: price=가격수준만 · full=가격+인구·거래량
    region_feature_tier: Literal["price", "full"] = "full"


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


class CandidateValidationSummary(BaseModel):
    candidate_id: str
    accepted: bool
    checks: dict[str, bool] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class JointFTest(BaseModel):
    """더미·변수 블록 전체의 추가 설명력 검정."""

    f_statistic: Optional[float] = None
    p_value: Optional[float] = None
    df_restriction: Optional[int] = None
    df_resid: Optional[int] = None
    tested: bool = False


class PoolingCandidateMetrics(BaseModel):
    """Local 또는 Twin 접두 실험 후보.

    candidate_id는 "local" 또는 "twin_prefix_k{k}".
    cv_mape는 Stage2 diagnose에서 탐색 CV(마지막 연도 제외). Lab optimize도 동일 필드.
    """

    candidate_id: str
    label: str
    n: int
    region_codes: list[str] = Field(default_factory=list)
    adj_r_squared: Optional[float] = None
    mape: Optional[float] = None
    cv_mape: Optional[float] = None
    cv_folds: Optional[int] = None
    confirm_cv_mape: Optional[float] = None
    confirm_cv_folds: Optional[int] = None
    aic: Optional[float] = None
    bic: Optional[float] = None
    joint_f_tests: dict[str, JointFTest] = Field(default_factory=dict)
    blocks: list[str] = Field(default_factory=list)
    response_scale: Optional[ResponseScale] = None
    prefix_k: int = 0
    key_coefficients: dict[str, float] = Field(default_factory=dict)


class DecisionConfidence(BaseModel):
    """1위·2위 후보 간 성능 격차 기반 신뢰도 — CANDIDATE_EVALUATION_DESIGN §5.4 1차 구현.

    임계값은 초기 휴리스틱이며 운영 데이터가 쌓이면 재보정할 계획이다.
    """

    stars: int = Field(ge=1, le=5)
    grade: str
    metric_gap_pct: Optional[float] = None
    note: Optional[str] = None


class TwinGateResult(BaseModel):
    """Twin 개별 후보 지역의 Pooling hard gate 결과(V2).

    price_gate=None은 표본 부족으로 가격수준 검증을 생략했다는 뜻이며,
    이 경우 가격수준 gate는 실패로 간주하지 않는다(데이터 결측을 불합격으로
    오판하지 않기 위함 — CH2 Macro의 명시적 결측 처리 원칙).
    """

    region_code: str
    rank: Optional[int] = None
    similarity_score: Optional[float] = None
    price_ratio: Optional[float] = None
    price_gate: Optional[bool] = None
    adjacency_gate: bool = True
    accepted: bool
    reasons: list[str] = Field(default_factory=list)


class PoolingEvaluation(BaseModel):
    """Local vs Twin Pooling 실측 비교 — '후보는 제안, Validation이 선택'을 API로 구현.

    V2: 검증 통과 Twin 후보에 가격수준·인접성 hard gate를 적용해 걸러내고,
    남은 Twin으로 복수 pool 조합(상위 1개/상위 3개/전체)을 만들어 Local과
    함께 경쟁시킨다. decision은 승자 candidate_id("local" 또는
    "twin_pool_n{k}")를 그대로 담는다.
    """

    candidates: list[PoolingCandidateMetrics] = Field(default_factory=list)
    decision: str
    decision_reason: str
    decision_confidence: Optional[DecisionConfidence] = None
    twin_gates: list[TwinGateResult] = Field(default_factory=list)


class RegressionSuggestResponse(BaseModel):
    deprecated: bool = True
    successor_path: str = "/built/regression/recommend"
    recommended_blocks: list[str]
    recommended_variables: RegressionVariableSpec
    response_scale: ResponseScale
    model_comparison: Optional[ModelComparison] = None
    metrics: ModelMetrics
    excluded: list[ExcludedBlock]
    forward_steps: list[ForwardStepInfo] = Field(default_factory=list)
    n: int
    selection_n: int = 0
    candidate_union_variables: list[str] = Field(default_factory=list)
    validation_contract_version: Optional[str] = None
    joint_f_tests: dict[str, JointFTest] = Field(default_factory=dict)
    candidate_validations: list[CandidateValidationSummary] = Field(default_factory=list)
    pooling_evaluation: Optional[PoolingEvaluation] = None
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
    joint_f_tests: dict[str, JointFTest] = Field(default_factory=dict)
    coefficients: list[RegressionCoeff] = Field(default_factory=list)


class RegressionCompareResponse(BaseModel):
    deprecated: bool = True
    successor_path: str = "/built/regression/recommend"
    candidates_by_aic: list[ModelCandidate]
    candidates_by_bic: list[ModelCandidate]
    candidates_by_mape: list[ModelCandidate]
    candidates_by_cv_mape: list[ModelCandidate] = Field(default_factory=list)
    n: int
    selection_n: int = 0
    candidate_union_variables: list[str] = Field(default_factory=list)
    validation_contract_version: Optional[str] = None
    candidate_validations: list[CandidateValidationSummary] = Field(default_factory=list)
    pooling_evaluation: Optional[PoolingEvaluation] = None
    scope_label: Optional[str] = None
    total_subsets: int = 0
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)
    explain: Optional[AnalysisExplain] = None
