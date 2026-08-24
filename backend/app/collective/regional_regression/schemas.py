"""집합 지역회귀 요청·응답. 한 행 = 단지(기본통계와 같은 유형)."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.collective.schemas import RegressionCoeff


class RegionalRegressionVariables(BaseModel):
    """단지 속성 블록. 약한 변수(구조·시공사)는 숨기지 않고 경고와 함께 쓴다."""

    households: bool = True
    max_floor: bool = True
    building_age: bool = True
    parking: bool = True
    structure: bool = False
    builder: bool = False
    asset_type_dummy: bool = True
    assessed_land_price: bool = False


class RegionalRegressionRunRequest(BaseModel):
    addr1: str
    addr2: str
    addr3_list: list[str] = Field(default_factory=list)
    addr4_list: list[str] = Field(default_factory=list)
    window_years: int = 3
    asset_type: str = "apartment"
    variables: RegionalRegressionVariables = Field(default_factory=RegionalRegressionVariables)
    model_type: Literal["linear", "log"] = "log"
    weight_mode: Literal["equal", "tx"] = "equal"


class RegionalRegressionPredictInputs(BaseModel):
    households: Optional[float] = None
    max_floor: Optional[float] = None
    building_age: Optional[float] = None
    parking_per_household: Optional[float] = None
    structure_group: Optional[str] = None
    builder_group: Optional[str] = None
    asset_type: Optional[str] = None
    assessed_land_price: Optional[float] = None


class RegionalRegressionPredictRequest(RegionalRegressionRunRequest):
    inputs: RegionalRegressionPredictInputs = Field(default_factory=RegionalRegressionPredictInputs)


class FunnelReason(BaseModel):
    code: str
    label: str
    n: int


class FunnelStep(BaseModel):
    """표본 깔때기 한 줄. drop 은 클릭하면 reasons 가 열린다. split 은 탈락이 아니다."""

    code: str
    label: str
    n: int
    delta: Optional[int] = None
    kind: Literal["remain", "drop", "split"] = "remain"
    note: Optional[str] = None
    reasons: list[FunnelReason] = Field(default_factory=list)


class SampleBreakdown(BaseModel):
    n_pool: int
    n_with_attributes: int
    n_usable_tier: int
    n_analysis: int
    n_fit: int
    n_hold: int
    n_missing_attr: int
    n_weak_tier: int
    n_no_price: int
    funnel: list[FunnelStep] = Field(default_factory=list)


class BlockContribution(BaseModel):
    block: str
    label: str
    weak: bool
    hold_mape: Optional[float] = None
    in_sample_mape: Optional[float] = None
    delta_mape_vs_core: Optional[float] = None
    note: Optional[str] = None


class FittedBuildingRow(BaseModel):
    building_key: str
    display_name: str
    y: float
    y_hat: float
    ape: Optional[float] = None
    asset_type: Optional[str] = None
    assessed_land_price: Optional[float] = None


class RegionalRegressionRunResponse(BaseModel):
    n: int
    model_type: Literal["linear", "log"]
    weight_mode: Literal["equal", "tx"] = "equal"
    n_effective: Optional[float] = None
    r_squared: Optional[float] = None
    adj_r_squared: Optional[float] = None
    mape: Optional[float] = None
    hold_mape: Optional[float] = None
    rmse: Optional[float] = None
    f_p_value: Optional[float] = None
    equation: Optional[str] = None
    coefficients: list[RegressionCoeff] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sample: SampleBreakdown
    blocks: list[BlockContribution] = Field(default_factory=list)
    fitted: list[FittedBuildingRow] = Field(default_factory=list)
    predict_options: dict[str, list[str]] = Field(default_factory=dict)
    reference_categories: dict[str, str] = Field(default_factory=dict)
    as_of_month: Optional[str] = None
    snapshot_ym: Optional[str] = None
    scope_label: Optional[str] = None


class RegionalRegressionPredictResponse(BaseModel):
    n: int
    model_type: Literal["linear", "log"]
    weight_mode: Literal["equal", "tx"] = "equal"
    y_hat: float
    unit: str = "만원/㎡"
    warnings: list[str] = Field(default_factory=list)
    contributions: list[dict] = Field(default_factory=list)
