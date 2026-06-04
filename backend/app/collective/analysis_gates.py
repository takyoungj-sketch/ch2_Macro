"""집합부동산 고급 분석(효용지수·회귀) 표본 게이트 — 토지 dedupe 정책과 별도."""

from __future__ import annotations

from dataclasses import dataclass

from app.stats_utils import MIN_RELIABLE_COUNT

# 건물表 CI (기존)
MIN_RELIABLE_BUILDING_STATS = MIN_RELIABLE_COUNT  # 15

# 방안 1: 기능별 최소 n (선택 연도 구간 기준)
MIN_COUNT_FLOOR_INDEX = 50
MIN_COUNT_REGRESSION = 30
MIN_COUNT_RECENT_REGRESSION = 15
RECENT_YEARS_WINDOW = 3


@dataclass(frozen=True)
class AnalysisGateResult:
    floor_index_eligible: bool
    regression_eligible: bool
    count_total: int
    count_recent: int
    messages: list[str]


def _recent_year_from(
    *,
    contract_year_to: int | None,
    years: list[int],
) -> int:
    if contract_year_to is not None:
        ref = contract_year_to
    elif years:
        ref = max(y for y in years if y is not None)
    else:
        ref = 0
    return ref - (RECENT_YEARS_WINDOW - 1)


def count_recent_transactions(
    years: list[int | None],
    *,
    contract_year_from: int | None,
    contract_year_to: int | None,
) -> int:
    if not years:
        return 0
    clean = [int(y) for y in years if y is not None]
    if not clean:
        return 0
    recent_from = _recent_year_from(contract_year_to=contract_year_to, years=clean)
    if contract_year_from is not None:
        recent_from = max(recent_from, contract_year_from)
    return sum(1 for y in clean if y >= recent_from)


def evaluate_analysis_gates(
    count_total: int,
    count_recent: int,
) -> AnalysisGateResult:
    messages: list[str] = []
    floor_ok = count_total >= MIN_COUNT_FLOOR_INDEX
    if not floor_ok:
        messages.append(
            f"층·동 효용지수: 선택 구간 거래 {count_total}건 "
            f"(최소 {MIN_COUNT_FLOOR_INDEX}건 필요)"
        )

    regression_ok = count_total >= MIN_COUNT_REGRESSION and count_recent >= MIN_COUNT_RECENT_REGRESSION
    if count_total < MIN_COUNT_REGRESSION:
        messages.append(
            f"회귀 분석: 선택 구간 거래 {count_total}건 "
            f"(최소 {MIN_COUNT_REGRESSION}건 필요)"
        )
    elif count_recent < MIN_COUNT_RECENT_REGRESSION:
        messages.append(
            f"회귀 분석: 최근 {RECENT_YEARS_WINDOW}년 거래 {count_recent}건 "
            f"(최소 {MIN_COUNT_RECENT_REGRESSION}건 필요)"
        )

    return AnalysisGateResult(
        floor_index_eligible=floor_ok,
        regression_eligible=regression_ok,
        count_total=count_total,
        count_recent=count_recent,
        messages=messages,
    )
