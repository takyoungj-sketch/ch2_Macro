"""Pydantic 스키마 (요청/응답 모델)."""

from __future__ import annotations

import math
from datetime import date
from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, BaseModel, Field, field_validator, model_validator


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
    population_year_end: Optional[int] = None  # 연도별 연말 인구 합(region_codes 산하·population_stats; 상위통계 시 구·시 확장 합산)


class MatrixCell(BaseModel):
    zone_type: str
    land_category: str
    stats: StatsResult


class FreeStatsResponse(BaseModel):
    beopjungri_code: str
    beopjungri_name: str
    year_from: int
    year_to: int
    analysis_base_key: Optional[str] = None
    total: StatsResult
    by_year: list[YearlyTradeStat] = []
    by_zone: dict[str, StatsResult] = {}
    by_land_category: dict[str, StatsResult] = {}
    matrix: list[MatrixCell] = []
    stats_excluded_codes: list[str] = Field(
        default_factory=list,
        description="요청에 있었지만 land_basic_stats(ALL×ALL)가 없어 합산 표본에서 제외된 법정코드.",
    )


class FreeStatsBulkRequest(BaseModel):
    """선택 법정동·리 코드 합산으로 무료 통계 화면과 동일 형식의 결과를 받는다 (유료 기본 통계용)."""

    region_codes: list[str] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# 무료 통계 V2 (land_basic_stats_v2, contract_date 롤링 창)
# ---------------------------------------------------------------------------
class FreeStatsV2BulkRequest(BaseModel):
    """V2 복수 법정동·리 합산 (원장을 동일 period로 재집계)."""

    region_codes: list[str] = Field(..., min_length=1)
    window_years: Literal[3, 5] = Field(
        default=5,
        description="무료 V2: 3년 또는 5년 롤링 창",
    )
    as_of_month: Optional[date] = Field(
        None,
        description=(
            "기준월(해당 월 1일). 미지정 시 STATS_V2_DEFAULT_AS_OF_MONTH·"
            "STATS_V2_ASSUMED_TODAY·실제 오늘 순(§3)."
        ),
    )

    @field_validator("window_years", mode="before")
    @classmethod
    def _coerce_window_years(cls, v):
        """JSON/클라이언트에서 빈 문자열·문자 숫자가 오는 경우 허용."""
        if v is None:
            return 5
        if isinstance(v, str):
            t = v.strip()
            if t == "" or t.lower() in ("null", "undefined"):
                return 5
            if t == "3":
                return 3
            if t == "5":
                return 5
        if v in (3, 5):
            return v
        raise ValueError("window_years 는 3 또는 5 여야 합니다.")

    @model_validator(mode="after")
    def _as_of_first(self) -> FreeStatsV2BulkRequest:
        if self.as_of_month is not None and self.as_of_month.day != 1:
            raise ValueError("as_of_month 는 YYYY-MM-01 형태(월의 1일)여야 합니다.")
        return self


class FreeStatsV2Response(BaseModel):
    """V2 기본 통계 응답: 기준월·날짜 구간·롤링 연수가 명시된다."""

    beopjungri_code: str
    beopjungri_name: str
    as_of_month: date
    stats_reference_date: date = Field(
        ...,
        description=(
            "UI 표시용 기준일: as_of_month(저장·스냅샷 키)의 다음 달 1일. "
            "예: as_of_month=2025-12-01 → stats_reference_date=2026-01-01 (1월 갱신 시점)"
        ),
    )
    period_start: date
    period_end: date
    window_years: int
    total: StatsResult
    by_year: list[YearlyTradeStat] = Field(
        default_factory=list,
        description=(
            "달력 연도별 총계(참고)—첫·중간 해는 해당 연도 1/1부터, 롤링창 시작과 교차하는 방식 포함. "
            "마지막 연도는 period_end 까지만. 순수 만년력 1·1~12·31 보려면 by_year_calendar_reference."
        ),
    )
    by_year_calendar_reference: list[YearlyTradeStat] = Field(
        default_factory=list,
        description=(
            "참고: 각 계약연도에 대해 contract_date 각 연도 1·1 ~ 12·31 로만 집계(롤링·필터와 무관)."
        ),
    )
    by_zone: dict[str, StatsResult] = Field(default_factory=dict)
    by_land_category: dict[str, StatsResult] = Field(default_factory=dict)
    matrix: list[MatrixCell] = Field(default_factory=list)
    stats_excluded_codes: list[str] = Field(
        default_factory=list,
        description="요청에 있었으나 해당 as_of_month·window 에서 V2 ALL×ALL 행이 없어 제외된 코드",
    )
    analysis_base_key: Optional[str] = Field(
        None,
        description="V2 MVP: analysis_base_cache 미연동(추후 contract_date 구간 지원 시)",
    )


RegionLevel = Literal["sido", "sigungu", "eupmyeondong", "city"]


class UpperStatsV2Response(BaseModel):
    """
    상위 행정구역(시도·시군구·읍면동) 사전집계 단건 응답.

    FreeStatsV2Response 와 같은 모양: total/by_zone/by_land_category/matrix/by_year.
    matrix(용도×지목) 는 land_upper_stats_v2 의 비-ALL 행에서 가져온다(C 작업).
    by_year 는 land_transactions 의 region_level/code 별 집계.
    """

    region_level: RegionLevel
    region_code: str
    region_name: str
    as_of_month: date
    stats_reference_date: date = Field(
        ...,
        description="as_of_month 의 다음 달 1일 (UI '기준일' 표시)",
    )
    period_start: date
    period_end: date
    window_years: int
    total: StatsResult
    by_year: list[YearlyTradeStat] = Field(default_factory=list)
    by_zone: dict[str, StatsResult] = Field(default_factory=dict)
    by_land_category: dict[str, StatsResult] = Field(default_factory=dict)
    matrix: list[MatrixCell] = Field(default_factory=list)
    by_year_calendar_reference: list[YearlyTradeStat] = Field(
        default_factory=list,
        description="참고: 만년력 1·1~12·31 연도별 집계(by_year 와 다른 정의 가능).",
    )


class FreeStatsV2MetaAsOfResponse(BaseModel):
    """테이블에 적재된 V2 스냅샷 메타(배치 확인용)."""

    max_as_of_month: Optional[date] = Field(
        None,
        description="land_basic_stats_v2 전체 중 최대 as_of_month(필터 없음)",
    )
    window_years_present: list[int] = Field(
        default_factory=list,
        description="해당 스냅샷에 존재하는 window_years 목록(중복 제거·정렬)",
    )


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


def _normalize_outlier_iqr_multiplier(v: object) -> float:
    """허용: 1.5, 2, 3 (exclude_outlier 미사용 시 값은 무시됨)."""
    if v is None:
        return 3.0
    fv = float(v)
    for a in (1.5, 2.0, 3.0):
        if math.isclose(fv, a, rel_tol=0, abs_tol=1e-9):
            return a
    raise ValueError("outlier_iqr_multiplier는 1.5, 2, 3 중 하나여야 합니다.")


OutlierIqrMultiplier = Annotated[
    float,
    Field(
        3.0,
        description="이상치 제외 시 적용할 IQR 배수(Tukey 펜스: Q1−k·IQR ~ Q3+k·IQR)",
    ),
    AfterValidator(_normalize_outlier_iqr_multiplier),
]


class PaidAreaSqmBounds(BaseModel):
    """
    계약면적(㎡) 직접 범위. 둘 중 하나만 줘도 된다.
    `area_sqm_min` 또는 `area_sqm_max` 가 하나라도 있으면 서버는 광소/정상/광대(`area_categories`)를 적용하지 않는다.
    """

    area_sqm_min: Optional[float] = Field(
        None,
        description="계약면적(㎡) 하한(포함). 지정 시 면적구분 칩 대신 면적 범위만 필터.",
    )
    area_sqm_max: Optional[float] = Field(
        None,
        description="계약면적(㎡) 상한(포함).",
    )

    @model_validator(mode="after")
    def _validate_area_sqm_range(self) -> PaidAreaSqmBounds:
        lo = self.area_sqm_min
        hi = self.area_sqm_max
        if lo is None and hi is None:
            return self
        if lo is not None:
            if not math.isfinite(lo) or lo <= 0:
                raise ValueError("area_sqm_min는 양의 유한 숫자여야 합니다.")
        if hi is not None:
            if not math.isfinite(hi) or hi <= 0:
                raise ValueError("area_sqm_max는 양의 유한 숫자여야 합니다.")
        if lo is not None and hi is not None and lo > hi:
            raise ValueError("area_sqm_min는 area_sqm_max 이하여야 합니다.")
        return self


class PaidFilters(PaidAreaSqmBounds):
    """유료 분석 공통 필터 (동적 쿼리 WHERE 조건과 동일)."""

    year_from: Optional[int] = Field(None, description="연도 시작(포함), years 미사용 시")
    year_to: Optional[int] = Field(None, description="연도 종료(포함), years 미사용 시")
    years: Optional[list[int]] = Field(
        None,
        description="선택 연도(비연속 포함). 비어 있지 않으면 year_from/year_to 대신 적용",
    )
    base_cache_key: Optional[str] = Field(
        None,
        description="1단계 기본 통계에서 확정한 후보 거래행 캐시 키",
    )
    road_conditions: Optional[list[str]] = Field(None, description="도로조건 복수")
    area_categories: Optional[list[str]] = Field(
        None,
        description="광소/정상/광대 복수",
    )
    land_categories: Optional[list[str]] = Field(None)
    zone_types: Optional[list[str]] = Field(None)
    exclude_partial: bool = Field(False, description="지분거래 제외(True일 때 미포함)")
    exclude_outlier: bool = Field(False, description="단가 IQR 기반 이상치 제외 활성화")
    outlier_iqr_multiplier: OutlierIqrMultiplier = 3.0

    rolling_matrix_period_start: Optional[date] = Field(
        None,
        description="매트릭스 칸 트렌드: contract_date 하한—V2 매트릭스 롤링 창과 동일해야 함.",
    )
    rolling_matrix_period_end: Optional[date] = Field(
        None,
        description="매트릭스 칸 트렌드: contract_date 상한.",
    )
    rolling_bucket_count: Optional[int] = Field(
        None,
        ge=1,
        le=10,
        description="롤링 12개월 구간 수(통상 window_years)",
    )
    rolling_stats_reference_date: Optional[date] = Field(
        None,
        description="차트 우측 기준 레이블(통상 stats_reference_date 미지정 시 자동 표기)",
    )

    model_config = {"extra": "forbid"}


class PaidAnalysisRequest(PaidAreaSqmBounds):
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
    base_cache_key: Optional[str] = Field(None)
    road_conditions: Optional[list[str]] = Field(None)
    area_categories: Optional[list[str]] = Field(None)
    land_categories: Optional[list[str]] = Field(None)
    zone_types: Optional[list[str]] = Field(None)
    exclude_partial: bool = Field(False, description="지분거래 제외")
    exclude_outlier: bool = Field(False)
    outlier_iqr_multiplier: OutlierIqrMultiplier = 3.0

    rolling_matrix_period_start: Optional[date] = Field(
        None, description="/paid/matrix-* 롤링 모드 전용(api 본편에서는 미사용)"
    )
    rolling_matrix_period_end: Optional[date] = Field(None)
    rolling_bucket_count: Optional[int] = Field(None, ge=1, le=10)
    rolling_stats_reference_date: Optional[date] = Field(None)

    # 다른 PaidFilters · RegionSelectionUnit 와 동일 정책: 프론트 필드명 오타가 조용히 무시되지 않게 422 반환.
    model_config = {"extra": "forbid"}


class PaidAnalysisResponse(BaseModel):
    request: PaidAnalysisRequest
    total: StatsResult
    """요청 연도별 건수·총액·면적 요약 (필터 조건과 동일, 상단 표용)."""
    by_year: list[YearlyTradeStat] = Field(default_factory=list)
    by_region: dict[str, StatsResult] = {}
    by_zone: dict[str, StatsResult] = {}
    by_land_category: dict[str, StatsResult] = {}
    by_road_condition: dict[str, StatsResult] = {}
    matrix: list[MatrixCell] = []
    response_ms: int = 0
    # DECISIONS D-006 — 무료/유료 화면이 같은 「YYYY년 M월 말 기준」 표기를 쓰도록 응답에 같이 노출.
    as_of_month: Optional[date] = Field(
        None,
        description="현재 land_basic_stats_v2 의 최신 스냅샷 월 1일 (= 직전 달까지 반영). 비어 있으면 V2 사전집계가 적재되지 않은 상태.",
    )
    stats_reference_date: Optional[date] = Field(
        None,
        description="UI 표시용 기준일 — `as_of_month` 의 다음 달 1일. 화면 상단의 「YYYY년 M월 말 기준」 라벨과 1:1.",
    )


class MatrixYearlyStat(BaseModel):
    """매트릭스 특정 칸: 연도별·또는 롤링 연간 구간별 분포 요약."""

    year: Optional[int] = Field(
        None,
        description="달력연도 모드(contract_year 단위 집계)일 때만 사용",
    )
    bucket_index: Optional[int] = Field(None, ge=0, description="롤링 12개월 모드 버킷(0=가장 과거)")
    period_start: Optional[date] = Field(None)
    period_end: Optional[date] = Field(None)
    chart_label: Optional[str] = Field(None, description="축 표시 문자열 예: y-1, 기준연월)")
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


class HistogramBin(BaseModel):
    """단가(만원/㎡) 구간별 건수."""

    bin_from: float
    bin_to: float
    count: int


class MatrixCellHistogramRequest(MatrixYearlyRequest):
    """매트릭스 한 칸: 단가 분포(히스토그램)."""

    histogram_scope: Literal["all", "single"] = Field(
        "all",
        description="all: 해당 칸 표본 전체, single: histogram_year 또는 histogram_bucket_index 에 해당하는 표본만",
    )
    histogram_year: Optional[int] = Field(
        None,
        description="달력(contract_year) 모드 single 시 필수. 롤링 트렌드에는 histogram_bucket_index 사용",
    )
    histogram_bucket_index: Optional[int] = Field(
        None,
        ge=0,
        description="롤링 트렌드 요청 중 single 한 구간(0부터 가장 과거 버킷)",
    )
    bin_count: int = Field(
        20, ge=5, le=60, description="히스토그램 구간 개수(서버에서 표본 크기에 맞게 조정 가능)"
    )

    @model_validator(mode="after")
    def _single_target(self) -> MatrixCellHistogramRequest:
        rolling = (
            self.rolling_matrix_period_start is not None
            and self.rolling_matrix_period_end is not None
            and self.rolling_bucket_count is not None
        )
        if self.histogram_scope != "single":
            return self
        if rolling:
            bc = self.rolling_bucket_count or 0
            bi = self.histogram_bucket_index
            if bi is None:
                raise ValueError(
                    "롤링 트렌드에서는 histogram_bucket_index 로 구간을 지정해야 합니다."
                )
            if bi < 0 or bi >= int(bc):
                raise ValueError(f"histogram_bucket_index 는 0 ~ {bc - 1} 범위여야 합니다.")
            return self
        if self.histogram_year is None:
            raise ValueError("histogram_scope가 single이면 histogram_year가 필요합니다.")
        return self


class MatrixCellHistogramResponse(BaseModel):
    zone_type: str
    land_category: str
    n: int
    exclude_outlier: bool
    outlier_iqr_multiplier: float
    histogram_scope: Literal["all", "single"]
    histogram_year: Optional[int] = None
    histogram_bucket_index: Optional[int] = None
    histogram_period_start: Optional[date] = None
    histogram_period_end: Optional[date] = None
    bins: list[HistogramBin] = []


class MatrixCellTransactionItem(BaseModel):
    id: int
    contract_year: int
    contract_month: int
    beopjungri_code: str
    beopjungri_name: Optional[str] = None
    area_sqm: Optional[float] = None
    total_price_10k: float
    unit_price_per_sqm: Optional[float] = None
    road_condition: Optional[str] = None


class MatrixCellTransactionsRequest(MatrixYearlyRequest):
    offset: int = Field(0, ge=0)
    limit: int = Field(25, ge=1, le=100)


class MatrixCellTransactionsResponse(BaseModel):
    zone_type: str
    land_category: str
    total: int
    offset: int
    limit: int
    exclude_outlier: bool
    outlier_iqr_multiplier: float
    items: list[MatrixCellTransactionItem] = []
