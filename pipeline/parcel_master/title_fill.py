"""K-apt 없는 필지 — 표제부 동을 합쳐 세대수·층·구조를 채운다.

조인 키는 PNU다. 용도 문자열은 한 필지에 여러 주거 유형 동이 있을 때만 나눈다.
해당 유형 글자가 없어도 본체 동이 있으면 붙인다(업무시설·공동주택 오피스텔 등).
시공사는 표제부에 없다. 첫째 동을 대표값으로 쓰지 않는다.
부대시설(경비실·주차장 등) 동은 합에서 뺀다.
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


def is_ancillary_only(main_purpose: object, purpose_detail: object) -> bool:
    """경비실 등. 아파트-관리사무소처럼 주거 키워드가 같이 있으면 본체로 본다."""
    main = str(main_purpose or "").strip()
    detail = str(purpose_detail or "").strip()
    if not _ANCILLARY.search(detail):
        return False
    blob = f"{main} {detail}"
    if "오피스텔" in blob or _ROWHOUSE_DETAIL.search(blob):
        return False
    if any(k in blob for k in _HOUSING_DETAIL):
        return False
    return True


def _dong_kind_labels(main_purpose: object, purpose_detail: object) -> frozenset[TitleKind]:
    labels: set[TitleKind] = set()
    if is_officetel_dong(main_purpose, purpose_detail):
        labels.add("officetel")
    if is_rowhouse_dong(main_purpose, purpose_detail):
        labels.add("rowhouse")
    if is_housing_dong(main_purpose, purpose_detail):
        labels.add("apartment")
    return frozenset(labels)


def select_title_dongs(
    rows: list[dict[str, Any]],
    kind: TitleKind = "apartment",
) -> list[dict[str, Any]]:
    """필지 표제부 행에서 이 실거래 유형에 쓸 동만 고른다.

    1) 유형 글자가 맞는 동
    2) 없으면 어느 유형에도 안 걸린 본체(업무시설·공동주택 등)
    3) 그것도 없고 다른 주거 유형이 하나뿐이면 그 동(실거래 유형과 대장 글자가 다른 경우)
    4) 아파트 동과 다세대 동이 함께 있고 이 유형 글자가 없으면 섞지 않는다
    """
    aligned: list[dict[str, Any]] = []
    untyped: list[dict[str, Any]] = []
    other_rows: list[dict[str, Any]] = []
    other_kinds: set[TitleKind] = set()
    for row in rows:
        main = row.get("main_purpose")
        detail = row.get("purpose_detail")
        if is_ancillary_only(main, detail):
            continue
        labels = _dong_kind_labels(main, detail)
        if kind in labels:
            aligned.append(row)
            continue
        if not labels:
            untyped.append(row)
            continue
        other_rows.append(row)
        other_kinds |= set(labels)
    if aligned:
        return aligned
    if untyped:
        return untyped
    if len(other_kinds) == 1:
        return other_rows
    return []


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
    """한 필지 표제부 행 → 목록용 합. 본체 동이 없으면 None."""
    housing = select_title_dongs(rows, kind=kind)
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


def title_rows_for_pnu(
    pnu: str | None,
    by_pnu: dict[str, list[dict[str, Any]]],
    current_to_old_bjd: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """신 PNU를 먼저 보고, 없으면 인천 분구 구 PNU를 본다."""
    from parcel_master.pnu import remap_pnu_bjd

    if not pnu:
        return []
    rows = by_pnu.get(pnu) or []
    if rows:
        return rows
    if not current_to_old_bjd:
        return []
    old = remap_pnu_bjd(pnu, current_to_old_bjd)
    if old and old != pnu:
        return by_pnu.get(old) or []
    return []


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
