"""2단계 헤도닉 API 스키마."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class HedonicCoeff(BaseModel):
    term: str
    term_label: str
    term_kind: str
    coef: float
    pct_effect: Optional[float] = None
    se: Optional[float] = None
    t: Optional[float] = None
    p_value: Optional[float] = None
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    boot_ci_low: Optional[float] = None
    boot_ci_high: Optional[float] = None
    n_buildings: Optional[int] = None
    vif: Optional[float] = None
    effect_plain: Optional[str] = None


class QualityIndexRow(BaseModel):
    building_key: str
    display_name: Optional[str] = None
    sigungu_code: str
    quality_index: float
    quality_se: Optional[float] = None
    n_tx: int
    percentile_in_sigungu: Optional[float] = None


class SigunguBaseLevelRow(BaseModel):
    sigungu_code: str
    base_ln_price: float
    ref_area: float
    ref_floor_group: str
    ref_year: int
    area_beta: Optional[float] = None
    r_squared: Optional[float] = None
    n_buildings: int
    n_tx: int


class QualityIndexAnalysisResponse(BaseModel):
    as_of_month: date
    window_years: int
    asset_type: str
    n_buildings: int
    n_sigungu: int
    buildings: list[QualityIndexRow] = Field(default_factory=list)
    sigungu_base: list[SigunguBaseLevelRow] = Field(default_factory=list)
    distribution: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    controls_note: str = (
        "품질지수는 시군구 내에서 면적·상대층·계약연도를 통제한 뒤 "
        "단지 FE를 센터링한 상대 가격수준입니다."
    )


class BuildingQualityResponse(BaseModel):
    building_key: str
    display_name: Optional[str] = None
    as_of_month: date
    window_years: int
    quality_index: Optional[float] = None
    quality_se: Optional[float] = None
    n_tx: Optional[int] = None
    sigungu_code: Optional[str] = None
    percentile_in_sigungu: Optional[float] = None
    sigungu_base_ln_price: Optional[float] = None
    decomposition: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    controls_note: str = (
        "동일 시군구·면적·층·계약연도를 1단계에서 통제한 뒤의 단지 상대수준입니다."
    )


class AttributeEffectsRunRequest(BaseModel):
    spec: Literal["A", "B", "C"] = "A"
    scope_level: Literal["national", "sido", "sigungu"] = "national"
    scope_code: Optional[str] = None
    include_location: bool = False
    include_terms: list[str] = Field(
        default_factory=lambda: [
            "brand",
            "builder",
            "scale",
            "structure",
            "vintage",
            "parking",
            "danji_class",
            "max_floor",
        ]
    )
    match_tiers: list[str] = Field(default_factory=lambda: ["A", "B", "C"])
    supply_types: list[str] = Field(default_factory=lambda: ["분양"])
    min_buildings_per_term: int = 30
    weighting: Literal["wls", "ols"] = "wls"
    as_of_month: Optional[date] = None
    window_years: int = 5


class AttributeEffectsResponse(BaseModel):
    as_of_month: date
    window_years: int
    asset_type: str
    spec: str
    scope_level: str
    scope_code: Optional[str] = None
    include_location: bool = False
    weighting: str = "wls"
    equation: str = ""
    coefficients: list[HedonicCoeff] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    model_candidates: list[dict[str, Any]] = Field(default_factory=list)
    sample_breakdown: dict[str, Any] = Field(default_factory=dict)
    reference_categories: dict[str, str] = Field(default_factory=dict)
    controls_note: str = ""
    n_buildings: int = 0
    adj_r_squared: Optional[float] = None
    notes: list[str] = Field(
        default_factory=lambda: [
            "1단계(window·표본 규칙) 변경은 mart 재빌드가 필요합니다 — /run은 2단계만 재추정합니다."
        ]
    )


class MacroEffectsResponse(BaseModel):
    as_of_month: date
    window_years: int
    asset_type: str
    equation: str = ""
    coefficients: list[HedonicCoeff] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sample_breakdown: dict[str, Any] = Field(default_factory=dict)
    reference_categories: dict[str, str] = Field(default_factory=dict)
    n_sigungu: int = 0
    adj_r_squared: Optional[float] = None
    controls_note: str = ""
