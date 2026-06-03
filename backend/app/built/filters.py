"""지역 필터 공통."""

from __future__ import annotations


def _dedupe_strings(values: list[str] | None, single: str | None = None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    if single:
        s = str(single).strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    for raw in values or []:
        s = str(raw).strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def effective_addr3_list(addr3: str | None, addr3_list: list[str] | None) -> list[str]:
    return _dedupe_strings(addr3_list, addr3)


def effective_addr4_list(addr4: str | None, addr4_list: list[str] | None) -> list[str]:
    return _dedupe_strings(addr4_list, addr4)


def apply_addr3_filter(
    clauses: list[str],
    params: dict,
    addr3: str | None,
    addr3_list: list[str] | None,
) -> list[str]:
    lst = effective_addr3_list(addr3, addr3_list)
    if len(lst) == 1:
        clauses.append("addr3 = :addr3")
        params["addr3"] = lst[0]
    elif len(lst) > 1:
        clauses.append("addr3 = ANY(:addr3_list)")
        params["addr3_list"] = lst
    return lst


def apply_addr4_filter(
    clauses: list[str],
    params: dict,
    addr4: str | None,
    addr4_list: list[str] | None,
) -> list[str]:
    lst = effective_addr4_list(addr4, addr4_list)
    if len(lst) == 1:
        clauses.append("addr4 = :addr4")
        params["addr4"] = lst[0]
    elif len(lst) > 1:
        clauses.append("addr4 = ANY(:addr4_list)")
        params["addr4_list"] = lst
    return lst


def apply_ri_filter(clauses: list[str], params: dict, ri_list) -> None:
    """ri_list: RiPick 또는 dict — (eup, ri) 쌍."""
    if not ri_list:
        return
    parts: list[str] = []
    for i, raw in enumerate(ri_list):
        eup = (raw.eup if hasattr(raw, "eup") else raw["eup"]).strip()
        ri = (raw.ri if hasattr(raw, "ri") else raw["ri"]).strip()
        if not eup or not ri:
            continue
        parts.append(
            f"((addr4 = :ri_eup_{i} OR addr3 = :ri_eup_{i}) AND addr5 = :ri_name_{i})"
        )
        params[f"ri_eup_{i}"] = eup
        params[f"ri_name_{i}"] = ri
    if parts:
        clauses.append("(" + " OR ".join(parts) + ")")


def format_scope_label(names: list[str], *, suffix: str = "읍면동") -> str:
    if not names:
        return ""
    if len(names) == 1:
        return f"{names[0]} {suffix}"
    preview = ", ".join(names[:3])
    if len(names) > 3:
        preview += f" 외 {len(names) - 3}개"
    return f"선택 {suffix} {len(names)}개 ({preview})"


# 하위 호환
format_addr3_scope_label = format_scope_label

CONTINUOUS_FILTER_COLS = ("gross_area", "land_area", "building_age", "road_code")


def apply_sample_filters(
    clauses: list[str],
    params: dict,
    *,
    zone_types: list[str] | None = None,
    building_uses: list[str] | None = None,
    gross_area_min: float | None = None,
    gross_area_max: float | None = None,
    land_area_min: float | None = None,
    land_area_max: float | None = None,
    building_age_min: float | None = None,
    building_age_max: float | None = None,
    road_code_min: float | None = None,
    road_code_max: float | None = None,
) -> None:
    """회귀·거래 목록 공통 표본 필터 (범주 + 연속 구간)."""
    if zone_types:
        clauses.append("zone_type = ANY(:zone_types)")
        params["zone_types"] = zone_types
    if building_uses:
        clauses.append("building_use = ANY(:building_uses)")
        params["building_uses"] = building_uses
    for col, lo, hi in (
        ("gross_area", gross_area_min, gross_area_max),
        ("land_area", land_area_min, land_area_max),
        ("building_age", building_age_min, building_age_max),
        ("road_code", road_code_min, road_code_max),
    ):
        if lo is not None:
            clauses.append(f"{col} >= :{col}_min")
            params[f"{col}_min"] = float(lo)
        if hi is not None:
            clauses.append(f"{col} <= :{col}_max")
            params[f"{col}_max"] = float(hi)


def apply_sample_filters_from_request(clauses: list[str], params: dict, req) -> None:
    """RegressionRunRequest / 동일 필드 객체."""
    apply_sample_filters(
        clauses,
        params,
        zone_types=list(req.zone_types or []) or None,
        building_uses=list(req.building_uses or []) or None,
        gross_area_min=getattr(req, "gross_area_min", None),
        gross_area_max=getattr(req, "gross_area_max", None),
        land_area_min=getattr(req, "land_area_min", None),
        land_area_max=getattr(req, "land_area_max", None),
        building_age_min=getattr(req, "building_age_min", None),
        building_age_max=getattr(req, "building_age_max", None),
        road_code_min=getattr(req, "road_code_min", None),
        road_code_max=getattr(req, "road_code_max", None),
    )
