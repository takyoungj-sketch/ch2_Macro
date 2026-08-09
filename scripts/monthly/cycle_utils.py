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
from pathlib import Path


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


def collection_yyyymm_range_from_cycle_id(cycle_id: str) -> tuple[str, str]:
    """직전 12개월 수집 가정. 반환 (from_yyyymm, to_yyyymm)."""
    _validate_cycle_id(cycle_id)
    to_yyyymm = last_data_yyyymm_from_cycle_id(cycle_id)
    ty, tm = int(to_yyyymm[:4]), int(to_yyyymm[4:6])
    months: list[tuple[int, int]] = []
    y, m = ty, tm
    for _ in range(12):
        months.append((y, m))
        if m == 1:
            y, m = y - 1, 12
        else:
            m -= 1
    months.reverse()
    fy, fm = months[0]
    return f"{fy:04d}{fm:02d}", to_yyyymm


def monthly_csv_bundle_dirs(repo: Path, cycle_id: str) -> list[Path]:
    """`raw/` 아래 월간 Molit CSV 번들 폴더 후보 (cycle_id 우선, 구 `2607업데이트` fallback)."""
    _validate_cycle_id(cycle_id)
    raw = repo / "raw"
    yymm = f"{cycle_id[2:4]}{cycle_id[4:6]}"  # 202608 → 2608
    explicit = [
        raw / f"{yymm} 업데이트",
        raw / f"{yymm}업데이트",
    ]
    scanned = sorted(
        (d for d in raw.iterdir() if d.is_dir() and d.name.startswith(yymm)),
        key=lambda p: p.name.lower(),
    )
    legacy = raw / "2607업데이트"
    out: list[Path] = []
    seen: set[Path] = set()
    for p in [*explicit, *scanned, legacy]:
        if p.is_dir() and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def resolve_csv_subdir(
    repo: Path,
    cycle_id: str,
    folder_name: str,
    y_from: str,
    y_to: str,
    *,
    extra_candidates: list[Path] | None = None,
) -> Path | None:
    """`{folder_name}_{y_from}_{y_to}` CSV 폴더 — 월간 번들 → legacy 경로 순."""
    suffix = f"{y_from}_{y_to}"
    candidates: list[Path] = []
    for bundle in monthly_csv_bundle_dirs(repo, cycle_id):
        candidates.append(bundle / f"{folder_name}_{suffix}")
    if extra_candidates:
        candidates.extend(extra_candidates)
    for p in candidates:
        if p.is_dir() and list(p.glob("*.csv")):
            return p
    return None


def resolve_land_csv_raw_dir(repo: Path, cycle_id: str, y_from: str, y_to: str) -> Path | None:
    return resolve_csv_subdir(
        repo,
        cycle_id,
        "토지",
        y_from,
        y_to,
        extra_candidates=[
            repo / "raw" / "토지" / cycle_id,
            repo / "raw" / f"토지_{y_from}_{y_to}",
        ],
    )
