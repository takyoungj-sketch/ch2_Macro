"""K-apt 없는 필지 — 표제부 해당 용도 동을 합쳐 세대수·층·구조를 채운다.

시공사는 표제부에 없다. 첫째 동을 대표값으로 쓰지 않는다.
부대시설(경비실·주차장 등) 동은 합에서 뺀다.
지역회귀 hard 표본은 A·B·C 유지 (tier T 는 목록용).

종류별로 다른 동만 합친다 — 같은 필지의 아파트 동을 연립 행에 넣지 않는다.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable, Literal

from parcel_master.pnu_unique import REBUILD_YEAR_GAP

TitleKind = Literal["apartment", "rowhouse", "officetel"]

_ANCILLARY = re.compile(
    r"경비실|지하주차장|관리사무소|부대시설|복리시설|상가|경로당|공중변소|어린이집|노유자"
)
_HOUSING_DETAIL = ("아파트", "공동주택", "연립", "도시형생활", "임대아파트")
_ROWHOUSE_DETAIL = re.compile(r"다세대|연립|도시형생활")


def is_housing_dong(main_purpose: object, purpose_detail: object) -> bool:
    """아파트 목록용 — 공동주택·아파트 동. 기존 T 채움과 동일."""
    main = str(main_purpose or "").strip()
    detail = str(purpose_detail or "").strip()
    if main != "공동주택" and "아파트" not in main:
        return False
    if _ANCILLARY.search(detail) and not any(k in detail for k in _HOUSING_DETAIL):
        return False
    return True


def is_rowhouse_dong(main_purpose: object, purpose_detail: object) -> bool:
    """연립·다세대 실거래 행 — 다세대·연립·도시형생활 동만. 아파트 동은 제외."""
    main = str(main_purpose or "").strip()
    detail = str(purpose_detail or "").strip()
    blob = f"{main} {detail}"
    if not _ROWHOUSE_DETAIL.search(blob):
        return False
    if _ANCILLARY.search(detail) and not _ROWHOUSE_DETAIL.search(detail):
        return False
    return True


def is_officetel_dong(main_purpose: object, purpose_detail: object) -> bool:
    """오피스텔 실거래 행 — 주용도·기타용도에 오피스텔이 있는 동만."""
    main = str(main_purpose or "").strip()
    detail = str(purpose_detail or "").strip()
    if "오피스텔" not in main and "오피스텔" not in detail:
        return False
    if _ANCILLARY.search(detail) and "오피스텔" not in detail:
        return False
    return True


def is_title_dong(kind: TitleKind, main_purpose: object, purpose_detail: object) -> bool:
    if kind == "rowhouse":
        return is_rowhouse_dong(main_purpose, purpose_detail)
    if kind == "officetel":
        return is_officetel_dong(main_purpose, purpose_detail)
    return is_housing_dong(main_purpose, purpose_detail)


def _mode(values: Iterable[Any]) -> Any:
    items = [v for v in values if v is not None and v != ""]
    if not items:
        return None
    counts = Counter(items)
    top = counts.most_common(1)[0][1]
    tied = sorted(v for v, n in counts.items() if n == top)
    return tied[0]


def parse_year(value: object) -> int | None:
    s = re.sub(r"\D", "", str(value or ""))
    if len(s) >= 4:
        try:
            y = int(s[:4])
        except ValueError:
            return None
        if 1900 <= y <= 2100:
            return y
    return None


def aggregate_title_dongs(
    rows: list[dict[str, Any]],
    kind: TitleKind = "apartment",
) -> dict[str, Any] | None:
    """한 필지 표제부 행 → 목록용 합. 해당 용도 동이 없으면 None."""
    housing = [r for r in rows if is_title_dong(kind, r.get("main_purpose"), r.get("purpose_detail"))]
    if not housing:
        return None
    hh_vals = []
    for r in housing:
        v = r.get("households")
        if v is None:
            continue
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if n > 0:
            hh_vals.append(n)
    floors = []
    for r in housing:
        v = r.get("floors_above")
        if v is None:
            continue
        try:
            floors.append(int(v))
        except (TypeError, ValueError):
            continue
    years = [parse_year(r.get("approve_date")) for r in housing]
    names = [str(r.get("structure_name") or "").strip() for r in housing]
    return {
        "households": sum(hh_vals) if hh_vals else None,
        "dong_count": len(housing),
        "max_floor": max(floors) if floors else None,
        "structure_raw": _mode(names),
        "approved_year": _mode(y for y in years if y is not None),
        "n_dong": len(housing),
    }


def title_fill_skip_reason(
    *,
    agg: dict[str, Any] | None,
    building_year: int | None,
    require_households: bool = True,
) -> str | None:
    """None 이면 채움. no_housing | no_households | rebuild."""
    if agg is None:
        return "no_housing"
    if require_households and not agg.get("households"):
        return "no_households"
    approved = agg.get("approved_year")
    if (
        approved is not None
        and building_year is not None
        and abs(int(approved) - int(building_year)) >= REBUILD_YEAR_GAP
    ):
        return "rebuild"
    return None
