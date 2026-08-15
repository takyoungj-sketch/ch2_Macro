"""REB 상업용 임대동향 — 지표 매핑·연간 집계. 원장과 무관."""

from __future__ import annotations

import re
from typing import Optional

ASSET_KINDS = ("office", "mid_retail", "small_retail", "strata", "retail_all")

# 시트 번호 → 유형. 104·106은 규모별 서울광역이라 파싱에서 제외.
SHEET_ASSET: dict[str, str] = {}
for _n in range(101, 117):
    SHEET_ASSET[str(_n)] = "office"
for _n in range(201, 211):
    SHEET_ASSET[str(_n)] = "mid_retail"
for _n in range(301, 311):
    SHEET_ASSET[str(_n)] = "small_retail"
for _n in range(401, 411):
    SHEET_ASSET[str(_n)] = "strata"
SHEET_ASSET["502"] = "retail_all"

SKIP_SHEETS = frozenset(
    {str(n) for n in range(11, 52)}
    | {"104", "106", "116", "210", "310", "410", "510"}
)

# 오피스 층별 10층↓ / 11층↑ — 저장만, 1차 API/UI는 floor_band=all
SHEET_FLOOR_BAND = {
    "109": "le10",
    "110": "le10",
    "111": "ge11",
    "112": "ge11",
}

UI_HIDDEN_FLOOR_BANDS = frozenset({"le10", "ge11"})

# 월 환산 단가 → 연간 만원/㎡ = 4분기 평균 × 12 ÷ 10
ANNUALIZE_MONTHLY = frozenset({"rent", "floor_rent"})
# 분기 유량(공표 천원/㎡) → 연간 만원/㎡ = 4분기 합 ÷ 10
SUM_FLOW_METRICS = frozenset({"noi_per_m2"})
# 분기 수익률 → 부동산원 연간식(4분기 복리 연결)
COMPOUND_METRICS = frozenset({"income_yield", "capital_yield", "investment_yield"})
# 재고 스냅샷
LAST_METRICS = frozenset({"building_count", "avg_floors", "avg_area"})

# (group_id, 화면 그룹명, 지표 순서)
METRIC_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("building", "건물정보", ("building_count", "avg_floors", "avg_area")),
    ("price", "가격정보", ("rent", "rent_index", "noi_per_m2")),
    (
        "ops",
        "운영현황",
        (
            "rent_income_share",
            "other_income_share",
            "opex_share",
            "noi_pct",
            "vacancy",
        ),
    ),
    ("yield", "수익률", ("income_yield", "capital_yield", "investment_yield")),
    ("other", "기타정보", ("conversion",)),
)

MAIN_METRICS = tuple(m for _gid, _glabel, ms in METRIC_GROUPS for m in ms)
SERIES_METRICS = MAIN_METRICS + ("floor_rent", "floor_utility")
CHEON_TO_MAN = 0.1

Q_HEADER_RE = re.compile(r"^(20\d{2})\s*\.\s*([1-4])Q$")

_AGG_NAMES = frozenset({"합계", "계"})


def is_aggregate_name(name: str) -> bool:
    n = (name or "").strip()
    if not n or n in _AGG_NAMES:
        return True
    return "소계" in n


def metric_from_item(item: str) -> Optional[str]:
    t = (item or "").replace("\n", "").strip()
    if not t:
        return None
    if "동수" in t or t.startswith("호수"):
        return "building_count"
    if "평균층수" in t:
        return "avg_floors"
    if "평균연면적" in t or "평균임대면적" in t:
        return "avg_area"
    if "임대가격지수" in t:
        return "rent_index"
    if "공실률" in t:
        return "vacancy"
    if "층별임대료" in t:
        return "floor_rent"
    if "층별효용" in t:
        return "floor_utility"
    if "전환율" in t:
        return "conversion"
    if "소득수익률" in t:
        return "income_yield"
    if "자본수익률" in t:
        return "capital_yield"
    if "투자수익률" in t:
        return "investment_yield"
    if t.startswith("순영업소득(%)") or t == "순영업소득(%)":
        return "noi_pct"
    if "순영업소득(천원" in t:
        return "noi_per_m2"
    if t.startswith("임대수입"):
        return "rent_income_share"
    if t.startswith("기타수입"):
        return "other_income_share"
    if t.startswith("운영경비"):
        return "opex_share"
    if t.startswith("임대료") or "임대료(천원" in t:
        return "rent"
    return None


def parse_quarter_header(raw: object) -> Optional[tuple[int, int]]:
    h = str(raw or "").replace("\n", "").strip()
    m = Q_HEADER_RE.match(h)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def parse_number(raw: object) -> Optional[float]:
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        if raw != raw:  # NaN
            return None
        return float(raw)
    s = str(raw).strip().replace(",", "")
    if not s or s in {"-", "–", "—", "NA", "n/a"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _four_quarters(by_quarter: dict[int, Optional[float]]) -> Optional[list[float]]:
    vals = [by_quarter.get(q) for q in (1, 2, 3, 4)]
    if any(v is None for v in vals):
        return None
    return [float(v) for v in vals]  # type: ignore[arg-type]


def compound_annual(by_quarter: dict[int, Optional[float]]) -> Optional[float]:
    """부동산원 연간 수익률: ∏(1+r_q/100)−1, 퍼센트. 4분기 모두 있어야 함."""
    vals = _four_quarters(by_quarter)
    if vals is None:
        return None
    prod = 1.0
    for v in vals:
        prod *= 1.0 + v / 100.0
    return (prod - 1.0) * 100.0


def annual_value(metric: str, by_quarter: dict[int, Optional[float]]) -> Optional[float]:
    """연간값. 임대료=평균×12(만원), NOI 금액=합(만원), 수익률=복리, 재고=마지막, 그 외 평균."""
    present = {q: by_quarter.get(q) for q in (1, 2, 3, 4)}
    if metric in ANNUALIZE_MONTHLY:
        vals = _four_quarters(present)
        if vals is None:
            return None
        return (sum(vals) / 4.0) * 12.0 * CHEON_TO_MAN
    if metric in SUM_FLOW_METRICS:
        vals = _four_quarters(present)
        if vals is None:
            return None
        return sum(vals) * CHEON_TO_MAN
    if metric in COMPOUND_METRICS:
        return compound_annual(present)
    if metric in LAST_METRICS:
        for q in (4, 3, 2, 1):
            v = present.get(q)
            if v is not None:
                return float(v)
        return None
    nums = [float(present[q]) for q in (1, 2, 3, 4) if present.get(q) is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)
