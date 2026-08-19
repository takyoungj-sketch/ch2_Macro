"""신규아파트 회귀모델 — 트랙 A 상수. SSOT: docs/NEW_APARTMENT_REGRESSION_DESIGN.md"""

from __future__ import annotations

SIDO_DAEJEON = "30"
SIDO_CHUNGBUK = "43"
SUPPORTED_SIDOS = (SIDO_DAEJEON, SIDO_CHUNGBUK)
SIDO_NAMES: dict[str, str] = {
    SIDO_DAEJEON: "대전광역시",
    SIDO_CHUNGBUK: "충청북도",
}
TRANSFER_MAPE_DELTA_PP = 1.0
FOCUS_COEF_NAMES = (
    "ln_land_p50",
    "ln_households",
    "max_floor",
    "parking_per_household",
)
DAEJEON_SIGUNGU: dict[str, str] = {
    "30110": "동구",
    "30140": "중구",
    "30170": "서구",
    "30200": "유성구",
    "30230": "대덕구",
}
DEFAULT_ASSET_TYPE = "apartment"
APE_OUTLIER_PCT = 40.0
APE_REVIEW_MAX = 50.0
APE_REVIEW_HOLDOUT = 25.0
APE_REVIEW_NEW_MEDIAN = 30.0
ERROR_REPEAT_MIN = 5
WATCH_MIN_SIGUNGU = 2
WATCH_MIN_BUILDERS = 2
SMALL_COMPLEX_HH = 300
OLD_STOCK_AGE = 15
LOW_PARKING = 0.8
LARGE_NEW_HH = 500
EXPENSIVE_LAND_P50 = 500.0
COMMERCIAL_ZONES = frozenset({"근상", "유상", "일상", "중상"})
INDUSTRIAL_ZONES = frozenset({"전공", "일공", "준공"})
BOOM_YEARS = frozenset({2020, 2021, 2022})
MIN_TX_PER_CELL = 10
MIN_BUILDINGS_PER_BUILDER = 30
NEW_AGE_MAX = 5
HOLD_OUT_FRAC = 0.2
LAND_THIN_N = 15
LAND_WINDOW_YEARS = 5
COARSE_UQA_CODES = frozenset({"UQA001"})  # 도시지역 — 너무 굵음
MATCH_TIERS = frozenset({"A", "B", "C"})
VINTAGE_REFERENCE = "2000-2009"
BUILDER_OTHER = "__other_builder__"
BUILDER_OTHER_LABEL = "기타 시공사"
STRUCTURE_REFERENCE = "RC"

# pipeline/constants.ZONE_TYPE_COMPACT_MAP 과 동일 — 토지 마트 zone_type 축약
ZONE_TYPE_COMPACT_MAP: dict[str, str] = {
    "제1종전용주거지역": "1전",
    "제2종전용주거지역": "2전",
    "제1종일반주거지역": "1주",
    "제2종일반주거지역": "2주",
    "제3종일반주거지역": "3주",
    "준주거지역": "준주",
    "근린상업지역": "근상",
    "유통상업지역": "유상",
    "일반상업지역": "일상",
    "중심상업지역": "중상",
    "전용공업지역": "전공",
    "일반공업지역": "일공",
    "준공업지역": "준공",
    "자연녹지지역": "자녹",
    "생산녹지지역": "생녹",
    "보전녹지지역": "보녹",
    "계획관리지역": "계관",
    "보전관리지역": "보관",
    "생산관리지역": "생관",
    "개발제한구역": "개제",
    "농림지역": "농림",
    "자연환경보전지역": "자보",
}

VINTAGE_BINS: list[tuple[str, int | None, int | None]] = [
    ("~1989", None, 1989),
    ("1990-1999", 1990, 1999),
    ("2000-2009", 2000, 2009),
    ("2010-2019", 2010, 2019),
    ("2020+", 2020, None),
]
