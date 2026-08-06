"""analysis_scope Pydantic models — built·land·collective 공통 shape (R0)."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.recommendation.cv_fitness import CvFitnessTier

Domain = Literal["built"]
RegionCodeLevel = Literal["eupmyeondong", "beopjungri"]
AdminLevel = Literal["sigungu", "gu", "eupmyeondong", "beopjungri"]
TerminationAction = Literal["stop", "proceed_twin"]
RecommendationVerdict = Literal[
    "adopt_predictive",
    "caution",
    "no_predictive_model",
    "explanatory_only",
]
AdoptMode = Literal["predictive", "review_only", "explanatory"]
ConclusionBulletKind = Literal["positive", "negative", "neutral"]
RecommendedActionKind = Literal["do", "dont", "optional"]
DiagnosticStatus = Literal["ok", "warn", "fail"]


class RegionUnitRef(BaseModel):
    code: str
    level: RegionCodeLevel
    name: str = ""
    addr1: str = ""
    addr2: str = ""
    eup: Optional[str] = None
    cross_parent: bool = False


class AnalysisRegionUnitHint(BaseModel):
    """프론트 analysisUnits 미러 — cross_parent·표시명 보존."""

    code: str
    level: RegionCodeLevel
    name: str = ""
    addr1: str = ""
    addr2: str = ""
    eup: Optional[str] = None
    cross_parent: bool = False


class AnalysisTimeScope(BaseModel):
    as_of_month: Optional[str] = None
    window_years: Optional[int] = None
    contract_year_from: Optional[int] = None
    contract_year_to: Optional[int] = None


class AnalysisSampleFilters(BaseModel):
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
    exclude_outliers_iqr: bool = False
    outlier_iqr_multiplier: float = 3.0


class AnalysisScope(BaseModel):
    domain: Domain = "built"
    asset_slice: str
    region_units: list[RegionUnitRef] = Field(default_factory=list)
    anchor_unit: Optional[RegionUnitRef] = None
    time: AnalysisTimeScope
    sample_filters: AnalysisSampleFilters
    scope_label: str = ""
    admin_level: AdminLevel = "sigungu"
    region_codes: list[str] = Field(default_factory=list)
    region_code_level: Optional[RegionCodeLevel] = None
    region_addrs: list[str] = Field(default_factory=list)
    scope_n_tx: int = 0


class TerminationInfo(BaseModel):
    stage_reached: int = 1
    action: TerminationAction = "stop"
    grade: str = "pending"
    reasons: list[str] = Field(default_factory=list)
    next_stage_hint: Optional[str] = None
    recommended_pool: Optional[str] = None


class ConclusionBullet(BaseModel):
    kind: ConclusionBulletKind
    text: str


class RecommendedAction(BaseModel):
    action_id: str
    kind: RecommendedActionKind
    label_ko: str


class DiagnosticCheckItem(BaseModel):
    check_id: str
    label_ko: str
    status: DiagnosticStatus
    summary_ko: str


class CoefficientNarrative(BaseModel):
    name: str
    label_ko: str
    text_ko: str
    significant: bool = False
    is_top_contributor: bool = False


class RecommendationConclusion(BaseModel):
    verdict: RecommendationVerdict = "caution"
    headline_ko: str = "탐색 결과"
    final_verdict_ko: str = "주의"
    final_verdict_tone: Literal["positive", "warning", "negative"] = "warning"
    final_verdict_emoji: str = "🟡"
    final_verdict_sublines: list[str] = Field(default_factory=list)
    bullets: list[ConclusionBullet] = Field(default_factory=list)
    summary_ko: str = ""
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    cv_fitness: Optional[CvFitnessTier] = None
    cv_mape: Optional[float] = None
    twin_available: bool = False
    twin_recommended: bool = False
    twin_ran: bool = False
    adopt_mode: AdoptMode = "predictive"
    variable_limit: bool = False
