export type BuiltAssetKind = "commercial" | "factory" | "detached";
/** API asset_type: 단일 / "commercial,factory" / "all" */
export type AssetType = BuiltAssetKind | "all" | (string & {});
export type ResponseScale = "linear" | "log" | "loglog";

export interface BuiltTransactionRow {
  id: number;
  asset_type: string;
  addr1?: string | null;
  addr2?: string | null;
  addr3?: string | null;
  addr4?: string | null;
  addr5?: string | null;
  lot_number?: string | null;
  display_address?: string | null;
  road_name?: string | null;
  road_width_label?: string | null;
  deal_type?: string | null;
  trade_year_label?: string | null;
  contract_year?: number | null;
  contract_month?: number | null;
  contract_date?: string | null;
  zone_type?: string | null;
  building_use?: string | null;
  building_scale?: number | null;
  land_scale?: number | null;
  age_bucket?: number | null;
  price: number;
  gross_area?: number | null;
  land_area?: number | null;
  building_age?: number | null;
  building_year?: number | null;
  buyer_type?: string | null;
  seller_type?: string | null;
  road_code?: number | null;
  is_partial_ownership?: boolean;
  partial_ownership_label?: string | null;
  structure_group?: string | null;
  recovered_lot?: string | null;
  match_tier?: string | null;
}

export interface BuiltTransactionListResponse {
  total: number;
  page: number;
  page_size: number;
  items: BuiltTransactionRow[];
}

export interface BuiltFilterMeta {
  asset_types: string[];
  contract_years: number[];
  zone_types: string[];
  building_uses: string[];
  road_width_labels: string[];
  addr1_list: string[];
  as_of_month?: string | null;
  default_window_years: number;
}

export interface RegressionVariableSpec {
  gross_area: boolean;
  land_area: boolean;
  building_age: boolean;
  road_width_dummy: boolean;
  road_code: boolean;
  zone_type_dummy: boolean;
  building_use_dummy: boolean;
  structure_dummy: boolean;
  asset_type_dummy: boolean;
  region_leaf_dummy: boolean;
}

export interface Addr3Option {
  name: string;
  count: number;
  disabled?: boolean;
  min_reliable_count?: number;
}

export interface RegionStructure {
  has_intermediate: boolean;
  intermediate_label?: string | null;
  leaf_level: string;
  has_ri?: boolean;
  tx_count?: number;
}

export interface RegionOption {
  name: string;
  count: number;
  parent?: string | null;
  disabled?: boolean;
  min_reliable_count?: number;
}

export interface RiPick {
  eup: string;
  ri: string;
}

export type IqrMultiplier = 1.5 | 2 | 3;

export interface AnalysisRegionUnitHint {
  code: string;
  level: "eupmyeondong" | "beopjungri";
  name: string;
  addr1: string;
  addr2: string;
  eup?: string;
  cross_parent: boolean;
}

export interface AnalysisTimeScope {
  as_of_month?: string | null;
  window_years?: number | null;
  contract_year_from?: number | null;
  contract_year_to?: number | null;
}

export interface AnalysisSampleFilters {
  zone_types: string[];
  building_uses: string[];
  road_width_labels: string[];
  gross_area_min?: number | null;
  gross_area_max?: number | null;
  land_area_min?: number | null;
  land_area_max?: number | null;
  building_age_min?: number | null;
  building_age_max?: number | null;
  road_code_min?: number | null;
  road_code_max?: number | null;
  exclude_outliers_iqr: boolean;
  outlier_iqr_multiplier: number;
  include_partial?: boolean;
}

export interface RegionUnitRef {
  code: string;
  level: "eupmyeondong" | "beopjungri";
  name: string;
  addr1: string;
  addr2: string;
  eup?: string | null;
  cross_parent: boolean;
}

export interface AnalysisScope {
  domain: "built";
  asset_slice: string;
  region_units: RegionUnitRef[];
  anchor_unit?: RegionUnitRef | null;
  time: AnalysisTimeScope;
  sample_filters: AnalysisSampleFilters;
  scope_label: string;
  admin_level: "sigungu" | "gu" | "eupmyeondong" | "beopjungri";
  region_codes: string[];
  region_code_level?: "eupmyeondong" | "beopjungri" | null;
  region_addrs: string[];
  scope_n_tx: number;
  include_partial?: boolean;
  partial_tx_count?: number;
  partial_n_note?: string | null;
}

export interface RegressionScopeResponse {
  analysis_scope: AnalysisScope;
}

export interface TerminationInfo {
  stage_reached: number;
  action: "stop" | "proceed_twin";
  grade: string;
  reasons: string[];
  next_stage_hint?: string | null;
  recommended_pool?: string | null;
}

export interface RecommendationSatisfaction {
  grade: string;
  stars: number;
  cv_mape?: number | null;
}

export interface RecommendationStage1 {
  candidates_explanatory: ModelCandidate[];
  candidates_predictive: ModelCandidate[];
  primary: ModelCandidate;
  alternate?: ModelCandidate | null;
  selection_n: number;
  fit_n: number;
  candidate_pool: string[];
  satisfaction: RecommendationSatisfaction;
  total_subsets: number;
  truncated: boolean;
}

export interface RecommendationPoolCandidate {
  candidate_id: string;
  label: string;
  n: number;
  region_codes: string[];
  adj_r_squared?: number | null;
  mape?: number | null;
  cv_mape?: number | null;
  cv_mape_delta?: number | null;
  blocks?: string[];
  response_scale?: ResponseScale | null;
  variables?: RegressionVariableSpec | null;
}

export type TwinValidationVerdictKind = "improved" | "tie" | "worse" | "skipped";

export interface TwinValidationVerdict {
  verdict: TwinValidationVerdictKind;
  label_ko: string;
  summary_ko: string;
  epsilon_pp: number;
  local_cv_mape?: number | null;
  compared_cv_mape?: number | null;
  cv_mape_delta?: number | null;
  compared_candidate_id?: string | null;
  twin_adopt_recommended: boolean;
}

export interface RecommendationStage2 {
  ran: boolean;
  skipped_reason?: string | null;
  pools: RecommendationPoolCandidate[];
  primary?: RecommendationPoolCandidate | null;
  local_cv_mape?: number | null;
  twin_gates: TwinGateResult[];
  decision: string;
  decision_reason?: string | null;
  twin_validation?: TwinValidationVerdict | null;
  fixed_blocks: string[];
  fixed_response_scale: ResponseScale;
  recommended_blocks?: string[];
}

export type RecommendationVerdict =
  | "adopt_predictive"
  | "caution"
  | "no_predictive_model"
  | "explanatory_only";

export type RecommendationAdoptMode = "predictive" | "review_only" | "explanatory";

export interface ConclusionBullet {
  kind: "positive" | "negative" | "neutral";
  text: string;
}

export interface RecommendedAction {
  action_id: string;
  kind: "do" | "dont" | "optional";
  label_ko: string;
}

export interface RecommendationConclusion {
  verdict: RecommendationVerdict;
  headline_ko: string;
  final_verdict_ko: string;
  final_verdict_tone: "positive" | "warning" | "negative";
  final_verdict_emoji: string;
  final_verdict_sublines: string[];
  bullets: ConclusionBullet[];
  summary_ko: string;
  recommended_actions: RecommendedAction[];
  cv_fitness?: CvFitnessTier | null;
  cv_mape?: number | null;
  twin_available: boolean;
  twin_recommended: boolean;
  twin_ran: boolean;
  adopt_mode: RecommendationAdoptMode;
}

export interface CvFitnessTier {
  tier: string;
  label_ko: string;
  tone: "positive" | "neutral" | "warning" | "negative";
  max_cv_mape?: number | null;
}

export interface RegressionRecommendResponse {
  analysis_scope: AnalysisScope;
  stage1: RecommendationStage1;
  stage2?: RecommendationStage2 | null;
  termination: TerminationInfo;
  conclusion: RecommendationConclusion;
  diagnostics_checklist: DiagnosticCheckItem[];
  coefficient_narratives: CoefficientNarrative[];
  narrative_hints: string[];
  warnings: string[];
  explain?: AnalysisExplain | null;
}

export interface DiagnosticCheckItem {
  check_id: string;
  label_ko: string;
  status: "ok" | "warn" | "fail";
  summary_ko: string;
}

export interface CoefficientNarrative {
  name: string;
  label_ko: string;
  text_ko: string;
  significant: boolean;
  is_top_contributor: boolean;
}

export interface RegressionRunRequest {
  asset_type: AssetType;
  addr1?: string;
  addr2?: string;
  addr3?: string;
  addr3_list?: string[];
  addr4_list?: string[];
  ri_list?: RiPick[];
  /** 교차 시군구 인접 복수 — 있으면 leaf addr 필터보다 우선 */
  region_codes?: string[];
  region_code_level?: "eupmyeondong" | "beopjungri";
  /** '시도|시군구|읍면동' — 행정코드 NULL 원장 행 포함 */
  region_addrs?: string[];
  contract_year_from?: number;
  contract_year_to?: number;
  as_of_month?: string;
  window_years?: number;
  zone_types?: string[];
  building_uses?: string[];
  road_width_labels?: string[];
  gross_area_min?: number;
  gross_area_max?: number;
  land_area_min?: number;
  land_area_max?: number;
  building_age_min?: number;
  building_age_max?: number;
  road_code_min?: number;
  road_code_max?: number;
  variables: RegressionVariableSpec;
  response_scale?: ResponseScale;
  compare_admin_levels?: boolean;
  leaf_level?: "addr3" | "addr4";
  exclude_outliers_iqr: boolean;
  outlier_iqr_multiplier?: number;
  include_partial?: boolean;
  /** R0 — analysis_scope anchor (analysisUnits[0] non-crossParent) */
  anchor_region_code?: string;
  region_unit_hints?: AnalysisRegionUnitHint[];
}

export interface ScopeSampleFilterResponse {
  total: number;
  zone_types: { name: string; count: number }[];
  building_uses: { name: string; count: number }[];
  road_width_labels: { name: string; count: number }[];
  continuous: { name: string; min?: number | null; max?: number | null }[];
}

export interface SampleFilterState {
  zoneTypes: string[];
  buildingUses: string[];
  roadWidthLabels: string[];
  gross_area_min: string;
  gross_area_max: string;
  land_area_min: string;
  land_area_max: string;
  building_age_min: string;
  building_age_max: string;
}

export const EMPTY_SAMPLE_FILTER: SampleFilterState = {
  zoneTypes: [],
  buildingUses: [],
  roadWidthLabels: [],
  gross_area_min: "",
  gross_area_max: "",
  land_area_min: "",
  land_area_max: "",
  building_age_min: "",
  building_age_max: "",
};

export interface RegressionCoeff {
  name: string;
  estimate: number;
  std_err?: number | null;
  t_value?: number | null;
  p_value?: number | null;
}

export interface AnalysisExplainPreset {
  id: string;
  question: string;
  answer: string;
}

export interface AnalysisExplain {
  spec_id: string;
  spec_version: string;
  title: string;
  summary: string;
  formula?: string | null;
  index_rule?: string | null;
  reference?: string | null;
  floor_groups?: string[];
  controls?: string[];
  interpretation: string[];
  limitations: string[];
  interpretation_hints: string[];
  presets: AnalysisExplainPreset[];
}

export interface VifEntry {
  name: string;
  vif?: number | null;
}

export interface PredictOptions {
  zone_types: string[];
  building_uses: string[];
  structure_groups?: string[];
  road_width_labels: string[];
  asset_types: string[];
  zone_reference?: string | null;
  building_use_reference?: string | null;
  structure_reference?: string | null;
  road_width_reference?: string | null;
  asset_type_reference?: string | null;
  region_leaves?: string[];
  region_reference?: string | null;
  continuous: { name: string; min?: number | null; max?: number | null }[];
}

export interface FunnelReason {
  code: string;
  label: string;
  n: number;
}

export interface FunnelStep {
  code: string;
  label: string;
  n: number;
  kind: "remain" | "drop";
  note?: string | null;
  reasons?: FunnelReason[];
}

export interface SampleBreakdown {
  n_pool: number;
  n_fit: number;
  funnel: FunnelStep[];
}

export interface RegressionLevelResult {
  admin_level: "sigungu" | "gu" | "eupmyeondong" | "beopjungri";
  scope_label?: string | null;
  n: number;
  r_squared?: number | null;
  adj_r_squared?: number | null;
  f_statistic?: number | null;
  f_p_value?: number | null;
  significant_count: number;
  equation: string;
  coefficients: RegressionCoeff[];
  vif?: VifEntry[];
  vif_warning?: string | null;
  predict_options?: PredictOptions | null;
  warning?: string | null;
  mape?: number | null;
  sample?: SampleBreakdown | null;
}

export interface CorrelationPoint {
  x: number;
  y: number;
}

export interface CorrelationSeries {
  variable: string;
  label: string;
  pearson_r?: number | null;
  points: CorrelationPoint[];
  y_axis_label?: string | null;
}

export interface PartialRegressionSeries {
  variable: string;
  label: string;
  points: CorrelationPoint[];
  beta?: number | null;
  p_value?: number | null;
  partial_r_squared?: number | null;
  x_axis_label?: string | null;
  y_axis_label?: string | null;
}

export interface RegressionRunResponse {
  primary: RegressionLevelResult;
  comparisons: RegressionLevelResult[];
  focus_admin_level?: "sigungu" | "gu" | "eupmyeondong" | "beopjungri" | null;
  focus_scope_label?: string | null;
  correlations: CorrelationSeries[];
  partial_regressions?: PartialRegressionSeries[];
  correlation_admin_level?: "sigungu" | "gu" | "eupmyeondong" | "beopjungri" | null;
  correlation_scope_label?: string | null;
  correlation_n?: number | null;
  analysis_scope?: AnalysisScope | null;
  explain?: AnalysisExplain | null;
  include_partial?: boolean;
  partial_tx_count?: number;
  partial_n_note?: string | null;
}

export interface RegressionPredictRequest extends RegressionRunRequest {
  admin_level: "sigungu" | "gu" | "eupmyeondong" | "beopjungri";
  gross_area?: number;
  land_area?: number;
  building_age?: number;
  road_code?: number;
  road_width_label?: string;
  zone_type?: string;
  building_use?: string;
  structure_group?: string;
  predict_asset_type?: string;
  region_leaf?: string;
}

export interface ContinuousExtrapolation {
  name: string;
  label: string;
  min: number;
  max: number;
  value: number;
  level: number;
  bound_ratio: number;
}

export interface RegressionPredictResponse {
  admin_level: "sigungu" | "gu" | "eupmyeondong" | "beopjungri";
  scope_label?: string | null;
  n: number;
  y_hat: number;
  pi_lower: number;
  pi_upper: number;
  ci_lower: number;
  ci_upper: number;
  response_scale?: ResponseScale;
  extrapolation_level?: number;
  y_hat_suppressed?: boolean;
  continuous_assessments?: ContinuousExtrapolation[];
  warnings: string[];
  explain?: AnalysisExplain | null;
}

export interface ModelMetrics {
  model_type: ResponseScale;
  adj_r_squared?: number | null;
  mape?: number | null;
  rmse?: number | null;
  cv_mape?: number | null;
  cv_folds?: number;
  cv_method?: string | null;
}

export interface ModelComparison {
  log?: ModelMetrics | null;
  linear?: ModelMetrics | null;
  recommended: ResponseScale;
  metric_basis: "cv" | "insample";
  confidence_stars: number;
  confidence_label?: string | null;
}

export interface ExcludedBlockReason {
  code: string;
  message: string;
  metric_value?: number | null;
}

export interface ExcludedBlock {
  block_id: string;
  label: string;
  reasons: ExcludedBlockReason[];
}

export interface ForwardStepInfo {
  added_block: string;
  block_label: string;
  aic_before: number;
  aic_after: number;
}

export interface RegressionSelectionRequest extends RegressionRunRequest {
  candidate_blocks?: string[];
  max_candidates?: number;
  ranking_metric?: "aic" | "bic" | "mape" | "adj_r2";
  profile_version?: string | null;
  profile_as_of_month?: string | null;
  profile_window_years?: number | null;
  profile_twin_neighbors?: ProfileTwinCandidateNeighbor[];
  /** R3.5 — true일 때만 Twin 2단계 실행 (기본 false, 사용자 opt-in) */
  run_stage2?: boolean;
}

export interface CandidateValidationSummary {
  candidate_id: string;
  accepted: boolean;
  checks: Record<string, boolean>;
  reasons: string[];
  warnings: string[];
}

/** Local 또는 Twin Pooling 후보 하나의 실측 지표 — evaluate_pooling_candidates 결과.
 *  candidate_id: "local" 또는 "twin_pool_n{k}"(V2 — pool 조합별). */
export interface PoolingCandidateMetrics {
  candidate_id: string;
  label: string;
  n: number;
  region_codes: string[];
  adj_r_squared?: number | null;
  mape?: number | null;
  cv_mape?: number | null;
  cv_folds?: number | null;
  aic?: number | null;
  bic?: number | null;
  joint_f_tests?: Record<string, JointFTest>;
}

/** 1위·2위 후보 간 성능 격차 기반 신뢰도 — V1 휴리스틱. */
export interface DecisionConfidence {
  stars: number;
  grade: string;
  metric_gap_pct?: number | null;
  note?: string | null;
}

/** Twin 개별 후보 지역의 Pooling hard gate 결과(V2). price_gate=null은 표본 부족으로 생략. */
export interface TwinGateResult {
  region_code: string;
  rank?: number | null;
  similarity_score?: number | null;
  price_ratio?: number | null;
  price_gate?: boolean | null;
  adjacency_gate: boolean;
  accepted: boolean;
  reasons: string[];
}

/** Local vs Twin Pooling(복수 조합) 실측 비교 — "후보는 제안, Validation이 선택"을 API로 구현. */
export interface PoolingEvaluation {
  candidates: PoolingCandidateMetrics[];
  decision: string;
  decision_reason: string;
  decision_confidence?: DecisionConfidence | null;
  twin_gates: TwinGateResult[];
}

/**
 * Regional Profile-native Twin (v21) — GET /api/regional-profile/twins/{eup} · twins-beop/{beop}.
 * Regional Profile Twin algo 21 전용 (`/api/regional-profile/twins*`).
 */
export interface ProfileTwinNeighborItem {
  rank: number;
  twin_eupmyeondong_code?: string | null;
  twin_eupmyeondong_name?: string | null;
  twin_beopjungri_code?: string | null;
  twin_beopjungri_name?: string | null;
  twin_sigungu_code?: string | null;
  twin_sigungu_name: string;
  twin_sido_name: string;
  similarity_score: number;
}

export interface ProfileTwinNeighborsResponse {
  profile_version: string;
  window_years: number;
  algorithm_version: number;
  scope?: string | null;
  as_of_month?: string | null;
  batch_key?: string | null;
  anchor_eupmyeondong_code?: string | null;
  anchor_beopjungri_code?: string | null;
  neighbors: ProfileTwinNeighborItem[];
}

/** RegressionSelectionRequest.profile_twin_neighbors 원소 — Candidate Provider 정규화 계약. */
export interface ProfileTwinCandidateNeighbor {
  region_code: string;
  similarity_score?: number | null;
}

export interface RegressionSuggestResponse {
  recommended_blocks: string[];
  recommended_variables: RegressionVariableSpec;
  response_scale: ResponseScale;
  model_comparison?: ModelComparison | null;
  metrics: ModelMetrics;
  excluded: ExcludedBlock[];
  forward_steps: ForwardStepInfo[];
  n: number;
  selection_n?: number;
  candidate_union_variables?: string[];
  validation_contract_version?: string | null;
  joint_f_tests?: Record<string, JointFTest>;
  candidate_validations?: CandidateValidationSummary[];
  pooling_evaluation?: PoolingEvaluation | null;
  scope_label?: string | null;
  warnings: string[];
  explain?: AnalysisExplain | null;
}

export interface JointFTest {
  f_statistic?: number | null;
  p_value?: number | null;
  df_restriction?: number | null;
  df_resid?: number | null;
  tested: boolean;
}

export interface ModelCandidate {
  rank: number;
  blocks: string[];
  variables: RegressionVariableSpec;
  response_scale: ResponseScale;
  metrics: ModelMetrics;
  model_comparison?: ModelComparison | null;
  aic?: number | null;
  bic?: number | null;
  joint_f_tests?: Record<string, JointFTest>;
  coefficients?: RegressionCoeff[];
}

export interface RegressionCompareResponse {
  candidates_by_aic: ModelCandidate[];
  candidates_by_bic: ModelCandidate[];
  candidates_by_mape: ModelCandidate[];
  candidates_by_cv_mape?: ModelCandidate[];
  n: number;
  selection_n?: number;
  candidate_union_variables?: string[];
  validation_contract_version?: string | null;
  candidate_validations?: CandidateValidationSummary[];
  pooling_evaluation?: PoolingEvaluation | null;
  scope_label?: string | null;
  total_subsets: number;
  truncated: boolean;
  warnings: string[];
  explain?: AnalysisExplain | null;
}
