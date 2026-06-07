"""집합부동산 API 스키마."""

from __future__ import annotations

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


class RegionOption(BaseModel):
    name: str
    count: int
    parent: Optional[str] = None


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
    exclusive_area: Optional[float] = None
    land_area: Optional[float] = None
    price: float
    unit_price: Optional[float] = None
    floor: Optional[float] = None
    dong: Optional[str] = None
    housing_subtype: Optional[str] = None
    building_age: Optional[float] = None


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
    n_total: int
    baseline_median: Optional[float] = None
    cells: list[FloorIndexCell] = []
    analysis: AnalysisFeatures = Field(default_factory=AnalysisFeatures)


class CollectiveRegressionSpec(BaseModel):
    exclusive_area: bool = True
    building_age: bool = True
    floor: bool = True
    dong: bool = True
    housing_subtype: bool = False
    floor_mode: Literal["linear", "dummy", "grouped", "relative"] = "relative"


class CollectiveRegressionRequest(BaseModel):
    asset_type: AssetType
    contract_year_from: Optional[int] = None
    contract_year_to: Optional[int] = None
    variables: CollectiveRegressionSpec = Field(default_factory=CollectiveRegressionSpec)
    exclude_outliers_iqr: bool = False
    outlier_iqr_multiplier: float = 3.0
    experiment: bool = False


class RegressionCoeff(BaseModel):
    name: str
    label: str
    coef: float
    se: Optional[float] = None
    t: Optional[float] = None
    p: Optional[float] = None


class CollectiveRegressionResponse(BaseModel):
    building_key: str
    display_name: str
    n: int
    r_squared: Optional[float] = None
    adj_r_squared: Optional[float] = None
    coefficients: list[RegressionCoeff] = []
    warnings: list[str] = []
