"""OLS 회귀 — 금액(만원) 종속."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

from app.built.asset_scope import apply_asset_type_filter, is_unified
from app.built.filters import (
    effective_addr3_list,
    effective_addr4_list,
    format_scope_label,
)
from app.built.region_structure import detect_region_structure
from app.built.schemas import (
    AdminLevel,
    ContinuousRange,
    CorrelationPoint,
    CorrelationSeries,
    PredictOptions,
    RegressionCoeff,
    RegressionLevelResult,
    RegressionPredictRequest,
    RegressionPredictResponse,
    RegressionRunRequest,
    RegressionRunResponse,
    RegressionVariableSpec,
    ResponseScale,
    RiPick,
    VifEntry,
)

from app.built.time_scope import apply_contract_date_window, parse_as_of_month

CompareMode = Literal["sigungu_only", "two_way", "three_way"]
CONTINUOUS_VARS = frozenset({"gross_area", "land_area", "building_age"})
_CONT_LABELS = {
    "gross_area": "연면적",
    "land_area": "대지면적",
    "building_age": "연식",
    "road_code": "도로",
}
_ASSET_LABELS = {
    "commercial": "상업",
    "factory": "공장",
    "detached": "단독",
}
VIF_WARN = 10.0
VIF_CAUTION = 5.0
MAX_REGION_DUMMY_WARN = 15


def _eup_leaf_column(addr4_city: bool) -> str:
    """읍·면·동 풀링 회귀에서 지역 더미용 컬럼 (광역=addr4 동, 그 외=addr3)."""
    return "addr4" if addr4_city else "addr3"


def _duan_smearing(residuals: np.ndarray) -> float:
    r = np.asarray(residuals, dtype=float)
    r = r[np.isfinite(r)]
    if r.size == 0:
        return 1.0
    return float(np.mean(np.exp(r)))


def _insample_mape_pct(
    y_price: np.ndarray,
    model,
    *,
    response_scale: ResponseScale,
) -> float | None:
    """적합값 기준 in-sample MAPE(%), 종속은 항상 금액(만원) 원척도."""
    y = np.asarray(y_price, dtype=float)
    fitted = np.asarray(model.fittedvalues, dtype=float)
    if response_scale == "log":
        pred = np.exp(fitted) * _duan_smearing(model.resid.to_numpy())
    else:
        pred = fitted
    mask = np.isfinite(y) & np.isfinite(pred) & (y != 0)
    if not mask.any():
        return None
    err = np.abs(y[mask] - pred[mask]) / np.abs(y[mask])
    return round(float(np.mean(err)) * 100, 2)


@dataclass
class DesignMeta:
    feature_columns: list[str] = field(default_factory=list)
    zone_types: list[str] = field(default_factory=list)
    building_uses: list[str] = field(default_factory=list)
    road_width_labels: list[str] = field(default_factory=list)
    asset_types: list[str] = field(default_factory=list)
    zone_reference: str | None = None
    building_use_reference: str | None = None
    road_width_reference: str | None = None
    asset_type_reference: str | None = None
    region_leaves: list[str] = field(default_factory=list)
    region_reference: str | None = None
    continuous_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)
    response_scale: ResponseScale = "linear"


def _meta_to_predict_options(meta: DesignMeta | None) -> PredictOptions | None:
    if meta is None or not meta.feature_columns:
        return None
    return PredictOptions(
        zone_types=meta.zone_types,
        building_uses=meta.building_uses,
        road_width_labels=meta.road_width_labels,
        asset_types=meta.asset_types,
        zone_reference=meta.zone_reference,
        building_use_reference=meta.building_use_reference,
        road_width_reference=meta.road_width_reference,
        asset_type_reference=meta.asset_type_reference,
        region_leaves=meta.region_leaves,
        region_reference=meta.region_reference,
        continuous=[
            ContinuousRange(name=k, min=v[0], max=v[1]) for k, v in meta.continuous_ranges.items()
        ],
    )


def _back_transform(value: float, scale: ResponseScale) -> float:
    if scale == "log":
        return float(np.exp(value))
    return float(value)


def _build_where(
    req: RegressionRunRequest,
    *,
    conn=None,
    include_subregion: bool = True,
) -> tuple[str, dict]:
    clauses = ["is_valid = true"]
    params: dict[str, Any] = {}
    apply_asset_type_filter(clauses, params, req.asset_type)
    if include_subregion:
        from app.region_scope import apply_region_scope

        if req.addr1 and req.addr2:
            apply_region_scope(
                clauses,
                params,
                conn=conn,
                table="built_transactions",
                addr1=req.addr1,
                addr2=req.addr2,
                addr3=req.addr3,
                addr3_list=req.addr3_list,
                addr4_list=req.addr4_list,
                ri_list=req.ri_list,
                asset_type=req.asset_type,
            )
        elif req.addr1:
            clauses.append("addr1 = :addr1")
            params["addr1"] = req.addr1
            from app.built.filters import apply_addr3_filter, apply_addr4_filter, apply_ri_filter

            apply_addr3_filter(clauses, params, req.addr3, req.addr3_list)
            apply_addr4_filter(clauses, params, None, req.addr4_list)
            apply_ri_filter(clauses, params, req.ri_list)
    elif req.addr1 and req.addr2:
        from app.flat_sido_region import apply_addr2_scope

        apply_addr2_scope(clauses, params, addr1=req.addr1, addr2=req.addr2)
    elif req.addr1:
        clauses.append("addr1 = :addr1")
        params["addr1"] = req.addr1
    if req.contract_year_from is not None:
        clauses.append("contract_year >= :cy_from")
        params["cy_from"] = req.contract_year_from
    if req.contract_year_to is not None:
        clauses.append("contract_year <= :cy_to")
        params["cy_to"] = req.contract_year_to
    if req.as_of_month and req.window_years:
        apply_contract_date_window(
            clauses,
            params,
            as_of_month=parse_as_of_month(req.as_of_month),
            window_years=req.window_years,
        )
    from app.built.filters import apply_sample_filters_from_request

    apply_sample_filters_from_request(clauses, params, req)
    return " AND ".join(clauses), params


def _fetch_df(conn, req: RegressionRunRequest, *, include_subregion: bool = True) -> pd.DataFrame:
    from sqlalchemy import text

    where, params = _build_where(req, conn=conn, include_subregion=include_subregion)
    sql = f"""
        SELECT price, gross_area, land_area, building_age, road_code, road_width_label,
               zone_type, building_use, asset_type, contract_year,
               addr3, addr4, addr5,
               sigungu_code, eupmyeondong_code, beopjungri_code
        FROM built_transactions
        WHERE {where}
    """
    rows = conn.execute(text(sql), params).mappings().all()
    return pd.DataFrame(rows)


def _uses_addr4_leaf(df: pd.DataFrame) -> bool:
    if df.empty or "addr3" not in df.columns:
        return False
    a3 = df["addr3"].dropna().astype(str).str.strip()
    if a3.empty:
        return False
    return bool((a3.str.endswith("구")).mean() >= 0.85)


def _resolve_addr4_city(
    conn,
    req: RegressionRunRequest,
    wide_df: pd.DataFrame,
) -> bool:
    """구→읍면동 2단계 시군구 — 클라이언트 leaf_level · region_structure · 표본 휴리스틱."""
    if req.leaf_level == "addr4":
        return True
    if req.leaf_level == "addr3":
        return False

    leaves = effective_addr4_list(None, req.addr4_list)
    if leaves and not wide_df.empty:
        hits = wide_df[_norm_col(wide_df, "addr4").isin(set(leaves))]
        if len(hits):
            a3 = _norm_col(hits, "addr3")
            if a3.str.endswith("구").mean() >= 0.5:
                return True

    if req.addr1 and req.addr2:
        info = detect_region_structure(conn, req.addr1, req.addr2, req.asset_type)
        if info.get("leaf_level") == "addr4":
            return True
        if not info.get("has_intermediate"):
            return False
    return _uses_addr4_leaf(wide_df)


def _normalize_leaf_fields(
    req: RegressionRunRequest,
    wide_df: pd.DataFrame,
    *,
    addr4_city: bool,
) -> RegressionRunRequest:
    """addr3_list에 읍면동(실제 addr4)이 들어온 경우 addr4_list로 이동."""
    if wide_df.empty:
        return req

    gu_in_data = {s for s in _norm_col(wide_df, "addr3").tolist() if s.endswith("구")}
    dong_in_data = {s for s in _norm_col(wide_df, "addr4").tolist() if s}

    a3 = effective_addr3_list(req.addr3, req.addr3_list)
    a4 = effective_addr4_list(None, req.addr4_list)
    has_dong_in_a3 = any(n in dong_in_data and n not in gu_in_data for n in a3)
    should_norm = addr4_city or req.leaf_level == "addr4" or bool(a4) or has_dong_in_a3
    if not should_norm:
        return req

    kept_gu: list[str] = []
    extra_a4: list[str] = []
    for name in a3:
        if name in gu_in_data:
            kept_gu.append(name)
        elif name in dong_in_data:
            extra_a4.append(name)
        elif name.endswith("구"):
            kept_gu.append(name)
        else:
            kept_gu.append(name)

    merged_a4 = list(a4)
    seen_a4 = set(a4)
    for name in extra_a4:
        if name not in seen_a4:
            seen_a4.add(name)
            merged_a4.append(name)

    if extra_a4 or kept_gu != a3 or (merged_a4 and merged_a4 != a4):
        return req.model_copy(update={"addr3": None, "addr3_list": kept_gu, "addr4_list": merged_a4})
    return req


def _finalize_addr4_city(
    conn,
    req: RegressionRunRequest,
    wide_df: pd.DataFrame,
) -> bool:
    """정규화 후 최종 구-동 구조 여부."""
    if _resolve_addr4_city(conn, req, wide_df):
        return True
    leaves = effective_addr4_list(None, req.addr4_list)
    if not leaves or wide_df.empty:
        return False
    hits = wide_df[_norm_col(wide_df, "addr4").isin(set(leaves))]
    if hits.empty:
        return False
    return bool(_norm_col(hits, "addr3").str.endswith("구").mean() >= 0.5)


def _prepare_regression_scope(
    conn,
    req: RegressionRunRequest,
) -> tuple[pd.DataFrame, RegressionRunRequest, bool, CompareMode]:
    wide_df = _fetch_df(conn, req, include_subregion=False)
    if req.exclude_outliers_iqr:
        wide_df = _iqr_filter(wide_df, "price", req.outlier_iqr_multiplier)
    addr4_city_hint = _resolve_addr4_city(conn, req, wide_df)
    req = _normalize_leaf_fields(req, wide_df, addr4_city=addr4_city_hint)
    addr4_city = _finalize_addr4_city(conn, req, wide_df)
    mode = _compare_mode(req, addr4_city)
    return wide_df, req, addr4_city, mode


def _has_leaf_selection(req: RegressionRunRequest, addr4_city: bool) -> bool:
    if addr4_city:
        return bool(effective_addr4_list(None, req.addr4_list))
    return bool(effective_addr3_list(req.addr3, req.addr3_list))


def _compare_mode(req: RegressionRunRequest, addr4_city: bool) -> CompareMode:
    if req.ri_list:
        return "three_way"
    if _has_leaf_selection(req, addr4_city):
        return "two_way"
    return "sigungu_only"


def _norm_col(df: pd.DataFrame, col: str) -> pd.Series:
    return df[col].astype(str).str.strip()


def _filter_sigungu(df: pd.DataFrame, req: RegressionRunRequest) -> pd.DataFrame:
    return df.copy()


def _effective_gu_names(req: RegressionRunRequest, df: pd.DataFrame) -> list[str]:
    """구-동 구조에서 비교 대상 구(addr3) — 명시 선택 또는 선택 동의 상위 구 추론."""
    gu = effective_addr3_list(req.addr3, req.addr3_list)
    if gu:
        return gu
    leaves = effective_addr4_list(None, req.addr4_list)
    if leaves and not df.empty:
        sub = df[_norm_col(df, "addr4").isin(set(leaves))]
        inferred = sorted({s for s in _norm_col(sub, "addr3").tolist() if s})
        if inferred:
            return inferred
    return []


def _filter_gu(df: pd.DataFrame, req: RegressionRunRequest) -> pd.DataFrame:
    """구 단위 (addr3=구, addr4=읍면동 구조)."""
    names = _effective_gu_names(req, df)
    if not names:
        return df.iloc[0:0]
    return df[_norm_col(df, "addr3").isin(set(names))]


def _filter_eup_leaf(df: pd.DataFrame, req: RegressionRunRequest, addr4_city: bool) -> pd.DataFrame:
    """선택 읍·면·동(복수 합집합)."""
    out = df.copy()
    gu = effective_addr3_list(req.addr3, req.addr3_list)
    if addr4_city:
        leaves = effective_addr4_list(None, req.addr4_list)
        if gu:
            out = out[_norm_col(out, "addr3").isin(set(gu))]
        if leaves:
            out = out[_norm_col(out, "addr4").isin(set(leaves))]
        elif not gu:
            out = out[_norm_col(out, "addr4") != ""]
    else:
        leaves = effective_addr3_list(req.addr3, req.addr3_list)
        if leaves:
            out = out[_norm_col(out, "addr3").isin(set(leaves))]
        else:
            out = out[_norm_col(out, "addr3") != ""]
    return out


def _filter_parent_eups(df: pd.DataFrame, ri_list: list[RiPick], addr4_city: bool) -> pd.DataFrame:
    """선택 리들의 상위 읍·면 전체(리 미선택 행 포함)."""
    parents = sorted({p.eup.strip() for p in ri_list if p.eup.strip()})
    if not parents:
        return df.iloc[0:0]
    parent_set = set(parents)
    out = df.copy()
    if addr4_city:
        return out[_norm_col(out, "addr4").isin(parent_set)]
    return out[_norm_col(out, "addr3").isin(parent_set)]


def _filter_ri_picks(df: pd.DataFrame, ri_list: list[RiPick]) -> pd.DataFrame:
    if not ri_list:
        return df.iloc[0:0]
    mask = pd.Series(False, index=df.index)
    for pick in ri_list:
        eup = pick.eup.strip()
        ri = pick.ri.strip()
        m = (_norm_col(df, "addr5") == ri) & (
            (_norm_col(df, "addr4") == eup) | (_norm_col(df, "addr3") == eup)
        )
        mask |= m
    return df[mask]


def _iqr_filter(df: pd.DataFrame, col: str, k: float) -> pd.DataFrame:
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    if len(s) < 4:
        return df
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    lo, hi = q1 - k * iqr, q3 + k * iqr
    return df[(df[col] >= lo) & (df[col] <= hi)]


def _compute_vif(X: pd.DataFrame) -> list[VifEntry]:
    """연속변수 간 VIF (더미·상수 제외)."""
    from statsmodels.stats.outliers_influence import variance_inflation_factor

    cols = [c for c in X.columns if c in CONTINUOUS_VARS]
    if len(cols) < 2:
        return []
    sub = X[cols].astype(float).dropna()
    if len(sub) < len(cols) + 5:
        return []
    out: list[VifEntry] = []
    values = sub.values
    for i, col in enumerate(cols):
        try:
            v = float(variance_inflation_factor(values, i))
            if v != v or v == float("inf"):  # NaN / inf
                v = None
        except Exception:
            v = None
        out.append(VifEntry(name=col, vif=v))
    return out


def _vif_warning(vif_entries: list[VifEntry]) -> str | None:
    if not vif_entries:
        return None
    high = [e for e in vif_entries if e.vif is not None and e.vif >= VIF_WARN]
    mid = [e for e in vif_entries if e.vif is not None and VIF_CAUTION <= e.vif < VIF_WARN]
    if high:
        labels = ", ".join(_CONT_LABELS.get(e.name, e.name) for e in high)
        return f"다중공선성 주의 — VIF≥{VIF_WARN:.0f}: {labels}"
    if mid:
        labels = ", ".join(_CONT_LABELS.get(e.name, e.name) for e in mid)
        return f"다중공선성 참고 — VIF≥{VIF_CAUTION:.0f}: {labels}"
    return None


def _build_design_matrix(
    df: pd.DataFrame,
    vars_spec: RegressionVariableSpec,
    *,
    unified: bool = False,
    response_scale: ResponseScale = "linear",
    region_col: str | None = None,
) -> tuple[pd.Series, pd.DataFrame, DesignMeta | None]:
    """종속 y와 독립 X (상수 미포함), 설계 메타."""
    if df.empty:
        return pd.Series(dtype=float), pd.DataFrame(), None

    y = pd.to_numeric(df["price"], errors="coerce")
    parts: list[pd.DataFrame] = []
    meta = DesignMeta(response_scale=response_scale)

    for col, enabled in (
        ("gross_area", vars_spec.gross_area),
        ("land_area", vars_spec.land_area),
        ("building_age", vars_spec.building_age),
    ):
        if not enabled:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        parts.append(pd.DataFrame({col: s}))
        valid = s.dropna()
        if len(valid):
            meta.continuous_ranges[col] = (float(valid.min()), float(valid.max()))

    if vars_spec.road_code and "road_code" in df.columns:
        s = pd.to_numeric(df["road_code"], errors="coerce")
        parts.append(pd.DataFrame({"road_code": s}))
        valid = s.dropna()
        if len(valid):
            meta.continuous_ranges["road_code"] = (float(valid.min()), float(valid.max()))

    X = pd.concat(parts, axis=1) if parts else pd.DataFrame(index=df.index)

    if vars_spec.road_width_dummy and "road_width_label" in df.columns:
        rw = df["road_width_label"].fillna("(null)").astype(str)
        cats = sorted(rw.unique().tolist())
        meta.road_width_labels = cats
        meta.road_width_reference = cats[0] if len(cats) > 1 else None
        d = pd.get_dummies(rw, prefix="road", drop_first=True)
        X = pd.concat([X, d], axis=1)

    if vars_spec.zone_type_dummy and "zone_type" in df.columns:
        zt = df["zone_type"].copy()
        if unified and "asset_type" in df.columns:
            zt = zt.where(df["asset_type"].astype(str) != "detached")
        zt = zt.fillna("(null)").astype(str)
        cats = sorted(zt.unique().tolist())
        if len(cats) > 1 or (len(cats) == 1 and cats[0] != "(null)"):
            meta.zone_types = cats
            meta.zone_reference = cats[0] if len(cats) > 1 else None
            d = pd.get_dummies(zt, prefix="zone", drop_first=True)
            X = pd.concat([X, d], axis=1)

    if vars_spec.building_use_dummy and "building_use" in df.columns:
        bu = df["building_use"].fillna("(null)").astype(str)
        cats = sorted(bu.unique().tolist())
        meta.building_uses = cats
        meta.building_use_reference = cats[0] if len(cats) > 1 else None
        d = pd.get_dummies(bu, prefix="use", drop_first=True)
        X = pd.concat([X, d], axis=1)

    if unified and vars_spec.asset_type_dummy and "asset_type" in df.columns:
        at = df["asset_type"].fillna("(null)").astype(str)
        cats = sorted(at.unique().tolist())
        meta.asset_types = cats
        meta.asset_type_reference = "commercial" if "commercial" in cats else (cats[0] if cats else None)
        d = pd.get_dummies(at, prefix="atype", drop_first=True)
        X = pd.concat([X, d], axis=1)

    if vars_spec.region_leaf_dummy and region_col and region_col in df.columns:
        rs = _norm_col(df, region_col).replace("", "(null)")
        valid = rs[(rs != "(null)") & (rs.notna())]
        cats = sorted(valid.unique().tolist())
        if len(cats) >= 2:
            meta.region_leaves = cats
            meta.region_reference = cats[0]
            d = pd.get_dummies(rs, prefix="loc", drop_first=True)
            if not d.empty:
                X = pd.concat([X, d], axis=1)

    if X.empty:
        return y, X, None

    meta.feature_columns = list(X.columns)
    mask = y.notna()
    if response_scale == "log":
        mask &= y > 0
    for c in X.columns:
        mask &= pd.to_numeric(X[c], errors="coerce").notna()
    y_out = y.loc[mask]
    if response_scale == "log":
        y_out = np.log(y_out.astype(float))
    return y_out, X.loc[mask].astype(float), meta


def _input_to_x_row(
    meta: DesignMeta,
    vars_spec: RegressionVariableSpec,
    inp: RegressionPredictRequest,
) -> pd.DataFrame:
    row = {c: 0.0 for c in meta.feature_columns}

    for col in meta.continuous_ranges:
        if not getattr(vars_spec, col, False):
            continue
        val = getattr(inp, col, None)
        if val is None:
            raise ValueError(f"{_CONT_LABELS.get(col, col)} 값이 필요합니다.")
        row[col] = float(val)

    if vars_spec.zone_type_dummy and meta.zone_types:
        z = inp.zone_type or meta.zone_reference or meta.zone_types[0]
        if z not in meta.zone_types:
            raise ValueError(f"용도지역 '{z}' — 모형에 없는 값입니다.")
        for c in meta.feature_columns:
            if c.startswith("zone_"):
                row[c] = 0.0
        if meta.zone_reference and z != meta.zone_reference:
            key = f"zone_{z}"
            if key in row:
                row[key] = 1.0

    if vars_spec.building_use_dummy and meta.building_uses:
        u = inp.building_use or meta.building_use_reference or meta.building_uses[0]
        if u not in meta.building_uses:
            raise ValueError(f"건축물용도 '{u}' — 모형에 없는 값입니다.")
        for c in meta.feature_columns:
            if c.startswith("use_"):
                row[c] = 0.0
        if meta.building_use_reference and u != meta.building_use_reference:
            key = f"use_{u}"
            if key in row:
                row[key] = 1.0

    if vars_spec.road_width_dummy and meta.road_width_labels:
        rw = inp.road_width_label or meta.road_width_reference or meta.road_width_labels[0]
        if rw not in meta.road_width_labels:
            raise ValueError(f"도로조건 '{rw}' — 모형에 없는 값입니다.")
        for c in meta.feature_columns:
            if c.startswith("road_"):
                row[c] = 0.0
        if meta.road_width_reference and rw != meta.road_width_reference:
            key = f"road_{rw}"
            if key in row:
                row[key] = 1.0

    if vars_spec.asset_type_dummy and meta.asset_types:
        at = inp.predict_asset_type or meta.asset_type_reference or meta.asset_types[0]
        if at not in meta.asset_types:
            raise ValueError(f"유형 '{at}' — 모형에 없는 값입니다.")
        for c in meta.feature_columns:
            if c.startswith("atype_"):
                row[c] = 0.0
        if meta.asset_type_reference and at != meta.asset_type_reference:
            key = f"atype_{at}"
            if key in row:
                row[key] = 1.0

    if vars_spec.region_leaf_dummy and meta.region_leaves:
        leaf = inp.region_leaf or meta.region_reference or meta.region_leaves[0]
        if leaf not in meta.region_leaves:
            raise ValueError(f"지역 '{leaf}' — 모형에 없는 값입니다.")
        for c in meta.feature_columns:
            if str(c).startswith("loc_"):
                row[c] = 0.0
        if meta.region_reference and leaf != meta.region_reference:
            key = f"loc_{leaf}"
            if key in row:
                row[key] = 1.0

    return pd.DataFrame([row])[meta.feature_columns]


def _extrapolation_warnings(
    meta: DesignMeta,
    inp: RegressionPredictRequest,
) -> list[str]:
    out: list[str] = []
    for col, (lo, hi) in meta.continuous_ranges.items():
        val = getattr(inp, col, None)
        if val is None:
            continue
        if val < lo or val > hi:
            label = _CONT_LABELS.get(col, col)
            out.append(f"외삽 — {label} 학습범위 [{lo:,.1f}, {hi:,.1f}] 밖 (입력 {val:,.1f})")
    return out


def _scope_for_level(
    wide_df: pd.DataFrame,
    req: RegressionRunRequest,
    admin_level: AdminLevel,
    addr4_city: bool,
    mode: CompareMode,
) -> pd.DataFrame:
    if admin_level == "sigungu":
        return _filter_sigungu(wide_df, req)
    if admin_level == "gu":
        return _filter_gu(wide_df, req)
    if admin_level == "eupmyeondong":
        if mode == "three_way":
            return _filter_parent_eups(wide_df, req.ri_list, addr4_city)
        return _filter_eup_leaf(wide_df, req, addr4_city)
    if admin_level == "beopjungri":
        return _filter_ri_picks(wide_df, req.ri_list)
    return _filter_sigungu(wide_df, req)


def _fit_ols(
    df: pd.DataFrame,
    vars_spec: RegressionVariableSpec,
    admin_level: str | None,
    scope_label: str | None = None,
    *,
    unified: bool = False,
    response_scale: ResponseScale = "linear",
    addr4_city: bool = False,
) -> RegressionLevelResult:
    import statsmodels.api as sm

    level = admin_level or "sigungu"
    if df.empty:
        return RegressionLevelResult(
            admin_level=level,
            scope_label=scope_label,
            n=0,
            equation="",
            coefficients=[],
            warning="표본 0건",
        )

    region_col = None
    if vars_spec.region_leaf_dummy and level == "eupmyeondong":
        region_col = _eup_leaf_column(addr4_city)

    y, X, meta = _build_design_matrix(
        df,
        vars_spec,
        unified=unified,
        response_scale=response_scale,
        region_col=region_col,
    )
    n = len(y)

    if n < 10 or X.empty:
        warn = f"n={n} — 회귀 비권장 (권장 n≥30)"
        if response_scale == "log":
            warn += " · log(금액) 모형"
        return RegressionLevelResult(
            admin_level=level,
            scope_label=scope_label,
            n=n,
            equation="",
            coefficients=[],
            warning=warn,
        )

    vif_entries = _compute_vif(X)
    vif_warn = _vif_warning(vif_entries)

    X = sm.add_constant(X)
    model = sm.OLS(y, X).fit()

    coefs = [
        RegressionCoeff(
            name=str(name),
            estimate=float(model.params[name]),
            std_err=float(model.bse[name]) if name in model.bse else None,
            t_value=float(model.tvalues[name]) if name in model.tvalues else None,
            p_value=float(model.pvalues[name]) if name in model.pvalues else None,
        )
        for name in model.params.index
    ]
    sig = sum(1 for c in coefs if c.name != "const" and c.p_value is not None and c.p_value < 0.05)

    warn = None
    if n < 30:
        warn = f"n={n} — 참고용 (권장 n≥30)"
    if response_scale == "log":
        log_note = "종속=log(금액) — 계수는 log-선형"
        warn = f"{warn} · {log_note}" if warn else log_note
    if vif_warn:
        warn = f"{warn} · {vif_warn}" if warn else vif_warn
    if vars_spec.region_leaf_dummy and level == "eupmyeondong":
        loc_cols = sum(1 for c in X.columns if str(c).startswith("loc_"))
        if loc_cols == 0:
            ref_note = "지역 1개뿐 — 지역 더미 미적용"
            warn = f"{warn} · {ref_note}" if warn else ref_note
        elif loc_cols >= MAX_REGION_DUMMY_WARN:
            ref = meta.region_reference if meta else "?"
            many_note = (
                f"지역 더미 {loc_cols + 1}개(기준={ref}) — 과적합·n 대비 변수 주의"
            )
            warn = f"{warn} · {many_note}" if warn else many_note
        elif meta and meta.region_reference:
            ref_note = f"지역 더미 기준={meta.region_reference}"
            warn = f"{warn} · {ref_note}" if warn else ref_note

    y_price = pd.to_numeric(df["price"], errors="coerce").loc[y.index].to_numpy()
    mape = _insample_mape_pct(y_price, model, response_scale=response_scale)

    return RegressionLevelResult(
        admin_level=level,
        scope_label=scope_label,
        n=n,
        r_squared=float(model.rsquared),
        adj_r_squared=float(model.rsquared_adj),
        f_statistic=float(model.fvalue) if model.fvalue is not None else None,
        f_p_value=float(model.f_pvalue) if model.f_pvalue is not None else None,
        significant_count=sig,
        equation="",
        coefficients=coefs,
        vif=vif_entries,
        vif_warning=vif_warn,
        predict_options=_meta_to_predict_options(meta),
        warning=warn,
        mape=mape,
    )


def _correlations(df: pd.DataFrame, vars_spec: RegressionVariableSpec) -> list[CorrelationSeries]:
    out: list[CorrelationSeries] = []
    y = pd.to_numeric(df["price"], errors="coerce")
    specs = []
    if vars_spec.gross_area:
        specs.append(("gross_area", "연면적"))
    if vars_spec.land_area:
        specs.append(("land_area", "대지면적"))
    if vars_spec.building_age:
        specs.append(("building_age", "연식"))
    if vars_spec.road_width_dummy:
        specs.append(("road_width_label", "도로조건"))
    elif vars_spec.road_code:
        specs.append(("road_code", "도로"))
    for col, label in specs:
        x = pd.to_numeric(df[col], errors="coerce")
        m = x.notna() & y.notna()
        if m.sum() < 2:
            continue
        xv, yv = x[m], y[m]
        r = float(xv.corr(yv)) if xv.std() > 0 else None
        step = max(1, len(xv) // 500)
        pts = [
            CorrelationPoint(x=float(xv.iloc[i]), y=float(yv.iloc[i]))
            for i in range(0, len(xv), step)
        ]
        out.append(CorrelationSeries(variable=col, label=label, pearson_r=r, points=pts))
    return out


def _sigungu_label(req: RegressionRunRequest) -> str:
    if req.addr2:
        from app.flat_sido_region import is_flat_sido_addr2

        if is_flat_sido_addr2(req.addr2):
            return req.addr1 or "시도"
        return f"{req.addr2} 시군구"
    if req.addr1:
        return f"{req.addr1} 전체"
    return "전국"


def _gu_label(req: RegressionRunRequest, df: pd.DataFrame) -> str:
    names = _effective_gu_names(req, df)
    if not names:
        return "구"
    if len(names) == 1:
        return names[0]
    preview = ", ".join(names[:3])
    if len(names) > 3:
        preview += f" 외 {len(names) - 3}개"
    return f"선택 구 {len(names)}개 ({preview})"


def _eup_label(req: RegressionRunRequest, addr4_city: bool) -> str:
    if addr4_city:
        leaves = effective_addr4_list(None, req.addr4_list)
    else:
        leaves = effective_addr3_list(req.addr3, req.addr3_list)
    return format_scope_label(leaves, suffix="읍면동")


def _parent_eup_label(ri_list: list[RiPick]) -> str:
    parents = sorted({p.eup.strip() for p in ri_list if p.eup.strip()})
    return format_scope_label(parents, suffix="읍·면")


def _ri_label(ri_list: list[RiPick]) -> str:
    names = [p.ri.strip() for p in ri_list if p.ri.strip()]
    return format_scope_label(names, suffix="리")


def run_regression(conn, req: RegressionRunRequest) -> RegressionRunResponse:
    wide_df, req, addr4_city, mode = _prepare_regression_scope(conn, req)
    unified = is_unified(req.asset_type)
    scale = req.response_scale
    fit_kw = dict(unified=unified, response_scale=scale, addr4_city=addr4_city)

    if mode == "sigungu_only":
        scoped = _filter_sigungu(wide_df, req)
        primary = _fit_ols(scoped, req.variables, "sigungu", _sigungu_label(req), **fit_kw)
        corrs = _correlations(scoped, req.variables)
        return RegressionRunResponse(
            primary=primary,
            comparisons=[],
            correlations=corrs,
            correlation_admin_level="sigungu",
            correlation_scope_label=_sigungu_label(req),
            correlation_n=len(scoped),
        )

    if mode == "two_way":
        eup = _filter_eup_leaf(wide_df, req, addr4_city)
        if addr4_city:
            gu = _filter_gu(wide_df, req)
            primary = _fit_ols(gu, req.variables, "gu", _gu_label(req, wide_df), **fit_kw)
        else:
            sig = _filter_sigungu(wide_df, req)
            primary = _fit_ols(sig, req.variables, "sigungu", _sigungu_label(req), **fit_kw)
        comp = _fit_ols(eup, req.variables, "eupmyeondong", _eup_label(req, addr4_city), **fit_kw)
        corrs = _correlations(eup, req.variables)
        return RegressionRunResponse(
            primary=primary,
            comparisons=[comp],
            correlations=corrs,
            correlation_admin_level="eupmyeondong",
            correlation_scope_label=_eup_label(req, addr4_city),
            correlation_n=len(eup),
        )

    # three_way
    ri_list = req.ri_list
    if addr4_city:
        gu = _filter_gu(wide_df, req)
        primary = _fit_ols(gu, req.variables, "gu", _gu_label(req, wide_df), **fit_kw)
    else:
        sig = _filter_sigungu(wide_df, req)
        primary = _fit_ols(sig, req.variables, "sigungu", _sigungu_label(req), **fit_kw)
    eup = _filter_parent_eups(wide_df, ri_list, addr4_city)
    ri = _filter_ri_picks(wide_df, ri_list)
    comp_eup = _fit_ols(eup, req.variables, "eupmyeondong", _parent_eup_label(ri_list), **fit_kw)
    comp_ri = _fit_ols(ri, req.variables, "beopjungri", _ri_label(ri_list), **fit_kw)
    corr_df = ri if len(ri) >= 10 else eup
    use_ri = len(ri) >= 10
    corrs = _correlations(corr_df, req.variables)
    return RegressionRunResponse(
        primary=primary,
        comparisons=[comp_eup, comp_ri],
        correlations=corrs,
        correlation_admin_level="beopjungri" if use_ri else "eupmyeondong",
        correlation_scope_label=_ri_label(ri_list) if use_ri else _parent_eup_label(ri_list),
        correlation_n=len(corr_df),
    )


def predict_regression(conn, req: RegressionPredictRequest) -> RegressionPredictResponse:
    import statsmodels.api as sm

    wide_df, req, addr4_city, mode = _prepare_regression_scope(conn, req)
    df = _scope_for_level(wide_df, req, req.admin_level, addr4_city, mode)

    scope_label = None
    if req.admin_level == "sigungu":
        scope_label = _sigungu_label(req)
    elif req.admin_level == "gu":
        scope_label = _gu_label(req, wide_df)
    elif req.admin_level == "eupmyeondong":
        scope_label = (
            _parent_eup_label(req.ri_list)
            if mode == "three_way"
            else _eup_label(req, addr4_city)
        )
    elif req.admin_level == "beopjungri":
        scope_label = _ri_label(req.ri_list)

    region_col = None
    if req.variables.region_leaf_dummy and req.admin_level == "eupmyeondong":
        region_col = _eup_leaf_column(addr4_city)

    y, X, meta = _build_design_matrix(
        df,
        req.variables,
        unified=is_unified(req.asset_type),
        response_scale=req.response_scale,
        region_col=region_col,
    )
    n = len(y)
    if n < 10 or X.empty or meta is None:
        raise ValueError(f"예측 불가 — scope n={n} (최소 10건 필요)")

    X_const = sm.add_constant(X)
    model = sm.OLS(y, X_const).fit()

    x_new = _input_to_x_row(meta, req.variables, req)
    x_new_const = sm.add_constant(x_new, has_constant="add")
    frame = model.get_prediction(x_new_const).summary_frame(alpha=0.05)

    warnings = _extrapolation_warnings(meta, req)
    if n < 30:
        warnings.insert(0, f"n={n} — 참고용 (권장 n≥30, 예측구간 넓음)")
    if req.response_scale == "log":
        warnings.insert(0, "log(금액) 모형 — 예측값은 exp(ŷ) 역변환")

    row = frame.iloc[0]
    scale = req.response_scale
    return RegressionPredictResponse(
        admin_level=req.admin_level,
        scope_label=scope_label,
        n=n,
        y_hat=_back_transform(float(row["mean"]), scale),
        pi_lower=_back_transform(float(row["obs_ci_lower"]), scale),
        pi_upper=_back_transform(float(row["obs_ci_upper"]), scale),
        ci_lower=_back_transform(float(row["mean_ci_lower"]), scale),
        ci_upper=_back_transform(float(row["mean_ci_upper"]), scale),
        response_scale=scale,
        warnings=warnings,
    )
