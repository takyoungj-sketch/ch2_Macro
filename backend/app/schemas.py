"""Pydantic 스키마 (요청/응답 모델)."""

from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 공통 통계 스키마
# ---------------------------------------------------------------------------
class StatsResult(BaseModel):
    count: int
    mean: Optional[float] = None
    std: Optional[float] = None
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    min: Optional[float] = None
    p25: Optional[float] = None
    median: Optional[float] = None
    p75: Optional[float] = None
    max: Optional[float] = None
    is_reliable: bool = False   # count >= 15

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# 지역 코드 스키마
# ---------------------------------------------------------------------------
class RegionItem(BaseModel):
    beopjungri_code: str
    beopjungri_name: str
    eupmyeondong_code: str
    eupmyeondong_name: str
    sigungu_code: str
    sigungu_name: str
    sido_code: str
    sido_name: str

    model_config = {"from_attributes": True}


class RegionTree(BaseModel):
    sido_code: str
    sido_name: str
    children: list[SigunguNode] = []


class SigunguNode(BaseModel):
    sigungu_code: str
    sigungu_name: str
    children: list[EupmyeondongNode] = []


class EupmyeondongNode(BaseModel):
    eupmyeondong_code: str
    eupmyeondong_name: str
    children: list[BeopjungriNode] = []


class BeopjungriNode(BaseModel):
    beopjungri_code: str
    beopjungri_name: str


# ---------------------------------------------------------------------------
# 무료 통계 응답
# ---------------------------------------------------------------------------
class YearlyTradeStat(BaseModel):
    """법정동/리 단위 연도별 실거래 요약 (정상 거래만, 만원·㎡)."""

    year: int
    count: int = 0
    total_price_10k_sum: float = 0.0
    area_sqm_sum: float = 0.0
    unit_price_per_sqm: Optional[float] = None  # Σ만원 / Σ㎡, 면적 합 0이면 None


class MatrixCell(BaseModel):
    zone_type: str
    land_category: str
    stats: StatsResult


class FreeStatsResponse(BaseModel):
    beopjungri_code: str
    beopjungri_name: str
    year_from: int
    year_to: int
    total: StatsResult
    by_year: list[YearlyTradeStat] = []
    by_zone: dict[str, StatsResult] = {}
    by_land_category: dict[str, StatsResult] = {}
    matrix: list[MatrixCell] = []


class FreeStatsBulkRequest(BaseModel):
    """선택 법정동·리 코드 합산으로 무료 통계 화면과 동일 형식의 결과를 받는다 (유료 기본 통계용)."""

    region_codes: list[str] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# 유료 분석 요청/응답
# ---------------------------------------------------------------------------
class RegionSelectionUnit(BaseModel):
    """
    행정 범위 단위 선택. 시·도 코드 단일 선택은 허용하지 않는다(시군구 이하만).
    - beopjungri: 법정동·리 코드 10자리
    - eupmyeondong: 읍면동 코드 8자리 하위 모든 법정동·리 포함
    - sigungu: 시군구 코드 5자리 하위 전체 포함
    """

    scope_type: Literal["beopjungri", "eupmyeondong", "sigungu"]
    code: str = Field(..., min_length=1, description="해당 레벨의 행정구역 코드")

    model_config = {"extra": "forbid"}


class PaidFilters(BaseModel):
    """유료 분석 공통 필터 (동적 쿼리 WHERE 조건과 동일)."""

    year_from: Optional[int] = Field(None, description="연도 시작(포함), years 미사용 시")
    year_to: Optional[int] = Field(None, description="연도 종료(포함), years 미사용 시")
    years: Optional[list[int]] = Field(
        None,
        description="선택 연도(비연속 포함). 비어 있지 않으면 year_from/year_to 대신 적용",
    )
    road_conditions: Optional[list[str]] = Field(None, description="도로조건 복수")
    area_categories: Optional[list[str]] = Field(
        None,
        description="광소/정상/광대 복수",
    )
    land_categories: Optional[list[str]] = Field(None)
    zone_types: Optional[list[str]] = Field(None)
    exclude_partial: bool = Field(False, description="지분거래 제외(True일 때 미포함)")
    exclude_outlier: bool = Field(False, description="IQR×3 이상치 제외")

    model_config = {"extra": "forbid"}


class PaidAnalysisRequest(BaseModel):
    """
    유료 전용 분석 요청.

    지역 범위: `region_selections` 또는 (하위 호환) `region_codes` 단독 목록 중 하나 이상 필요.
    `region_codes`만 지정하면 모두 법정동·리 단위 선택으로 간주한다.
    """

    region_selections: Optional[list[RegionSelectionUnit]] = Field(
        None,
        description="복수 선택 단위 목록 — 시도 전체 선택은 허용되지 않음",
    )
    region_codes: Optional[list[str]] = Field(
        None,
        description="[하위 호환] 법정동·리 코드만 있는 목록 (=scope beopjungri)",
    )

    year_from: Optional[int] = Field(None, description="연도 시작(포함)")
    year_to: Optional[int] = Field(None, description="연도 종료(포함)")
    years: Optional[list[int]] = Field(None)
    road_conditions: Optional[list[str]] = Field(None)
    area_categories: Optional[list[str]] = Field(None)
    land_categories: Optional[list[str]] = Field(None)
    zone_types: Optional[list[str]] = Field(None)
    exclude_partial: bool = Field(False, description="지분거래 제외")
    exclude_outlier: bool = Field(False)


class PaidAnalysisResponse(BaseModel):
    request: PaidAnalysisRequest
    total: StatsResult
    by_region: dict[str, StatsResult] = {}
    by_zone: dict[str, StatsResult] = {}
    by_land_category: dict[str, StatsResult] = {}
    by_road_condition: dict[str, StatsResult] = {}
    matrix: list[MatrixCell] = []
    response_ms: int = 0


class MatrixYearlyStat(BaseModel):
    """매트릭스 특정 칸: 계약연도별 거래건수·평균 단가(만원/㎡)."""

    year: int
    count: int
    mean_unit_price_per_sqm: Optional[float] = None


class MatrixYearlyRequest(PaidFilters):
    """동일 필터 + 지역 선택 + 용도×지목."""

    region_selections: Optional[list[RegionSelectionUnit]] = Field(None)
    region_codes: Optional[list[str]] = Field(None)

    zone_type: str = Field(...)
    land_category: str = Field(...)


class MatrixYearlyResponse(BaseModel):
    zone_type: str
    land_category: str
    rows: list[MatrixYearlyStat] = []
