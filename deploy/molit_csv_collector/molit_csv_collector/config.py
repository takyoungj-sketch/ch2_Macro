"""국토부 실거래 CSV 수집 — 유형·시도·파일명 규격."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date

MOLIT_XLS_URL = "https://rt.molit.go.kr/pt/xls/xls.do?mobileAt="

DEFAULT_SIDO_LIST = [
    "서울특별시",
    "부산광역시",
    "대구광역시",
    "인천광역시",
    "대전광역시",
    "울산광역시",
    "세종특별자치시",
    "경기도",
    "강원특별자치도",
    "충청북도",
    "충청남도",
    "전북특별자치도",
    "전남광주통합특별시",  # 2026-07-01 광주·전남 통합
    "경상북도",
    "경상남도",
    "제주특별자치도",
]

DEAL_TYPE_SALE = "매매"
DEAL_TYPE_RENT = "전월세"
DEAL_TYPE_CHOICES: list[tuple[str, str]] = [
    ("sale", DEAL_TYPE_SALE),
    ("rent", DEAL_TYPE_RENT),
]
RENT_SUPPORTED_KEYS = frozenset({"apartment", "rowhouse", "detached", "officetel"})

DEFAULT_MAX_NEW_DOWNLOADS = 100

# 국토부 실거래 CSV: 1회 요청 최대 12개월 (전월세·매매 공통). 초과 시 사이트 알림 후 실패.
MOLIT_MAX_PERIOD_MONTHS = 12

# 거래량 많은 시도 — 서버 CSV 생성·다운로드 10~15분 걸릴 수 있음
LARGE_VOLUME_REGIONS = frozenset(
    {
        "서울특별시",
        "부산광역시",
        "인천광역시",
        "경기도",
        "충청남도",
        "전남광주통합특별시",
        "경상남도",
    }
)


def download_timeout_sec(region: str) -> int:
    return 900 if region in LARGE_VOLUME_REGIONS else 600


def processing_timeout_sec(region: str) -> int:
    return 600 if region in LARGE_VOLUME_REGIONS else 300


def resolve_deal_type(key: str) -> str:
    if key == "sale":
        return DEAL_TYPE_SALE
    if key == "rent":
        return DEAL_TYPE_RENT
    if key in (DEAL_TYPE_SALE, DEAL_TYPE_RENT):
        return key
    raise ValueError(f"unknown deal type: {key}")


@dataclass(frozen=True)
class DownloadPeriod:
    key: str
    from_date: str
    to_date: str

    @property
    def label(self) -> str:
        if self.key.isdigit() and len(self.key) == 4:
            return self.key
        return f"{self.from_date}~{self.to_date}"


def period_file_key(from_date: str, to_date: str) -> str:
    """전체 연도(1/1~12/31)면 연도만, 아니면 YYYYMMDD_YYYYMMDD."""
    if from_date.endswith("-01-01") and to_date.endswith("-12-31"):
        year_from = from_date[:4]
        year_to = to_date[:4]
        if year_from == year_to:
            return year_from
    return f"{from_date.replace('-', '')}_{to_date.replace('-', '')}"


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def iter_download_periods(
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
) -> list[DownloadPeriod]:
    """국토부 1회 한도(12개월)에 맞춰 기간을 분할한다.

    달력 연 전체(1~12월)는 파일키가 `{연도}`, 그 외는 `YYYYMMDD_YYYYMMDD`.
    월간 롤링 12개월(예: 2025-08~2026-07)은 한 구간으로 유지한다.
    """
    if (start_year, start_month) > (end_year, end_month):
        raise ValueError("시작 기간이 종료보다 늦습니다.")
    if not (1 <= start_month <= 12 and 1 <= end_month <= 12):
        raise ValueError("월은 1~12 사이여야 합니다.")

    periods: list[DownloadPeriod] = []
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        chunk_end_y, chunk_end_m = _add_months(y, m, MOLIT_MAX_PERIOD_MONTHS - 1)
        if (chunk_end_y, chunk_end_m) > (end_year, end_month):
            chunk_end_y, chunk_end_m = end_year, end_month
        from_s = date(y, m, 1).isoformat()
        to_s = date(
            chunk_end_y, chunk_end_m, monthrange(chunk_end_y, chunk_end_m)[1]
        ).isoformat()
        periods.append(DownloadPeriod(period_file_key(from_s, to_s), from_s, to_s))
        y, m = _add_months(chunk_end_y, chunk_end_m, 1)
    return periods


@dataclass(frozen=True)
class PropertyType:
    key: str
    tab_id: int
    label_ko: str
    deal_type: str = DEAL_TYPE_SALE

    @property
    def supports_rent(self) -> bool:
        return self.key in RENT_SUPPORTED_KEYS

    def with_deal_type(self, deal_type: str) -> PropertyType:
        if deal_type == DEAL_TYPE_RENT and not self.supports_rent:
            raise ValueError(f"{self.label_ko}은(는) 전월세를 지원하지 않습니다.")
        return PropertyType(self.key, self.tab_id, self.label_ko, deal_type)

    def csv_filename(self, region: str, period_key: str) -> str:
        return f"{region}_{self.label_ko}_{self.deal_type}_{period_key}.csv"

    def output_subdir(
        self,
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
    ) -> str:
        deal_part = f"_{self.deal_type}" if self.deal_type != DEAL_TYPE_SALE else ""
        if start_month == 1 and end_month == 12:
            return f"{self.label_ko}{deal_part}_{start_year}_{end_year}"
        return (
            f"{self.label_ko}{deal_part}_{start_year}{start_month:02d}_{end_year}{end_month:02d}"
        )


PROPERTY_TYPES: dict[str, PropertyType] = {
    "apartment": PropertyType("apartment", 1, "아파트"),
    "rowhouse": PropertyType("rowhouse", 2, "연립다세대"),
    "detached": PropertyType("detached", 3, "단독다가구"),
    "officetel": PropertyType("officetel", 4, "오피스텔"),
    "presale": PropertyType("presale", 5, "분양입주권"),
    "commercial": PropertyType("commercial", 6, "상업업무"),
    "land": PropertyType("land", 7, "토지"),
    "factory": PropertyType("factory", 8, "공장창고"),
}

PROPERTY_TYPE_CHOICES: list[tuple[str, str]] = [
    (key, pt.label_ko) for key, pt in PROPERTY_TYPES.items()
]


def get_property_type(key: str, *, deal_type: str = "sale") -> PropertyType:
    if key not in PROPERTY_TYPES:
        raise KeyError(f"unknown property type: {key}")
    return PROPERTY_TYPES[key].with_deal_type(resolve_deal_type(deal_type))
