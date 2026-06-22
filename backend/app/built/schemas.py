"""복합부동산 API 스키마."""

from __future__ import annotations

import math
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

AssetType = Literal["commercial", "factory", "detached", "all"]
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
    road_code: Optional[float] = None
    road_width_label: Optional[str] = None
    deal_type: Optional[str] = None


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


class RiPick(BaseModel):
    """상위 읍·면 + 리(addr5)."""

    eup: str
    ri: str


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


class RegressionRunResponse(BaseModel):
    primary: RegressionLevelResult
    comparisons: list[RegressionLevelResult] = Field(default_factory=list)
    correlations: list[CorrelationSeries] = Field(default_factory=list)
    correlation_admin_level: Optional[AdminLevel] = None
    correlation_scope_label: Optional[str] = None
    correlation_n: Optional[int] = None


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
