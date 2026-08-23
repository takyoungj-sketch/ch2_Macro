"""analysis_scope SSOT — built domain (R0)."""

from __future__ import annotations

from app.built.asset_scope import is_unified
from app.built.regression.engine import (
    _focus_admin_level,
    _label_for_level,
    _prepare_regression_scope,
)
from app.built.schemas import RegressionRunRequest
from app.recommendation.models import (
    AnalysisRegionUnitHint,
    AnalysisSampleFilters,
    AnalysisScope,
    AnalysisTimeScope,
    RegionCodeLevel,
    RegionUnitRef,
)


def _norm_code(code: str) -> str:
    return "".join(ch for ch in str(code or "") if ch.isdigit())


def _region_units_from_hints(hints: list[AnalysisRegionUnitHint]) -> list[RegionUnitRef]:
    out: list[RegionUnitRef] = []
    seen: set[str] = set()
    for hint in hints:
        code = _norm_code(hint.code)
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(
            RegionUnitRef(
                code=code,
                level=hint.level,
                name=(hint.name or "").strip() or code,
                addr1=(hint.addr1 or "").strip(),
                addr2=(hint.addr2 or "").strip(),
                eup=(hint.eup or "").strip() or None,
                cross_parent=bool(hint.cross_parent),
            )
        )
    return out


def _region_units_from_request(req: RegressionRunRequest) -> list[RegionUnitRef]:
    level: RegionCodeLevel = (req.region_code_level or "eupmyeondong")  # type: ignore[assignment]
    hints = getattr(req, "region_unit_hints", None) or []
    if hints:
        return _region_units_from_hints(hints)

    out: list[RegionUnitRef] = []
    seen: set[str] = set()

    for addr_key in req.region_addrs or []:
        parts = [p.strip() for p in str(addr_key).split("|")]
        if len(parts) < 3:
            continue
        a1, a2, leaf = parts[0], parts[1], parts[2]
        code = ""
        for raw in req.region_codes or []:
            if _norm_code(raw):
                code = _norm_code(raw)
                break
        key = f"{a1}|{a2}|{leaf}"
        if key in seen:
            continue
        seen.add(key)
        out.append(
            RegionUnitRef(
                code=code,
                level=level,
                name=leaf,
                addr1=a1,
                addr2=a2,
            )
        )

    for raw in req.region_codes or []:
        code = _norm_code(raw)
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(RegionUnitRef(code=code, level=level, name=code))

    return out


def resolve_anchor_unit(
    units: list[RegionUnitRef],
    *,
    anchor_region_code: str | None = None,
) -> RegionUnitRef | None:
    """본 지역 anchor — cross_parent 제외, 명시 code 우선."""
    if not units:
        return None

    anchor_digits = _norm_code(anchor_region_code or "")
    if anchor_digits:
        for unit in units:
            if _norm_code(unit.code) == anchor_digits:
                return unit
        for unit in units:
            code = _norm_code(unit.code)
            if code.startswith(anchor_digits) or anchor_digits.startswith(code):
                return unit

    for unit in units:
        if not unit.cross_parent:
            return unit
    return units[0]


def _time_scope_from_request(req: RegressionRunRequest) -> AnalysisTimeScope:
    return AnalysisTimeScope(
        as_of_month=req.as_of_month,
        window_years=req.window_years,
        contract_year_from=req.contract_year_from,
        contract_year_to=req.contract_year_to,
    )


def _sample_filters_from_request(req: RegressionRunRequest) -> AnalysisSampleFilters:
    return AnalysisSampleFilters(
        zone_types=list(req.zone_types or []),
        building_uses=list(req.building_uses or []),
        road_width_labels=list(req.road_width_labels or []),
        gross_area_min=req.gross_area_min,
        gross_area_max=req.gross_area_max,
        land_area_min=req.land_area_min,
        land_area_max=req.land_area_max,
        building_age_min=req.building_age_min,
        building_age_max=req.building_age_max,
        road_code_min=req.road_code_min,
        road_code_max=req.road_code_max,
        exclude_outliers_iqr=req.exclude_outliers_iqr,
        outlier_iqr_multiplier=req.outlier_iqr_multiplier,
        include_partial=bool(getattr(req, "include_partial", False)),
    )


def scope_from_built_request(req: RegressionRunRequest) -> AnalysisScope:
    """DB 없이 scope 메타만 추출 (region·time·filters). scope_label·n_tx는 0/빈값."""
    region_units = _region_units_from_request(req)
    anchor = resolve_anchor_unit(
        region_units,
        anchor_region_code=getattr(req, "anchor_region_code", None),
    )
    level: RegionCodeLevel = (req.region_code_level or "eupmyeondong")  # type: ignore[assignment]
    return AnalysisScope(
        domain="built",
        asset_slice="unified" if is_unified(req.asset_type) else req.asset_type,
        region_units=region_units,
        anchor_unit=anchor,
        time=_time_scope_from_request(req),
        sample_filters=_sample_filters_from_request(req),
        region_codes=[_norm_code(c) for c in (req.region_codes or []) if _norm_code(c)],
        region_code_level=level if req.region_codes else None,
        region_addrs=list(req.region_addrs or []),
    )


def built_analysis_scope_from_prepared(
    req: RegressionRunRequest,
    *,
    wide_df,
    addr4_city: bool,
    partial_tx_count: int = 0,
) -> AnalysisScope:
    from app.built.partial_ownership import format_partial_n_note

    focus = _focus_admin_level(req, addr4_city)
    scope_label = _label_for_level(req, wide_df, focus, addr4_city)
    base = scope_from_built_request(req)
    include_partial = bool(getattr(req, "include_partial", False))
    return base.model_copy(
        update={
            "scope_label": scope_label,
            "admin_level": focus,
            "scope_n_tx": len(wide_df),
            "include_partial": include_partial,
            "partial_tx_count": int(partial_tx_count or 0),
            "partial_n_note": format_partial_n_note(
                include_partial=include_partial, partial_tx_count=partial_tx_count
            ),
        }
    )


def resolve_built_analysis_scope(conn, req: RegressionRunRequest) -> AnalysisScope:
    """RegressionRunRequest → analysis_scope (엔진과 동일 scope_label·scope_n_tx)."""
    wide_df, req, addr4_city, _mode, partial_tx_count = _prepare_regression_scope(conn, req)
    return built_analysis_scope_from_prepared(
        req, wide_df=wide_df, addr4_city=addr4_city, partial_tx_count=partial_tx_count
    )
