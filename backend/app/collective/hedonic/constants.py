"""2단계 헤도닉 공통 상수 — docs/COLLECTIVE_TWO_STAGE_HEDONIC_DESIGN.md SSOT."""

from __future__ import annotations

MIN_TX_PER_BUILDING = 10
MIN_BUILDINGS_PER_SIGUNGU = 10
MIN_TX_PER_SIGUNGU = 300
OUTLIER_IQR_MULTIPLIER = 1.5
MIN_BUILDINGS_PER_TERM = 30
BOOTSTRAP_REPS = 500

DEFAULT_ASSET_TYPE = "apartment"
DEFAULT_MATCH_TIERS = frozenset({"A", "B", "C"})
DEFAULT_DANJI_CLASSES = frozenset({"아파트", "주상복합"})
DEFAULT_SUPPLY_TYPES = frozenset({"분양"})

BRAND_REFERENCE = "__no_brand__"
BRAND_REFERENCE_LABEL = "브랜드 없음"
BUILDER_OTHER = "__other_builder__"
BUILDER_OTHER_LABEL = "기타 시공사"
BRAND_OTHER = "__other_brand__"
BRAND_OTHER_LABEL = "기타브랜드"
STRUCTURE_REFERENCE = "RC"
VINTAGE_REFERENCE = "2000-2009"

VINTAGE_BINS: list[tuple[str, int | None, int | None]] = [
    ("~1989", None, 1989),
    ("1990-1999", 1990, 1999),
    ("2000-2009", 2000, 2009),
    ("2010-2019", 2010, 2019),
    ("2020+", 2020, None),
]

REF_FLOOR_GROUP = "floor_rel_mid"

LOCATION_TERMS = frozenset({"eup_population", "rent_jeonse_p50", "land_p50_zone"})

MACRO_TERMS = frozenset({"sigungu_population", "sigungu_land_p50", "sigungu_rent_p50"})

STRUCTURE_LABELS: dict[str, str] = {
    "RC": "RC",
    "SRC": "SRC",
    "STEEL": "철골",
    "OTHER": "기타구조",
}

QUALITY_FLAG_SCALE = "scale_inconsistent"
QUALITY_FLAG_HH_ZERO = "hh_zero"
QUALITY_FLAG_FLOOR = "floor_implausible"
QUALITY_FLAG_PARKING = "parking_implausible"

SPEC_LABELS: dict[str, str] = {
    "A": "브랜드 + 규모·구조·vintage",
    "B": "시공사군 + 규모·구조·vintage",
    "C": "브랜드·시공사 동시(진단용)",
    "L": "시군구 매크로(인구·토지·임대)",
}
