"""연립·다세대 층 효용 · 승강기 — 칸·게이트.

제품 효용지수(상대층 n≥50)와 회귀 탭(금액 OLS)을 바꾸지 않는다.
선정은 n·층 분산만 쓴다 (단가·γ 금지).
"""
from __future__ import annotations

from typing import Literal

from app.land_lab.area_elasticity import REGION_TYPES, classify_region_type

WINDOW_YEARS = 5
ASSET_TYPE = "rowhouse"

EXP1_N_MIN = 10
EXP1_N1_MIN = 3
EXP1_NMID_MIN = 3
EXP1_MAX_FLOOR_MIN = 4
N_SENSITIVITY = (10, 20, 30, 50)
IDENT_FLOORS = (4, 5)

FloorBin = Literal["1", "mid", "top"]
TITLE_RIDE_ELVT_COL = 45
TITLE_EMGEN_ELVT_COL = 46


def floor_bin(floor: float | None, max_floor: float | None) -> FloorBin | None:
    """절대 MVP 칸. 아파트 상대층(저 30%/고 70%)이 아니다."""
    if floor is None or max_floor is None:
        return None
    try:
        f = float(floor)
        mx = float(max_floor)
    except (TypeError, ValueError):
        return None
    if f < 1 or mx < 1:
        return None
    if f == 1:
        return "1"
    if mx >= 2 and f == mx:
        return "top"
    if f > 1 and f < mx:
        return "mid"
    return None


def floor_bin_detail(floor: float | None, max_floor: float | None) -> str | None:
    b = floor_bin(floor, max_floor)
    if b is None:
        return None
    if b in {"1", "top"}:
        return b
    f = int(float(floor))  # type: ignore[arg-type]
    if f in {2, 3, 4}:
        return str(f)
    return "5plus"


def exp1_gate(
    *,
    n: int,
    n_1: int,
    n_mid: int,
    max_floor: float | None,
    n_min: int = EXP1_N_MIN,
) -> bool:
    if max_floor is None:
        return False
    try:
        mx = float(max_floor)
    except (TypeError, ValueError):
        return False
    return (
        int(n) >= n_min
        and int(n_1) >= EXP1_N1_MIN
        and int(n_mid) >= EXP1_NMID_MIN
        and mx >= EXP1_MAX_FLOOR_MIN
    )


def floor_bucket(max_floor: float | None) -> str | None:
    """거래 최고층 칸. 적격은 ≥4라 '4'는 정확히 4층."""
    if max_floor is None:
        return None
    try:
        mx = int(round(float(max_floor)))
    except (TypeError, ValueError):
        return None
    if mx <= 3:
        return "le3"
    if mx == 4:
        return "4"
    if mx == 5:
        return "5"
    return "6plus"


def ident_window_45(max_floor: float | None) -> bool:
    if max_floor is None:
        return False
    try:
        mx = int(round(float(max_floor)))
    except (TypeError, ValueError):
        return False
    return mx in IDENT_FLOORS


def age_band(year: float | None) -> str | None:
    if year is None:
        return None
    try:
        y = int(round(float(year)))
    except (TypeError, ValueError):
        return None
    if y >= 2015:
        return "2015p"
    if y >= 2005:
        return "2005_14"
    if y >= 1995:
        return "1995_04"
    if y >= 1900:
        return "pre1995"
    return None


CAP_SIDO = frozenset({"서울특별시", "경기도", "인천광역시"})


def cap_band(sido_name: str | None) -> str:
    """수도권=서울·경기·인천. metro_gu(부산 등)와 같지 않다."""
    if (sido_name or "").strip() in CAP_SIDO:
        return "capital"
    return "noncapital"


def age_coarse(year: float | None) -> str:
    b = age_band(year)
    if b in {"2015p", "2005_14"}:
        return "new"
    if b in {"1995_04", "pre1995"}:
        return "old"
    return "na"


def size_band(n: int) -> str:
    if int(n) >= 50:
        return "n50"
    if int(n) >= 20:
        return "n20"
    return "n10"


def n_tier_flags(n: int) -> dict[str, bool]:
    return {f"n_ge_{t}": int(n) >= t for t in N_SENSITIVITY}


def elevator_from_counts(ride: int | None, emgen: int | None) -> bool | None:
    if ride is None and emgen is None:
        return None
    r = int(ride or 0)
    e = int(emgen or 0)
    if r < 0 or e < 0:
        return None
    return (r + e) > 0
