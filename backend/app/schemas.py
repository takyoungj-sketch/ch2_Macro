"""Pydantic 스키마 (요청/응답 모델)."""

from __future__ import annotations

from typing import Optional
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


class MatrixCell(BaseModel):
    zone_type: str
    land_category: str
    stats: StatsResult


# ---------------------------------------------------------------------------
# 유료 분석 요청/응답
# ---------------------------------------------------------------------------
class PaidAnalysisRequest(BaseModel):
    """유료 전용: 복수 지역·기간·세부 필터. 무료 화면은 단일 지역 + 사전집계만 사용."""

    region_codes: list[str] = Field(
        ...,
        min_length=1,
        description="법정동/리 코드 목록 (무료 API는 단일 코드만 지원)",
    )
    year_from: Optional[int] = Field(None, description="무료 사전집계에는 미적용")
    year_to: Optional[int] = Field(None, description="무료 사전집계에는 미적용")
    road_conditions: Optional[list[str]] = Field(None, description="무료: 미지원")
    area_categories: Optional[list[str]] = Field(
        None,
        description="광소/정상/광대, 무료: 미지원",
    )
    land_categories: Optional[list[str]] = Field(None, description="무료: 매트릭스 전체")
    zone_types: Optional[list[str]] = Field(None, description="무료: 매트릭스 전체")
    exclude_partial: bool = Field(False, description="지분거래 제외, 무료 집계에는 지분 포함")
    exclude_outlier: bool = Field(False, description="IQR 이상치 제거, 무료: 미지원")


class PaidAnalysisResponse(BaseModel):
    request: PaidAnalysisRequest
    total: StatsResult
    by_region: dict[str, StatsResult] = {}
    by_zone: dict[str, StatsResult] = {}
    by_land_category: dict[str, StatsResult] = {}
    by_road_condition: dict[str, StatsResult] = {}
    matrix: list[MatrixCell] = []
    response_ms: int = 0
