"""국토부 실거래 CSV 수집 — 유형·시도·파일명 규격."""

from __future__ import annotations

from dataclasses import dataclass

MOLIT_XLS_URL = "https://rt.molit.go.kr/pt/xls/xls.do?mobileAt="

DEFAULT_SIDO_LIST = [
    "서울특별시",
    "부산광역시",
    "대구광역시",
    "인천광역시",
    "광주광역시",
    "대전광역시",
    "울산광역시",
    "세종특별자치시",
    "경기도",
    "강원특별자치도",
    "충청북도",
    "충청남도",
    "전북특별자치도",
    "전라남도",
    "경상북도",
    "경상남도",
    "제주특별자치도",
]

DEAL_TYPE_NAME = "매매"
DEFAULT_MAX_NEW_DOWNLOADS = 100

# 거래량 많은 시도 — 서버 CSV 생성·다운로드 10~15분 걸릴 수 있음
LARGE_VOLUME_REGIONS = frozenset(
    {
        "서울특별시",
        "부산광역시",
        "인천광역시",
        "경기도",
        "충청남도",
        "전라남도",
        "경상남도",
    }
)


def download_timeout_sec(region: str) -> int:
    return 900 if region in LARGE_VOLUME_REGIONS else 600


def processing_timeout_sec(region: str) -> int:
    return 600 if region in LARGE_VOLUME_REGIONS else 300


@dataclass(frozen=True)
class PropertyType:
    key: str
    tab_id: int
    label_ko: str
    deal_type: str = DEAL_TYPE_NAME

    def csv_filename(self, region: str, year: int) -> str:
        return f"{region}_{self.label_ko}_{self.deal_type}_{year}.csv"

    def output_subdir(self, start_year: int, end_year: int) -> str:
        return f"{self.label_ko}_{start_year}_{end_year}"


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
    (key, f"{pt.label_ko} ({pt.deal_type})")
    for key, pt in PROPERTY_TYPES.items()
]


def get_property_type(key: str) -> PropertyType:
    if key not in PROPERTY_TYPES:
        raise KeyError(f"unknown property type: {key}")
    return PROPERTY_TYPES[key]
