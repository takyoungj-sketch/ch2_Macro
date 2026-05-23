"""
월간 배치 ID(`YYYYMM`) ↔ V2 통계 `as_of_month` 기본 매핑.

가정(문서 `docs/MONTHLY_UPDATE_SOP.md` 참고):
  - `cycle_id`(예: `202605`) = 그 달(2026-05)에 **월간 작업 번들**을 돌린 운영 라벨이다.
  - 수집되는 계약연월 범위는 직전까지 12개월(예: `202505`~`202604`)이며,
    **마지막 포함 연월**은 `cycle`의 **직전 달**(여기서는 202604)이다.
  - `build_stats_v2 --as-of YYYY-MM-01` 에서 `as_of_month` 는 해당 달 **말까지**가 기간 끝이다
    (V2_STATS / `build_stats_v2` 의 `period_bounds_for_window` 규칙).

따라서 기본값: `stats_as_of = first_day_of( last_month(cycle_calendar_month) )`
는 **마지막 수집 연월이 cycle 직전 달**일 때 `last_yyyy_mm` 와 일치한다.
"""

from __future__ import annotations

from datetime import date


def _validate_cycle_id(cycle_id: str) -> None:
    if len(cycle_id) != 6 or not cycle_id.isdigit():
        raise ValueError(f"cycle_id 는 YYYYMM 6자리여야 합니다: {cycle_id!r}")
    m = int(cycle_id[4:6])
    if m < 1 or m > 12:
        raise ValueError(f"cycle_id 월이 잘못되었습니다: {cycle_id!r}")


def last_data_yyyymm_from_cycle_id(cycle_id: str) -> str:
    """
    cycle_id=202605 (2026년 5월 작업) → 마지막 포함 계약연월 202604 가정.
    반환: 'YYYYMM' 문자열.
    """
    _validate_cycle_id(cycle_id)
    y = int(cycle_id[:4])
    m = int(cycle_id[4:6])
    if m == 1:
        py, pm = y - 1, 12
    else:
        py, pm = y, m - 1
    return f"{py:04d}{pm:02d}"


def stats_as_of_date_from_cycle_id(cycle_id: str) -> date:
    """기본 매핑: 마지막 데이터 연월이 cycle 직전 달일 때의 `as_of_month`(해당 달 1일)."""
    tail = last_data_yyyymm_from_cycle_id(cycle_id)
    y = int(tail[:4])
    m = int(tail[4:6])
    return date(y, m, 1)


def stats_as_of_iso_from_cycle_id(cycle_id: str) -> str:
    """`--as-of` CLI 용 YYYY-MM-DD."""
    d = stats_as_of_date_from_cycle_id(cycle_id)
    return d.isoformat()
