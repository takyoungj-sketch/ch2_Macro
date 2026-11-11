"""OLS 회귀 — 금액(만원) 종속."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
import pandas as pd

from app.built.asset_scope import apply_asset_type_filter, is_unified
from app.regression_missing import treatment_label
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
    PartialRegressionSeries,
    FunnelReason,
    FunnelStep,
    PredictOptions,
    DesignColumnNote,
    RegressionCoeff,
    RegressionLevelResult,
    SampleBreakdown,
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

if TYPE_CHECKING:
    from app.built.regression.price_index import YearIndex

CompareMode = Literal["sigungu_only", "gu_only", "two_way", "three_way"]
CONTINUOUS_VARS = frozenset(
    {
        "gross_area",
        "land_area",
        "building_age",
        "region_population",
        "region_land_p50",
        "region_apt_p50",
        "region_apt_n",
        "region_comm_p50",
        "region_comm_n",
        "assessed_land_price",
    }
)
LOGLOG_X_COLS = frozenset({"gross_area", "land_area"})
_CONT_LABELS = {
    "gross_area": "연면적",
    "land_area": "대지면적",
    "building_age": "연식",
    "road_code": "도로",
    "region_population": "지역인구",
    "region_land_p50": "지역토지가격",
    "region_apt_p50": "지역아파트가격",
    "region_apt_n": "지역아파트거래량",
    "region_comm_p50": "지역상가가격",
    "region_comm_n": "지역상가거래량",
    "assessed_land_price": "개별공시지가",
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


def _region_dummy_column(
    vars_spec: RegressionVariableSpec,
    level: AdminLevel | str | None,
    *,
    addr4_city: bool,
) -> str | None:
    """분석 초점에 맞는 지역 더미 원천 컬럼을 반환한다."""
    if not vars_spec.region_leaf_dummy:
        return None
    if level == "beopjungri":
        return "addr5"
    if level == "eupmyeondong":
        return _eup_leaf_column(addr4_city)
    return None


def _duan_smearing(residuals: np.ndarray) -> float:
    r = np.asarray(residuals, dtype=float)
    r = r[np.isfinite(r)]
    if r.size == 0:
        return 1.0
    return float(np.mean(np.exp(r)))


def _uses_log_y(scale: ResponseScale) -> bool:
    return scale in ("log", "loglog")


def _is_loglog(scale: ResponseScale) -> bool:
    return scale == "loglog"


def _insample_pred_price(model, *, response_scale: ResponseScale) -> np.ndarray:
    """적합값을 원척도 금액(만원)으로. log 종속이면 Duan 보정을 건다.

    MAPE와 잔차 진단(P5)이 **같은 예측값**을 써야 집단별 MAPE가 화면 상단 MAPE와 맞는다.
    """
    fitted = np.asarray(model.fittedvalues, dtype=float)
    if _uses_log_y(response_scale):
        return np.exp(fitted) * _duan_smearing(model.resid.to_numpy())
    return fitted


def _insample_mape_pct(
    y_price: np.ndarray,
    pred_price: np.ndarray,
) -> float | None:
    """적합값 기준 in-sample MAPE(%), 종속은 항상 금액(만원) 원척도."""
    y = np.asarray(y_price, dtype=float)
    pred = np.asarray(pred_price, dtype=float)
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
    structure_groups: list[str] = field(default_factory=list)
    road_width_labels: list[str] = field(default_factory=list)
    asset_types: list[str] = field(default_factory=list)
    zone_reference: str | None = None
    building_use_reference: str | None = None
    structure_reference: str | None = None
    road_width_reference: str | None = None
    asset_type_reference: str | None = None
    n_excluded_missing: int = 0
    region_leaves: list[str] = field(default_factory=list)
    region_reference: str | None = None
    continuous_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)
    log_x_columns: frozenset[str] = field(default_factory=frozenset)
    response_scale: ResponseScale = "linear"
    dropped_columns: list[DesignColumnNote] = field(default_factory=list)


def _meta_to_predict_options(meta: DesignMeta | None) -> PredictOptions | None:
    if meta is None or not meta.feature_columns:
        return None
    return PredictOptions(
        zone_types=meta.zone_types,
        building_uses=meta.building_uses,
        structure_groups=meta.structure_groups,
        road_width_labels=meta.road_width_labels,
        asset_types=meta.asset_types,
        zone_reference=meta.zone_reference,
        building_use_reference=meta.building_use_reference,
        structure_reference=meta.structure_reference,
        road_width_reference=meta.road_width_reference,
        asset_type_reference=meta.asset_type_reference,
        region_leaves=meta.region_leaves,
        region_reference=meta.region_reference,
        continuous=[
            ContinuousRange(name=k, min=v[0], max=v[1]) for k, v in meta.continuous_ranges.items()
        ],
    )


def _back_transform(value: float, scale: ResponseScale) -> float:
    if _uses_log_y(scale):
        return float(np.exp(value))
    return float(value)


def _build_where(
    req: RegressionRunRequest,
    *,
    conn=None,
    include_subregion: bool = True,
    include_partial: bool | None = None,
    defer_age_filter: bool = False,
    exclude_direct: bool | None = None,
) -> tuple[str, dict]:
    clauses = ["is_valid = true"]
    params: dict[str, Any] = {}
    apply_asset_type_filter(clauses, params, req.asset_type)
    if include_subregion:
        from app.region_scope import apply_analysis_region_scope, apply_region_scope

        used_units = apply_analysis_region_scope(
            clauses,
            params,
            codes=getattr(req, "region_codes", None) or [],
            code_level=getattr(req, "region_code_level", None),
            addr_keys=getattr(req, "region_addrs", None) or [],
            conn=conn,
        )
        if not used_units and req.addr1 and req.addr2:
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
        elif not used_units and req.addr1:
            from app.region_sido import addr1_scope_sql

            clauses.append(
                addr1_scope_sql(conn, params, addr1=req.addr1, table="built_transactions")
            )
            from app.built.filters import apply_addr3_filter, apply_addr4_filter, apply_ri_filter

            apply_addr3_filter(clauses, params, req.addr3, req.addr3_list)
            apply_addr4_filter(clauses, params, None, req.addr4_list)
            apply_ri_filter(clauses, params, req.ri_list)
    elif _has_unit_region_scope(req):
        # wide fetch: 교차 시군구 단위의 상위 시군구 합집합
        from app.flat_sido_region import apply_addr2_scope, is_flat_sido_addr2
        from app.region_scope import parse_region_addr_keys

        if req.addr1:
            from app.region_sido import addr1_scope_sql

            clauses.append(
                addr1_scope_sql(conn, params, addr1=req.addr1, table="built_transactions")
            )
        if req.addr2 and is_flat_sido_addr2(req.addr2):
            # 세종 등 flat sido — 지도 단위 addr2(읍·면명)와 토큰이 섞여도 원장은 addr2 NULL
            apply_addr2_scope(clauses, params, addr1=req.addr1, addr2=req.addr2)
        else:
            triples = parse_region_addr_keys(getattr(req, "region_addrs", None) or [])
            addr2s = sorted({t[1] for t in triples if t[1]})
            if req.addr2 and req.addr2 not in addr2s:
                addr2s.append(req.addr2)
            if len(addr2s) > 1:
                clauses.append("addr2 = ANY(:unit_wide_addr2s)")
                params["unit_wide_addr2s"] = addr2s
            elif len(addr2s) == 1:
                apply_addr2_scope(clauses, params, addr1=req.addr1, addr2=addr2s[0])
            elif req.addr1 and req.addr2:
                apply_addr2_scope(clauses, params, addr1=req.addr1, addr2=req.addr2)
    elif req.addr1 and req.addr2:
        from app.flat_sido_region import apply_addr2_scope

        apply_addr2_scope(clauses, params, addr1=req.addr1, addr2=req.addr2)
    elif req.addr1:
        from app.region_sido import addr1_scope_sql

        clauses.append(addr1_scope_sql(conn, params, addr1=req.addr1, table="built_transactions"))
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

    enrich = bool(getattr(req, "enrich", False))
    apply_sample_filters_from_request(
        clauses, params, req, skip_zone=enrich, skip_age=defer_age_filter
    )
    from app.built.partial_ownership import apply_partial_ownership_filter

    flag = bool(getattr(req, "include_partial", False)) if include_partial is None else include_partial
    apply_partial_ownership_filter(clauses, include_partial=flag)
    from app.built.filters import apply_direct_trade_filter

    direct = bool(getattr(req, "exclude_direct_trades", False)) if exclude_direct is None else exclude_direct
    apply_direct_trade_filter(clauses, exclude=direct)
    return " AND ".join(clauses), params


def _fetch_df(conn, req: RegressionRunRequest, *, include_subregion: bool = True) -> pd.DataFrame:
    from sqlalchemy import text

    enrich_age = bool(getattr(req, "enrich", False))
    where, params = _build_where(
        req, conn=conn, include_subregion=include_subregion, defer_age_filter=enrich_age
    )
    inner = f"""
        SELECT id AS transaction_id, price, gross_area, land_area, building_age, road_code, road_width_label,
               zone_type, building_use, asset_type, contract_year,
               addr1, addr2, addr3, addr4, addr5,
               sigungu_code, eupmyeondong_code, beopjungri_code,
               is_partial_ownership, transaction_hash
        FROM built_transactions
        WHERE {where}
    """
    from app.built.enrichment_join import apply_wrapped_zone_columns, wrap_tx_enrichment
    from app.built.enrichment_policy import split_zone_filter

    enrich = bool(getattr(req, "enrich", False))
    _, outer_zones = split_zone_filter(enrich=enrich, zone_types=list(req.zone_types or []))
    if outer_zones:
        params = dict(params)
        params["zone_types"] = outer_zones
    sql = wrap_tx_enrichment(inner, enrich=enrich, zone_types=outer_zones)
    rows = conn.execute(text(sql), params).mappings().all()
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    if enrich:
        df = apply_wrapped_zone_columns(df)
        # F-1: 동의 시에만 회귀 연식을 대장 사용승인연도로 보강, 연식 범위는 보강 뒤 적용
        from app.built.regression.age_backfill import apply_age_range, backfill_age_from_ledger

        df = backfill_age_from_ledger(df)
        df = apply_age_range(
            df, getattr(req, "building_age_min", None), getattr(req, "building_age_max", None)
        )
    else:
        df = df.drop(columns=["transaction_hash"], errors="ignore")
    return df.sort_values("transaction_id", kind="stable").reset_index(drop=True) if "transaction_id" in df else df


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
) -> tuple[pd.DataFrame, RegressionRunRequest, bool, CompareMode, int]:
    from sqlalchemy import text

    where_all, params_all = _build_where(
        req, conn=conn, include_subregion=True, include_partial=True
    )
    partial_tx_count = int(
        conn.execute(
            text(
                f"""
                SELECT COUNT(*) FROM built_transactions
                WHERE {where_all} AND is_partial_ownership IS TRUE
                """
            ),
            params_all,
        ).scalar()
        or 0
    )
    direct_excluded = 0
    if bool(getattr(req, "exclude_direct_trades", False)):
        where_direct, params_direct = _build_where(
            req, conn=conn, include_subregion=True, exclude_direct=False
        )
        direct_excluded = int(
            conn.execute(
                text(
                    f"""
                    SELECT COUNT(*) FROM built_transactions
                    WHERE {where_direct} AND btrim(deal_type::text) = '직거래'
                    """
                ),
                params_direct,
            ).scalar()
            or 0
        )
    wide_df = _fetch_df(conn, req, include_subregion=False)
    if req.exclude_outliers_iqr:
        wide_df = _iqr_filter(wide_df, "price", req.outlier_iqr_multiplier)
    wide_df.attrs["direct_excluded_n"] = direct_excluded
    addr4_city_hint = _resolve_addr4_city(conn, req, wide_df)
    req = _normalize_leaf_fields(req, wide_df, addr4_city=addr4_city_hint)
    addr4_city = _finalize_addr4_city(conn, req, wide_df)
    mode = _compare_mode(req, addr4_city)
    return wide_df, req, addr4_city, mode, partial_tx_count


def _has_unit_region_scope(req: RegressionRunRequest) -> bool:
    codes = [str(c).strip() for c in (getattr(req, "region_codes", None) or []) if str(c).strip()]
    addrs = [str(a).strip() for a in (getattr(req, "region_addrs", None) or []) if str(a).strip()]
    return bool(codes or addrs)


def _unit_addr_triples(req: RegressionRunRequest) -> list[tuple[str, str, str]]:
    from app.region_scope import parse_region_addr_keys

    return parse_region_addr_keys(getattr(req, "region_addrs", None) or [])


def _has_leaf_selection(req: RegressionRunRequest, addr4_city: bool) -> bool:
    if _has_unit_region_scope(req):
        return True
    if addr4_city:
        return bool(effective_addr4_list(None, req.addr4_list))
    return bool(effective_addr3_list(req.addr3, req.addr3_list))


def _has_gu_selection(req: RegressionRunRequest, addr4_city: bool) -> bool:
    """구-동 구조에서 구(addr3)만 선택·동 미선택."""
    if not addr4_city:
        return False
    return bool(effective_addr3_list(req.addr3, req.addr3_list))


def _compare_mode(req: RegressionRunRequest, addr4_city: bool) -> CompareMode:
    if req.ri_list:
        return "three_way"
    if _has_leaf_selection(req, addr4_city):
        return "two_way"
    if _has_gu_selection(req, addr4_city):
        return "gu_only"
    return "sigungu_only"


def _focus_admin_level(req: RegressionRunRequest, addr4_city: bool) -> AdminLevel:
    """사용자 최종 선택 행정 층위 = 분석 초점."""
    if req.ri_list:
        return "beopjungri"
    if _has_unit_region_scope(req):
        lv = (getattr(req, "region_code_level", None) or "eupmyeondong").strip().lower()
        return "beopjungri" if lv == "beopjungri" else "eupmyeondong"
    if _has_leaf_selection(req, addr4_city):
        return "eupmyeondong"
    if _has_gu_selection(req, addr4_city):
        return "gu"
    return "sigungu"


def _upper_admin_levels(focus: AdminLevel, addr4_city: bool) -> list[AdminLevel]:
    """초점보다 상위 행정 층위 (가까운 순)."""
    if focus == "beopjungri":
        levels: list[AdminLevel] = ["eupmyeondong"]
        if addr4_city:
            levels.append("gu")
        levels.append("sigungu")
        return levels
    if focus == "eupmyeondong":
        if addr4_city:
            return ["gu", "sigungu"]
        return ["sigungu"]
    if focus == "gu":
        return ["sigungu"]
    return []


def _eup_scope_for_level(
    admin_level: AdminLevel,
    focus: AdminLevel,
    req: RegressionRunRequest,
) -> Literal["leaf", "parent"]:
    if admin_level == "eupmyeondong" and focus == "beopjungri" and req.ri_list:
        return "parent"
    return "leaf"


def _label_for_level(
    req: RegressionRunRequest,
    wide_df: pd.DataFrame,
    level: AdminLevel,
    addr4_city: bool,
    *,
    eup_scope: Literal["leaf", "parent"] = "leaf",
) -> str:
    if level == "sigungu":
        return _sigungu_label(req)
    if level == "gu":
        return _gu_label(req, wide_df)
    if level == "eupmyeondong":
        if eup_scope == "parent":
            return _parent_eup_label(req.ri_list)
        return _eup_label(req, addr4_city)
    if level == "beopjungri":
        return _ri_label(req.ri_list)
    return ""


def _coef_display_name(name: str, *, response_scale: ResponseScale = "linear") -> str:
    if name == "const":
        return "절편"
    if name in _CONT_LABELS:
        label = _CONT_LABELS[name]
        if name == "assessed_land_price" or (_is_loglog(response_scale) and name in LOGLOG_X_COLS):
            return f"log({label})"
        return label
    if name.startswith("zone_"):
        return name[5:]
    if name.startswith("use_"):
        return name[4:]
    if name.startswith("struct_"):
        return name[7:]
    if name.startswith("road_"):
        return name[5:]
    if name.startswith("atype_"):
        return name[6:]
    if name.startswith("loc_"):
        return name[4:]
    return name


_EQUATION_SIG_P = 0.1


def _format_equation(
    coefs: list[RegressionCoeff],
    *,
    response_scale: ResponseScale,
) -> str:
    """회귀식 문자열 — 유의(p<0.1) 변수만 (프론트 전체보기 기본과 동일)."""
    dep = "log(금액)" if _uses_log_y(response_scale) else "금액"
    intercept = next((c for c in coefs if c.name == "const"), None)
    if intercept is None:
        return f"{dep} = —"

    def _fmt(v: float) -> str:
        if abs(v) >= 100:
            return f"{v:,.0f}"
        if abs(v) >= 1:
            return f"{v:,.1f}".rstrip("0").rstrip(".")
        return f"{v:.4f}".rstrip("0").rstrip(".")

    parts = [f"{dep} = {_fmt(intercept.estimate)}"]
    others = [c for c in coefs if c.name != "const"]
    sig = [c for c in others if c.p_value is not None and c.p_value < _EQUATION_SIG_P]
    sig.sort(key=lambda c: c.p_value if c.p_value is not None else 1.0)
    for c in sig:
        sign = "+" if c.estimate >= 0 else "−"
        mag = _fmt(abs(c.estimate))
        label = _coef_display_name(c.name, response_scale=response_scale)
        parts.append(f" {sign} {mag}·{label}")
    return "".join(parts)


def _norm_col(df: pd.DataFrame, col: str) -> pd.Series:
    return df[col].astype(str).str.strip()


def _ledger_addr2_series(df: pd.DataFrame) -> pd.Series:
    if "addr2" not in df.columns:
        return pd.Series("", index=df.index, dtype=str)
    s = df["addr2"]
    return s.where(s.notna(), "").astype(str).str.strip()


def _addr2_row_match(df: pd.DataFrame, a2: str) -> pd.Series:
    from app.flat_sido_region import is_flat_sido_addr2

    if is_flat_sido_addr2(a2):
        return _ledger_addr2_series(df) == ""
    return _norm_col(df, "addr2") == a2.strip()


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


def _filter_by_region_units(
    df: pd.DataFrame,
    req: RegressionRunRequest,
    *,
    conn=None,
) -> pd.DataFrame:
    """region_codes / region_addrs 로 행 필터 (교차 시군구 포함)."""
    if df.empty or not _has_unit_region_scope(req):
        return df
    codes = [str(c).strip() for c in (getattr(req, "region_codes", None) or []) if str(c).strip()]
    triples = _unit_addr_triples(req)
    lv = (getattr(req, "region_code_level", None) or "eupmyeondong").strip().lower()
    # D-028: GIS/canonical → ledger historical expand
    if codes and conn is not None:
        from app.region_canonical import expand_to_ledger_codes

        if lv == "beopjungri":
            codes = expand_to_ledger_codes(conn, codes) or codes
        elif lv == "eupmyeondong":
            from app.region_scope import _eupmyeondong_ledger_emd_codes

            codes = _eupmyeondong_ledger_emd_codes(conn, codes)
    mask = pd.Series(False, index=df.index)

    if codes:
        if lv == "beopjungri" and "beopjungri_code" in df.columns:
            mask = mask | _norm_col(df, "beopjungri_code").isin(set(codes))
            # NULL beopjungri 원장: region_codes 명칭(addr5)으로 보강
            if conn is not None and "addr5" in df.columns:
                try:
                    from sqlalchemy import text as sa_text

                    nm = conn.execute(
                        sa_text(
                            """
                            SELECT btrim(sido_name::text), btrim(sigungu_name::text),
                                   btrim(beopjungri_name::text)
                            FROM region_codes
                            WHERE COALESCE(is_active, TRUE)
                              AND btrim(beopjungri_code::text) = ANY(:codes)
                            """
                        ),
                        {"codes": list(codes)},
                    ).fetchall()
                    for a1n, a2n, rin in nm:
                        if not rin:
                            continue
                        row_ok = _norm_col(df, "addr5") == rin
                        if "addr1" in df.columns and a1n:
                            row_ok = row_ok & (_norm_col(df, "addr1") == a1n)
                        if "addr2" in df.columns and a2n:
                            row_ok = row_ok & (_norm_col(df, "addr2") == a2n)
                        mask = mask | row_ok
                except Exception:
                    pass
        else:
            emd_set: set[str] = set(codes)
            if "eupmyeondong_code" in df.columns:
                mask = mask | _norm_col(df, "eupmyeondong_code").isin(emd_set)
            if "beopjungri_code" in df.columns:
                mask = mask | _norm_col(df, "beopjungri_code").str.slice(0, 8).isin(emd_set)

    has_a1 = "addr1" in df.columns
    has_a2 = "addr2" in df.columns
    for a1, a2, leaf in triples:
        leaf_ok = (
            (_norm_col(df, "addr3") == leaf)
            | (_norm_col(df, "addr4") == leaf)
            | (_norm_col(df, "addr5") == leaf)
        )
        if has_a1 and has_a2:
            row_ok = (_norm_col(df, "addr1") == a1) & _addr2_row_match(df, a2)
            mask = mask | (row_ok & leaf_ok)
        elif has_a2:
            mask = mask | (_addr2_row_match(df, a2) & leaf_ok)
        else:
            mask = mask | leaf_ok

    return df[mask]


def _filter_eup_leaf(
    df: pd.DataFrame,
    req: RegressionRunRequest,
    addr4_city: bool,
    *,
    conn=None,
) -> pd.DataFrame:
    """선택 읍·면·동(복수 합집합). region_* 단위가 있으면 그쪽 우선."""
    if _has_unit_region_scope(req):
        return _filter_by_region_units(df, req, conn=conn)
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


def _enabled_category_columns(
    vars_spec: RegressionVariableSpec,
    region_col: str | None,
) -> list[str]:
    columns: list[str] = []
    if vars_spec.road_width_dummy:
        columns.append("road_width_label")
    if vars_spec.zone_type_dummy:
        columns.append("zone_type")
    if vars_spec.building_use_dummy:
        columns.append("building_use")
    if vars_spec.structure_dummy:
        columns.append("structure_group")
    if vars_spec.asset_type_dummy:
        columns.append("asset_type")
    if vars_spec.region_leaf_dummy and region_col:
        columns.append(region_col)
    return columns


_DUMMY_KINDS: dict[str, str] = {
    "road_": "도로조건",
    "zone_": "용도지역",
    "use_": "건축물용도",
    "struct_": "구조",
    "atype_": "유형",
    "loc_": "지역",
}
_DUMMY_META_LISTS: dict[str, str] = {
    "road_": "road_width_labels",
    "zone_": "zone_types",
    "use_": "building_uses",
    "struct_": "structure_groups",
    "atype_": "asset_types",
    "loc_": "region_leaves",
}


def _dummy_prefix(name: str) -> str | None:
    s = str(name)
    for prefix in _DUMMY_KINDS:
        if s.startswith(prefix):
            return prefix
    return None


def prune_design_columns(X: pd.DataFrame) -> tuple[list[str], list[DesignColumnNote]]:
    """적합 직전 설계행렬에서 계수를 정할 수 없는 더미 열을 고른다 (B-12).

    1. 최종 표본(결측·IQR·필터 뒤)에서 값이 **모두 0인 더미** — 그 범주 거래가 없다.
    2. **유형 더미가 건축물용도 더미에 내포**되어 완전 중복 — 같은 건축물용도 안에서
       유형이 한 값뿐이면 유형 열은 상수+용도 더미의 선형결합이다. 유형 더미를 뺀다.
       (예: 상업+단독 통합에서 ``atype_detached`` = 단독 + 다가구)

    두 경우 모두 열 공간이 그대로라 적합값·예측값은 바뀌지 않는다. 연속 변수와
    ``const`` 는 건드리지 않는다. 학습 fold에도 같은 규칙을 쓴다.
    """
    keep: list[str] = []
    dropped: list[DesignColumnNote] = []
    for col in X.columns:
        prefix = _dummy_prefix(col)
        if prefix is not None and not (X[col].to_numpy(dtype=float) != 0).any():
            label = str(col)[len(prefix):]
            dropped.append(
                DesignColumnNote(
                    name=str(col),
                    reason="all_zero",
                    detail=f"{_DUMMY_KINDS[prefix]} '{label}' 거래가 최종 표본에 없어 제외",
                )
            )
            continue
        keep.append(str(col))
    atype_cols = [c for c in keep if c.startswith("atype_")]
    use_cols = [c for c in keep if c.startswith("use_")]
    if atype_cols and use_cols and len(X):
        groups = X[use_cols].astype(float).round(12).apply(tuple, axis=1)
        for col in atype_cols:
            per_group = X[col].astype(float).groupby(groups).nunique(dropna=False)
            if bool((per_group <= 1).all()):
                keep.remove(col)
                dropped.append(
                    DesignColumnNote(
                        name=col,
                        reason="nested_duplicate",
                        detail="유형 더미가 건축물용도 더미와 완전히 겹쳐(내포) 유형 더미를 제외 — "
                        "유형 차이는 건축물용도 계수에 담깁니다",
                    )
                )
    return keep, dropped


def nonidentifiable_columns(exog: np.ndarray, names: list[str]) -> list[str]:
    """rank 부족 설계에서 한 값으로 정해지지 않는 계수 이름 (B-12).

    열 노름으로 정규화한 설계행렬의 영공간 벡터에 성분이 있는 열이 식별 불가다.
    rank가 꽉 차면 빈 목록. 예측값(열 공간)은 이와 무관하게 계산된다.
    """
    arr = np.asarray(exog, dtype=float)
    if arr.ndim != 2 or arr.shape[1] == 0 or arr.shape[0] == 0:
        return []
    norms = np.linalg.norm(arr, axis=0)
    norms[norms == 0.0] = 1.0
    scaled = arr / norms
    rank = int(np.linalg.matrix_rank(scaled))
    if rank >= arr.shape[1]:
        return []
    _u, _s, vt = np.linalg.svd(scaled, full_matrices=True)
    null = vt[rank:]
    weight = np.abs(null).max(axis=0)
    return [names[j] for j in range(len(names)) if weight[j] > 1e-6]


def _build_design_matrix(
    df: pd.DataFrame,
    vars_spec: RegressionVariableSpec,
    *,
    unified: bool = False,
    response_scale: ResponseScale = "linear",
    region_col: str | None = None,
    categorical_missing: str = "keep_unknown",
) -> tuple[pd.Series, pd.DataFrame, DesignMeta | None]:
    """종속 y와 독립 X (상수 미포함), 설계 메타."""
    from app.regression_missing import categorical_dummies, drop_unknown_rows

    if df.empty:
        return pd.Series(dtype=float), pd.DataFrame(), None

    excluded = 0
    if categorical_missing == "drop":
        df, excluded = drop_unknown_rows(df, _enabled_category_columns(vars_spec, region_col))
        if df.empty:
            return pd.Series(dtype=float), pd.DataFrame(), None

    y = pd.to_numeric(df["price"], errors="coerce")
    parts: list[pd.DataFrame] = []
    meta = DesignMeta(response_scale=response_scale, n_excluded_missing=excluded)

    for col, enabled in (
        ("gross_area", vars_spec.gross_area),
        ("land_area", vars_spec.land_area),
        ("building_age", vars_spec.building_age),
        ("region_population", vars_spec.region_population),
        ("region_land_p50", vars_spec.region_land_p50),
        ("region_apt_p50", vars_spec.region_apt_p50),
        ("region_apt_n", vars_spec.region_apt_n),
        ("region_comm_p50", vars_spec.region_comm_p50),
        ("region_comm_n", vars_spec.region_comm_n),
        ("assessed_land_price", vars_spec.assessed_land_price),
    ):
        if not enabled or col not in df.columns:
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
        d, cats, ref = categorical_dummies(df["road_width_label"], "road")
        meta.road_width_labels = cats
        meta.road_width_reference = ref
        if not d.empty:
            X = pd.concat([X, d], axis=1)

    if vars_spec.zone_type_dummy and "zone_type" in df.columns:
        d, cats, ref = categorical_dummies(df["zone_type"], "zone")
        meta.zone_types = cats
        meta.zone_reference = ref
        if not d.empty:
            X = pd.concat([X, d], axis=1)

    if vars_spec.building_use_dummy and "building_use" in df.columns:
        d, cats, ref = categorical_dummies(df["building_use"], "use")
        meta.building_uses = cats
        meta.building_use_reference = ref
        if not d.empty:
            X = pd.concat([X, d], axis=1)

    if vars_spec.structure_dummy and "structure_group" in df.columns:
        d, cats, ref = categorical_dummies(df["structure_group"], "struct")
        meta.structure_groups = cats
        meta.structure_reference = ref
        if not d.empty:
            X = pd.concat([X, d], axis=1)

    if unified and vars_spec.asset_type_dummy and "asset_type" in df.columns:
        from app.regression_missing import normalize_categories

        normalized = normalize_categories(df["asset_type"])
        preferred = "commercial" if (normalized == "commercial").any() else None
        d, cats, ref = categorical_dummies(df["asset_type"], "atype", reference=preferred)
        meta.asset_types = cats
        meta.asset_type_reference = ref
        if not d.empty:
            X = pd.concat([X, d], axis=1)

    if vars_spec.region_leaf_dummy and region_col and region_col in df.columns:
        d, cats, ref = categorical_dummies(df[region_col], "loc")
        real = [level for level in cats if level != "미상"]
        if len(real) >= 2 and ref:
            meta.region_leaves = real
            meta.region_reference = ref
            if not d.empty:
                X = pd.concat([X, d], axis=1)

    if X.empty:
        return y, X, None

    meta.feature_columns = list(X.columns)
    mask = y.notna()
    if _uses_log_y(response_scale):
        mask &= y > 0

    log_cols: set[str] = set()
    if _is_loglog(response_scale):
        for col in LOGLOG_X_COLS:
            if col not in X.columns:
                continue
            s = pd.to_numeric(X[col], errors="coerce")
            mask &= s > 0
            log_cols.add(col)
    if "assessed_land_price" in X.columns:
        s = pd.to_numeric(X["assessed_land_price"], errors="coerce")
        mask &= s > 0
        log_cols.add("assessed_land_price")
    meta.log_x_columns = frozenset(log_cols)

    for c in X.columns:
        mask &= pd.to_numeric(X[c], errors="coerce").notna()

    X_out = X.loc[mask].astype(float).copy()
    for col in meta.log_x_columns:
        X_out[col] = np.log(X_out[col])

    # B-12: 모든 표본 단계 뒤 — 전부 0인 더미·내포 유형 더미 제외
    keep_cols, dropped_cols = prune_design_columns(X_out)
    if dropped_cols:
        X_out = X_out.loc[:, keep_cols]
        meta.feature_columns = list(keep_cols)
        meta.dropped_columns = dropped_cols
        for note in dropped_cols:
            if note.reason != "all_zero":
                continue
            prefix = _dummy_prefix(note.name)
            attr = _DUMMY_META_LISTS.get(prefix or "")
            if attr:
                level = note.name[len(prefix):]  # type: ignore[arg-type]
                setattr(meta, attr, [v for v in getattr(meta, attr) if v != level])

    y_out = y.loc[mask]
    if _uses_log_y(response_scale):
        y_out = np.log(y_out.astype(float))
    return y_out, X_out, meta


_VAR_DROP_ORDER = (
    "missing_gross",
    "missing_land",
    "missing_age",
    "missing_road",
    "missing_assessed",
    "nonpositive_area",
    "other",
)
_VAR_DROP_LABELS = {
    "missing_gross": "연면적 결측",
    "missing_land": "대지면적 결측",
    "missing_age": "연식 결측",
    "missing_road": "도로코드 결측",
    "missing_assessed": "개별공시지가 결측",
    "nonpositive_area": "면적 0 이하 (log-log)",
    "other": "기타 결측",
}
_CATEGORY_DROP_LABELS = {
    "road_width_label": "도로조건 미상",
    "zone_type": "용도지역 미상",
    "building_use": "건축물용도 미상",
    "structure_group": "구조 미상",
    "asset_type": "유형 미상",
}
_CATEGORY_NAME = {
    "road_width_label": "도로조건",
    "zone_type": "용도지역",
    "building_use": "건축물용도",
    "structure_group": "구조",
    "asset_type": "유형",
}


def _cell_num(row: pd.Series, col: str) -> float:
    if col not in row.index:
        return float("nan")
    return pd.to_numeric(row[col], errors="coerce")


def _row_drop_reason(
    row: pd.Series,
    vars_spec: RegressionVariableSpec,
    *,
    response_scale: ResponseScale,
) -> tuple[str, str]:
    """적합에서 빠진 한 행의 첫 사유. 한 행은 한 칸만 탄다."""
    price = _cell_num(row, "price")
    if pd.isna(price):
        return "no_price", "금액 없음"
    if _uses_log_y(response_scale) and float(price) <= 0:
        return "nonpositive_price", "금액 0 이하 (로그 모형)"
    if vars_spec.gross_area:
        g = _cell_num(row, "gross_area")
        if pd.isna(g):
            return "missing_gross", _VAR_DROP_LABELS["missing_gross"]
        if _is_loglog(response_scale) and float(g) <= 0:
            return "nonpositive_area", _VAR_DROP_LABELS["nonpositive_area"]
    if vars_spec.land_area:
        a = _cell_num(row, "land_area")
        if pd.isna(a):
            return "missing_land", _VAR_DROP_LABELS["missing_land"]
        if _is_loglog(response_scale) and float(a) <= 0:
            return "nonpositive_area", _VAR_DROP_LABELS["nonpositive_area"]
    if vars_spec.building_age and pd.isna(_cell_num(row, "building_age")):
        return "missing_age", _VAR_DROP_LABELS["missing_age"]
    if vars_spec.assessed_land_price:
        p = _cell_num(row, "assessed_land_price")
        if pd.isna(p) or float(p) <= 0:
            return "missing_assessed", _VAR_DROP_LABELS["missing_assessed"]
    if vars_spec.road_code and pd.isna(_cell_num(row, "road_code")):
        return "missing_road", _VAR_DROP_LABELS["missing_road"]
    return "other", _VAR_DROP_LABELS["other"]


def _count_funnel_reasons(pairs: list[tuple[str, str]]) -> list[FunnelReason]:
    counts: dict[str, int] = {}
    labels: dict[str, str] = {}
    seen: list[str] = []
    for code, label in pairs:
        if code not in counts:
            seen.append(code)
            labels[code] = label
            counts[code] = 0
        counts[code] += 1
    ordered = [c for c in _VAR_DROP_ORDER if c in counts] + [c for c in seen if c not in _VAR_DROP_ORDER]
    return [FunnelReason(code=c, label=labels[c], n=counts[c]) for c in ordered]


def _category_drop_reason(row: pd.Series, columns: list[str]) -> tuple[str, str] | None:
    """결측 거래 제외일 때, 켠 범주가 미상인 첫 열."""
    from app.regression_missing import UNKNOWN, normalize_categories

    for column in columns:
        if column not in row.index:
            continue
        if normalize_categories(pd.Series([row[column]])).iloc[0] != UNKNOWN:
            continue
        if column not in _CATEGORY_DROP_LABELS:
            return column, "지역 미상"
        return column, _CATEGORY_DROP_LABELS[column]
    return None


def build_sample_funnel(
    df: pd.DataFrame,
    vars_spec: RegressionVariableSpec,
    *,
    fitted_index: pd.Index,
    response_scale: ResponseScale,
    categorical_missing: str = "keep_unknown",
    category_columns: list[str] | None = None,
) -> SampleBreakdown:
    """조회 거래에서 최종 표본이 어떻게 남는지.

    한 행은 한 사유만 탄다. 금액 → 숫자 결측 → 범주 결측 순이다.
    범주 결측은 '결측 거래 제외'를 켠 식에서만 행을 뺀다.
    """
    n_pool = int(len(df))
    n_fit = int(len(fitted_index))
    funnel: list[FunnelStep] = [
        FunnelStep(code="pool", label="조회 거래", n=n_pool, kind="remain"),
    ]
    if n_pool == 0:
        funnel.append(FunnelStep(code="fit", label="최종 표본", n=0, kind="remain"))
        return SampleBreakdown(n_pool=0, n_fit=0, funnel=funnel)

    dropped = df.loc[df.index.difference(fitted_index)]
    price_pairs: list[tuple[str, str]] = []
    var_pairs: list[tuple[str, str]] = []
    cat_pairs: list[tuple[str, str]] = []
    cat_cols = category_columns or []
    numeric_also_unknown = 0
    for _, row in dropped.iterrows():
        code, label = _row_drop_reason(row, vars_spec, response_scale=response_scale)
        if code in ("no_price", "nonpositive_price"):
            price_pairs.append((code, label))
            continue
        if code != "other":
            var_pairs.append((code, label))
            if categorical_missing == "drop" and _category_drop_reason(row, cat_cols) is not None:
                numeric_also_unknown += 1
            continue
        if categorical_missing == "drop":
            cat = _category_drop_reason(row, cat_cols)
            if cat is not None:
                cat_pairs.append(cat)
                continue
        var_pairs.append((code, label))

    if price_pairs:
        funnel.append(
            FunnelStep(
                code="price_drop",
                label="금액 없음·0 이하",
                n=len(price_pairs),
                kind="drop",
                note="로그 모형은 금액이 0보다 커야 합니다.",
                reasons=_count_funnel_reasons(price_pairs),
            )
        )
    if var_pairs:
        numeric_note = "켠 숫자 변수에 값이 없거나 0 이하인 거래입니다. 개별공시지가를 켜면 그 결측도 여기 포함됩니다."
        if numeric_also_unknown:
            numeric_note += (
                f" 이 중 범주 미상도 있는 거래 {numeric_also_unknown}건은 여기서 한 번만 셉니다."
            )
        funnel.append(
            FunnelStep(
                code="var_drop",
                label="숫자 결측 제외",
                n=len(var_pairs),
                kind="drop",
                note=numeric_note,
                reasons=_count_funnel_reasons(var_pairs),
            )
        )
    if cat_pairs:
        funnel.append(
            FunnelStep(
                code="cat_drop",
                label="범주 결측 제외",
                n=len(cat_pairs),
                kind="drop",
                note="결측 거래 제외를 켜서, 선택한 범주가 미상인 거래를 뺐습니다.",
                reasons=_count_funnel_reasons(cat_pairs),
            )
        )
    funnel.append(
        FunnelStep(
            code="fit",
            label="최종 표본",
            n=n_fit,
            kind="remain",
            note="금액·숫자·범주 조건을 반영한 회귀식의 표본입니다.",
        )
    )
    if vars_spec.building_age:
        from app.built.regression.age_backfill import ledger_backfill_count

        backfilled = ledger_backfill_count(df, fitted_index)
        if backfilled:
            funnel.append(
                FunnelStep(
                    code="ledger_age",
                    label="대장 보강 연식",
                    n=backfilled,
                    kind="info",
                    note=(
                        "최종 표본 중 실거래 건축연도가 없어 대장 사용승인연도로 연식을 채운 거래입니다. "
                        "대장 정보 동의 시에만 적용하며 원장은 바꾸지 않습니다."
                    ),
                )
            )
    return SampleBreakdown(n_pool=n_pool, n_fit=n_fit, funnel=funnel)


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
        fval = float(val)
        if col in meta.log_x_columns:
            if fval <= 0:
                raise ValueError(f"{_CONT_LABELS.get(col, col)} — log-log 모형은 0보다 큰 값이 필요합니다.")
            row[col] = float(np.log(fval))
        else:
            row[col] = fval

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

    if vars_spec.structure_dummy and meta.structure_groups:
        s = inp.structure_group or meta.structure_reference or meta.structure_groups[0]
        if s not in meta.structure_groups:
            raise ValueError(f"구조 '{s}' — 모형에 없는 값입니다.")
        for c in meta.feature_columns:
            if c.startswith("struct_"):
                row[c] = 0.0
        if meta.structure_reference and s != meta.structure_reference:
            key = f"struct_{s}"
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
    from app.built.regression.extrapolation import assess_prediction

    inputs = {
        col: getattr(inp, col, None)
        for col in meta.continuous_ranges
    }
    _level, _assessments, warnings = assess_prediction(
        meta.continuous_ranges,
        inputs,
        labels=_CONT_LABELS,
    )
    return warnings


def _scope_for_level(
    wide_df: pd.DataFrame,
    req: RegressionRunRequest,
    admin_level: AdminLevel,
    addr4_city: bool,
    mode: CompareMode,
    *,
    eup_scope: Literal["leaf", "parent"] = "leaf",
    conn=None,
) -> pd.DataFrame:
    if admin_level == "sigungu":
        return _filter_sigungu(wide_df, req)
    if admin_level == "gu":
        return _filter_gu(wide_df, req)
    if admin_level == "eupmyeondong":
        if eup_scope == "parent" and req.ri_list:
            return _filter_parent_eups(wide_df, req.ri_list, addr4_city)
        return _filter_eup_leaf(wide_df, req, addr4_city, conn=conn)
    if admin_level == "beopjungri":
        return _filter_ri_picks(wide_df, req.ri_list)
    return _filter_sigungu(wide_df, req)


def _focus_cv_mape(
    df: pd.DataFrame,
    vars_spec: RegressionVariableSpec,
    *,
    unified: bool,
    response_scale: ResponseScale,
    region_col: str | None,
    enabled: bool,
    diagnostics: dict | None = None,
) -> tuple[float | None, int, float | None, str | None]:
    """초점 식 하나의 연도 롤링 CV. 모형 추천의 탐색 CV·마지막 연도 확인과 같다."""
    def unavailable(code, reason, status="unavailable"):
        if diagnostics is not None:
            diagnostics.update({key: dict(status=status, method=method, requested_folds=0,
                reason_code=code, reason=reason) for key, method in (("search", "rolling_year"), ("confirm", "last_year"))})
    if not enabled:
        unavailable("not_requested", "이 단계는 학습 적합만 제공하며 연도별 검증을 실행하지 않습니다.", "not_run")
        return None, 0, None, None
    if "contract_year" not in df.columns:
        unavailable("missing_year", "계약연도가 없어 연도별 검증을 실행하지 못했습니다.")
        return None, 0, None, "CV-MAPE는 계약연도가 있어야 계산합니다."
    from app.built.regression.selection.fit import rolling_time_cv_split

    try:
        search, folds, confirm, _confirm_folds, skip = rolling_time_cv_split(
            df,
            vars_spec,
            unified=unified,
            response_scale=response_scale,
            region_col=region_col, diagnostics=diagnostics,
        )
    except Exception:  # noqa: BLE001 — CV 실패가 회귀 결과를 막으면 안 된다
        unavailable("fit_failure", "연도별 검증의 적합 또는 예측이 실패했습니다.")
        return None, 0, None, "CV-MAPE를 계산하지 못했습니다."
    if search is None:
        return None, int(folds or 0), confirm, skip or "CV-MAPE는 계약연도가 두 해 미만이면 계산하지 않습니다."
    return search, int(folds or 0), confirm, skip


def _fit_ols(
    df: pd.DataFrame,
    vars_spec: RegressionVariableSpec,
    admin_level: str | None,
    scope_label: str | None = None,
    *,
    unified: bool = False,
    response_scale: ResponseScale = "linear",
    addr4_city: bool = False,
    year_index: "YearIndex | None" = None,
    with_residuals: bool = False,
    with_cv: bool = False,
    categorical_missing: str = "keep_unknown",
) -> RegressionLevelResult:
    import statsmodels.api as sm

    level = admin_level or "sigungu"
    # 거래가를 기준시점 수준으로 환산한 뒤 적합한다 (D-075). 계수가 시간 추세를 흡수하지
    # 않게 하는 것이 목적이고, 적합에 쓰는 표본만 환산한다 — 산점도·거래목록은 명목가 유지.
    if year_index is not None:
        from app.built.regression.price_index import deflate_prices

        df = deflate_prices(df, year_index)
    if df.empty:
        return RegressionLevelResult(
            admin_level=level,
            scope_label=scope_label,
            n=0,
            equation="",
            coefficients=[],
            warning="표본 0건",
            sample=build_sample_funnel(
                df,
                vars_spec,
                fitted_index=df.index[:0],
                response_scale=response_scale,
                categorical_missing=categorical_missing,
            ),
        )

    region_col = None
    region_col = _region_dummy_column(
        vars_spec,
        level,
        addr4_city=addr4_city,
    )

    y, X, meta = _build_design_matrix(
        df,
        vars_spec,
        unified=unified,
        response_scale=response_scale,
        region_col=region_col,
        categorical_missing=categorical_missing,
    )
    n = len(y)

    if n < 10 or X.empty:
        warn = f"n={n} — 회귀 비권장 (권장 n≥30)"
        if _uses_log_y(response_scale):
            warn += " · log(금액) 모형"
        return RegressionLevelResult(
            admin_level=level,
            scope_label=scope_label,
            n=n,
            equation="",
            coefficients=[],
            warning=warn,
            sample=build_sample_funnel(
                df,
                vars_spec,
                fitted_index=y.index,
                response_scale=response_scale,
                categorical_missing=categorical_missing,
                category_columns=_enabled_category_columns(vars_spec, region_col),
            ),
        )

    vif_entries = _compute_vif(X)
    vif_warn = _vif_warning(vif_entries)

    X = sm.add_constant(X)
    model = sm.OLS(y, X).fit()
    from app.regression_sample_judge import identification_note, judge_exog, provision_note, sample_notes

    verdict = judge_exog(model.model.exog)
    if verdict.tier == "blocked":
        return RegressionLevelResult(
            admin_level=level,
            scope_label=scope_label,
            n=int(verdict.n),
            equation="",
            coefficients=[],
            warning=sample_notes(verdict)[0],
            sample=build_sample_funnel(
                df,
                vars_spec,
                fitted_index=y.index,
                response_scale=response_scale,
                categorical_missing=categorical_missing,
                category_columns=_enabled_category_columns(vars_spec, region_col),
            ),
        )

    # B-12: 열을 정리한 뒤에도 rank 부족이면 식별 불가 계수의 SE·t·p 를 비운다.
    unident = set(nonidentifiable_columns(model.model.exog, [str(c) for c in model.params.index]))
    coefs = [
        RegressionCoeff(
            name=str(name),
            estimate=float(model.params[name]),
            std_err=float(model.bse[name]) if name in model.bse and name not in unident else None,
            t_value=float(model.tvalues[name]) if name in model.tvalues and name not in unident else None,
            p_value=float(model.pvalues[name]) if name in model.pvalues and name not in unident else None,
            identifiable=name not in unident,
        )
        for name in model.params.index
    ]
    sig = sum(
        1
        for c in coefs
        if c.name != "const" and c.identifiable and c.p_value is not None and c.p_value < 0.05
    )

    warn = provision_note(verdict)
    ident = identification_note(verdict)
    if ident:
        warn = f"{warn} · {ident}" if warn else ident
    identification_warning = None
    if unident:
        shown = ", ".join(_coef_display_name(c, response_scale=response_scale) for c in sorted(unident) if c != "const")
        identification_warning = (
            f"설계 열 {verdict.n_columns}개 중 독립 계수 {verdict.rank}개 — "
            f"{len(unident)}개 계수가 한 값으로 정해지지 않습니다"
            + (f" ({shown})" if shown else "")
            + ". 이 계수들은 p값·유의 계수 집계에서 제외합니다. 추정금액(예측값)은 계산되지만 "
            "해당 변수의 효과는 따로 해석할 수 없습니다."
        )
    if _uses_log_y(response_scale):
        if _is_loglog(response_scale):
            log_note = "종속·면적=log — log-log (광평수 외삽에 유리)"
        else:
            log_note = "종속=log(금액) — semi-log (극단 외삽 시 exp 폭발 주의)"
        warn = f"{warn} · {log_note}" if warn else log_note
    if vif_warn:
        warn = f"{warn} · {vif_warn}" if warn else vif_warn
    if categorical_missing != "drop":
        from app.regression_missing import rare_unknown_warning

        rare = rare_unknown_warning(
            df.loc[y.index],
            [
                (column, _CATEGORY_NAME.get(column, "지역"))
                for column in _enabled_category_columns(vars_spec, region_col)
            ],
        )
        if rare:
            warn = f"{warn} · {rare}" if warn else rare
    if vars_spec.region_leaf_dummy and level in {"eupmyeondong", "beopjungri"}:
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
    elif vars_spec.region_leaf_dummy:
        # 시군구·구는 그 단위 자체가 표본 경계라 지역 간 차이를 담을 열이 없다.
        # 초점과 사양이 달라지므로 화면·AI가 우열 비교로 읽지 않도록 사실을 남긴다.
        drop_note = "지역 더미 제외 — 이 단계가 표본 경계 (초점과 변수 구성 다름)"
        warn = f"{warn} · {drop_note}" if warn else drop_note

    y_price = pd.to_numeric(df["price"], errors="coerce").loc[y.index].to_numpy()
    pred_price = _insample_pred_price(model, response_scale=response_scale)
    mape = _insample_mape_pct(y_price, pred_price)
    validation = {}
    cv_mape, cv_folds, confirm_cv_mape, confirm_cv_note = _focus_cv_mape(
        df,
        vars_spec,
        unified=unified,
        response_scale=response_scale,
        region_col=region_col,
        enabled=with_cv, diagnostics=validation,
    )

    # 잔차 진단은 초점 모형만 (P5). 상위 행정층 비교에는 이 화면이 없고, 그쪽 n은
    # 수만 건까지 가므로 영향도 계산을 매번 돌릴 이유가 없다.
    residuals = None
    if with_residuals:
        from app.built.regression.residuals import build_residual_diagnostics

        try:
            residuals = build_residual_diagnostics(
                df,
                model,
                y_price=y_price,
                pred_price=pred_price,
                fitted_index=y.index,
                leaf_col=_eup_leaf_column(addr4_city),
                unified=unified,
            )
        except Exception:  # noqa: BLE001 — 진단 실패가 회귀 결과를 막으면 안 된다
            residuals = None

    from app.regression_contracts import build_analysis_context
    return RegressionLevelResult(
        analysis=build_analysis_context(
            reference_categories={"용도지역": meta.zone_reference, "건축물 용도": meta.building_use_reference,
                "구조": meta.structure_reference, "도로조건": meta.road_width_reference,
                "유형": meta.asset_type_reference, "지역": meta.region_reference} if meta else {},
            request=dict(variables=vars_spec.model_dump(), admin_level=level, scope_label=scope_label,
                categorical_missing=categorical_missing, response_scale=response_scale),
            rows=df.loc[y.index], coefficients=coefs, observation_unit="transaction",
            target="price", target_unit="만원", response_scale=response_scale,
            fit_n=n, exog=model.model.exog, source_n=len(df), metrics=[
                dict(key="mape", role="training", scale="price", value=mape, n=n, method="in_sample"),
                dict(key="mape", role="selection_validation", scale="price", value=cv_mape,
                    method="rolling_year", reason=validation.get("search", {}).get("reason"), validation=validation.get("search")),
                dict(key="mape", role="independent_confirmation", scale="price", value=confirm_cv_mape,
                    method="last_year", reason=validation.get("confirm", {}).get("reason") or confirm_cv_note or "마지막 연도 확인을 제공하지 않습니다.", validation=validation.get("confirm")),
            ]),
        admin_level=level,
        scope_label=scope_label,
        n=n,
        r_squared=float(model.rsquared),
        adj_r_squared=float(model.rsquared_adj),
        f_statistic=float(model.fvalue) if model.fvalue is not None else None,
        f_p_value=float(model.f_pvalue) if model.f_pvalue is not None else None,
        significant_count=sig,
        equation=_format_equation(coefs, response_scale=response_scale),
        coefficients=coefs,
        vif=vif_entries,
        vif_warning=vif_warn,
        predict_options=_meta_to_predict_options(meta),
        warning=warn,
        mape=mape,
        cv_mape=cv_mape,
        cv_folds=cv_folds,
        confirm_cv_mape=confirm_cv_mape,
        confirm_cv_note=confirm_cv_note,
        categorical_missing=categorical_missing,  # type: ignore[arg-type]
        n_excluded_missing=int(meta.n_excluded_missing) if meta else 0,
        missing_treatment_label=treatment_label(
            categorical_missing, int(meta.n_excluded_missing) if meta else 0
        ),
        sample=build_sample_funnel(
            df,
            vars_spec,
            fitted_index=y.index,
            response_scale=response_scale,
            categorical_missing=categorical_missing,
            category_columns=_enabled_category_columns(vars_spec, region_col),
        ),
        residuals=residuals,
        dropped_design_columns=list(meta.dropped_columns) if meta else [],
        identification_warning=identification_warning,
    )


def _continuous_plot_specs(vars_spec: RegressionVariableSpec) -> list[tuple[str, str]]:
    specs: list[tuple[str, str]] = []
    if vars_spec.gross_area:
        specs.append(("gross_area", "연면적"))
    if vars_spec.land_area:
        specs.append(("land_area", "대지면적"))
    if vars_spec.building_age:
        specs.append(("building_age", "연식"))
    if vars_spec.road_code and not vars_spec.road_width_dummy:
        specs.append(("road_code", "도로"))
    return specs


def _subsample_points(xv: pd.Series, yv: pd.Series, *, max_pts: int = 500) -> list[CorrelationPoint]:
    step = max(1, len(xv) // max_pts)
    return [
        CorrelationPoint(x=float(xv.iloc[i]), y=float(yv.iloc[i]))
        for i in range(0, len(xv), step)
    ]


def _correlations(df: pd.DataFrame, vars_spec: RegressionVariableSpec) -> list[CorrelationSeries]:
    if df.empty or "price" not in df.columns:
        return []
    out: list[CorrelationSeries] = []
    y = pd.to_numeric(df["price"], errors="coerce")
    for col, label in _continuous_plot_specs(vars_spec):
        x = pd.to_numeric(df[col], errors="coerce")
        m = x.notna() & y.notna()
        if m.sum() < 2:
            continue
        xv, yv = x[m], y[m]
        r = float(xv.corr(yv)) if xv.std() > 0 else None
        out.append(
            CorrelationSeries(
                variable=col,
                label=label,
                pearson_r=r,
                points=_subsample_points(xv, yv),
                y_axis_label="금액(만원)",
            )
        )
    return out


def _region_col_for_scatter(
    vars_spec: RegressionVariableSpec,
    admin_level: AdminLevel,
    addr4_city: bool,
) -> str | None:
    return _region_dummy_column(
        vars_spec,
        admin_level,
        addr4_city=addr4_city,
    )


def _partial_regression_plots(
    df: pd.DataFrame,
    vars_spec: RegressionVariableSpec,
    *,
    unified: bool = False,
    response_scale: ResponseScale = "linear",
    region_col: str | None = None,
    categorical_missing: str = "keep_unknown",
) -> list[PartialRegressionSeries]:
    """Added-variable plot — OLS와 동일 설계행렬 기준."""
    import statsmodels.api as sm

    y, X, _meta = _build_design_matrix(
        df,
        vars_spec,
        unified=unified,
        response_scale=response_scale,
        region_col=region_col,
        categorical_missing=categorical_missing,
    )
    if len(y) < 10 or X.empty:
        return []

    X_const = sm.add_constant(X, has_constant="add")
    model = sm.OLS(y, X_const).fit()
    unident = set(nonidentifiable_columns(model.model.exog, [str(c) for c in X_const.columns]))
    y_label = "log(금액) 잔차" if _uses_log_y(response_scale) else "금액 잔차"

    out: list[PartialRegressionSeries] = []
    for col, label in _continuous_plot_specs(vars_spec):
        if col not in X.columns:
            continue
        other_cols = [c for c in X.columns if c != col]
        if not other_cols:
            continue

        X_other = sm.add_constant(X[other_cols], has_constant="add")
        y_res = sm.OLS(y, X_other).fit().resid
        x_res = sm.OLS(X[col], X_other).fit().resid

        pr2: float | None = None
        if x_res.std() > 0 and y_res.std() > 0:
            pr2 = round(float(x_res.corr(y_res) ** 2), 4)

        beta = float(model.params[col]) if col in model.params else None
        # B-12: 식별 불가 계수는 계수표와 같이 p값을 비운다.
        p_val = float(model.pvalues[col]) if col in model.pvalues and col not in unident else None

        out.append(
            PartialRegressionSeries(
                variable=col,
                label=label,
                points=_subsample_points(x_res, y_res),
                beta=beta,
                p_value=p_val,
                partial_r_squared=pr2,
                x_axis_label=f"{label} 잔차",
                y_axis_label=y_label,
            )
        )
    return out


def _scatter_scope(
    wide_df: pd.DataFrame,
    req: RegressionRunRequest,
    addr4_city: bool,
    mode: CompareMode,
    *,
    conn=None,
) -> tuple[pd.DataFrame, AdminLevel, str]:
    """산점도 scope = 분석 초점과 동일."""
    focus = _focus_admin_level(req, addr4_city)
    scoped = _scope_for_level(wide_df, req, focus, addr4_city, mode, conn=conn)
    label = _label_for_level(req, wide_df, focus, addr4_city)
    return scoped, focus, label


def _build_scatter_bundle(
    wide_df: pd.DataFrame,
    req: RegressionRunRequest,
    *,
    addr4_city: bool,
    mode: CompareMode,
    unified: bool,
    response_scale: ResponseScale,
    conn=None,
) -> tuple[list[CorrelationSeries], list[PartialRegressionSeries], AdminLevel, str, int]:
    scatter_df, admin_level, scope_label = _scatter_scope(
        wide_df, req, addr4_city, mode, conn=conn
    )
    scatter_df = _lock_recommendation_sample(
        scatter_df,
        req,
        admin_level=admin_level,
        addr4_city=addr4_city,
        mode=mode,
        unified=is_unified(req.asset_type),
    )
    region_col = _region_col_for_scatter(req.variables, admin_level, addr4_city)
    corrs = _correlations(scatter_df, req.variables)
    partials = _partial_regression_plots(
        scatter_df,
        req.variables,
        unified=unified,
        response_scale=response_scale,
        region_col=region_col,
        categorical_missing=req.categorical_missing,
    )
    return corrs, partials, admin_level, scope_label, len(scatter_df)


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
    triples = _unit_addr_triples(req)
    if triples:
        leaves = [t[2] for t in triples]
        # 교차 시군구면 시군구명 포함
        addr2s = {t[1] for t in triples}
        if len(addr2s) > 1:
            labeled = [f"{t[1]} {t[2]}" for t in triples]
            return format_scope_label(labeled, suffix="지역")
        return format_scope_label(leaves, suffix="읍면동")
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


def _window_year_index(wide_df: pd.DataFrame, req: RegressionRunRequest) -> "YearIndex | None":
    """창 전체 시군구 지수. **기본 off**라 제품 경로에서는 None이다 (D-075 보류)."""
    if not getattr(req, "time_adjust", False):
        return None
    from app.built.regression.price_index import estimate_year_index, last_complete_year

    index = estimate_year_index(
        wide_df, max_complete_year=last_complete_year(req.as_of_month)
    )
    return index if index.available else None


def _lock_recommendation_sample(
    df: pd.DataFrame,
    req: RegressionRunRequest,
    *,
    admin_level: str,
    addr4_city: bool,
    mode: CompareMode,
    unified: bool,
) -> pd.DataFrame:
    """추천 추정은 탐색이 고정한 블록 전체의 숫자 결측을 먼저 뺀다."""
    blocks = [str(b).strip() for b in (req.sample_lock_blocks or []) if str(b).strip()]
    if not blocks or df.empty:
        return df
    from app.built.regression.selection.context import SelectionContext, with_complete_case

    ctx = SelectionContext(
        df=df,
        scope_label="",
        admin_level=admin_level,  # type: ignore[arg-type]
        addr4_city=addr4_city,
        mode=mode,
        unified=unified,
    )
    return with_complete_case(ctx, blocks, region_col=None).df


def _with_recommendation_missing_policy(req: RegressionRunRequest) -> RegressionRunRequest:
    blocks = [str(b).strip() for b in (req.sample_lock_blocks or []) if str(b).strip()]
    if not blocks or req.categorical_missing == "keep_unknown":
        return req
    return req.model_copy(update={"categorical_missing": "keep_unknown"})


def run_regression(conn, req: RegressionRunRequest) -> RegressionRunResponse:
    from app.recommendation.scope import built_analysis_scope_from_prepared

    wide_df, req, addr4_city, mode, partial_tx_count = _prepare_regression_scope(conn, req)
    req = _with_recommendation_missing_policy(req)
    unified = is_unified(req.asset_type)
    scale = req.response_scale
    # 시군구 표본 하나로 지수를 세워 focus·상위 비교에 같은 기준시점을 쓴다 (D-075).
    # 수준별로 따로 세우면 비교 대상끼리 기준시점이 어긋난다.
    year_index = _window_year_index(wide_df, req)
    fit_kw = dict(
        unified=unified,
        response_scale=scale,
        addr4_city=addr4_city,
        year_index=year_index,
        categorical_missing=req.categorical_missing,
    )

    scatter_kw = dict(
        addr4_city=addr4_city,
        mode=mode,
        unified=unified,
        response_scale=scale,
    )

    focus = _focus_admin_level(req, addr4_city)
    focus_df = _scope_for_level(wide_df, req, focus, addr4_city, mode, conn=conn)
    focus_df = _lock_recommendation_sample(
        focus_df, req, admin_level=focus, addr4_city=addr4_city, mode=mode, unified=unified
    )
    focus_label = _label_for_level(req, wide_df, focus, addr4_city)
    primary = _fit_ols(
        focus_df,
        req.variables,
        focus,
        focus_label,
        with_residuals=True,
        with_cv=True,
        **fit_kw,
    )

    comparisons: list[RegressionLevelResult] = []
    for level in _upper_admin_levels(focus, addr4_city):
        eup_scope = _eup_scope_for_level(level, focus, req)
        scoped = _scope_for_level(
            wide_df, req, level, addr4_city, mode, eup_scope=eup_scope, conn=conn
        )
        scoped = _lock_recommendation_sample(
            scoped, req, admin_level=level, addr4_city=addr4_city, mode=mode, unified=unified
        )
        label = _label_for_level(
            req, wide_df, level, addr4_city, eup_scope=eup_scope
        )
        comparisons.append(
            _fit_ols(scoped, req.variables, level, label, **fit_kw)
        )

    corrs, partials, s_level, s_label, s_n = _build_scatter_bundle(
        wide_df, req, conn=conn, **scatter_kw
    )
    analysis_scope = built_analysis_scope_from_prepared(
        req,
        wide_df=wide_df,
        addr4_city=addr4_city,
        partial_tx_count=partial_tx_count,
        mode=mode,
        conn=conn,
    )
    from app.built.partial_ownership import format_partial_n_note

    include_partial = bool(getattr(req, "include_partial", False))
    return RegressionRunResponse(
        primary=primary,
        comparisons=comparisons,
        focus_admin_level=focus,
        focus_scope_label=focus_label,
        correlations=corrs,
        partial_regressions=partials,
        correlation_admin_level=s_level,
        correlation_scope_label=s_label,
        correlation_n=s_n,
        analysis_scope=analysis_scope,
        include_partial=include_partial,
        partial_tx_count=partial_tx_count,
        partial_n_note=format_partial_n_note(
            include_partial=include_partial, partial_tx_count=partial_tx_count
        ),
    )


NONPOSITIVE_ESTIMATE_WARNING = (
    "추정값이 0 이하입니다. 선형식 계산 결과이며 실제 거래금액을 의미하지 않습니다. "
    "선형식이 이 입력 조건에 맞지 않을 수 있으니(표본 범위 안에서도 나옵니다) Macro 모형 탐색에서 "
    "다른 척도(log·log-log)나 변수 조합을 확인해 보세요."
)
NEGATIVE_LOWER_BOUND_WARNING = (
    "구간 하한이 0 미만입니다. 선형식 구간 계산의 값을 숨기지 않고 그대로 보이며, "
    "금액의 하한을 뜻하지 않습니다. 하한은 모형 한계의 점검 단서로 읽어 주세요."
)


def nonpositive_estimate_flags(
    y_hat: float, *, ci_lower: float, pi_lower: float
) -> tuple[bool, bool, list[str]]:
    """B-01: 음수·0 추정은 숨기지 않고 성격만 표시한다 (값 변경 없음)."""
    nonpositive = bool(np.isfinite(y_hat) and y_hat <= 0)
    negative_lower = bool(
        not nonpositive
        and ((np.isfinite(ci_lower) and ci_lower < 0) or (np.isfinite(pi_lower) and pi_lower < 0))
    )
    notes: list[str] = []
    if nonpositive:
        notes.append(NONPOSITIVE_ESTIMATE_WARNING)
    elif negative_lower:
        notes.append(NEGATIVE_LOWER_BOUND_WARNING)
    return nonpositive, negative_lower, notes


def predict_regression(conn, req: RegressionPredictRequest) -> RegressionPredictResponse:
    import statsmodels.api as sm

    from app.built.regression.extrapolation import assess_prediction, should_suppress_y_hat
    from app.built.schemas import ContinuousExtrapolation

    scale = req.response_scale
    wide_df, req, addr4_city, mode, _partial_tx_count = _prepare_regression_scope(conn, req)
    req = _with_recommendation_missing_policy(req)
    focus = _focus_admin_level(req, addr4_city)
    eup_scope = _eup_scope_for_level(req.admin_level, focus, req)
    df = _scope_for_level(
        wide_df, req, req.admin_level, addr4_city, mode, eup_scope=eup_scope, conn=conn
    )
    df = _lock_recommendation_sample(
        df, req, admin_level=req.admin_level, addr4_city=addr4_city, mode=mode,
        unified=is_unified(req.asset_type),
    )

    scope_label = _label_for_level(
        req, wide_df, req.admin_level, addr4_city, eup_scope=eup_scope
    )

    region_col = _region_dummy_column(
        req.variables,
        req.admin_level,
        addr4_city=addr4_city,
    )

    # 예상값을 기준시점(창의 마지막 연도) 수준으로 내놓는다 (D-075). 보정 전에는 창 5년치
    # 명목가에 함께 맞춘 계수여서, 상승장에서는 예상값이 과거 수준으로 낮게 나왔다.
    year_index = _window_year_index(wide_df, req)
    if year_index is not None:
        from app.built.regression.price_index import deflate_prices

        df = deflate_prices(df, year_index)

    y, X, meta = _build_design_matrix(
        df,
        req.variables,
        unified=is_unified(req.asset_type),
        response_scale=req.response_scale,
        region_col=region_col,
        categorical_missing=req.categorical_missing,
    )
    n = len(y)
    if n < 10 or X.empty or meta is None:
        raise ValueError(f"예측 불가 — scope n={n} (최소 10건 필요)")

    X_const = sm.add_constant(X)
    model = sm.OLS(y, X_const).fit()
    from app.regression_sample_judge import identification_note, judge_exog, provision_note
    if getattr(req, "expected_model_signature", None) is not None:
        from app.regression_contracts import build_analysis_context, require_model_signature
        context = build_analysis_context(request={}, rows=df.loc[y.index],
            coefficients=[dict(name=str(name), estimate=float(value)) for name, value in model.params.items()],
            observation_unit="transaction", target="price", target_unit="만원",
            response_scale=scale, fit_n=int(model.nobs))
        require_model_signature(req.expected_model_signature, context.model_signature)

    verdict = judge_exog(model.model.exog)
    if verdict.tier == "blocked":
        raise ValueError("계산 불가: " + ", ".join(verdict.reasons))

    x_new = _input_to_x_row(meta, req.variables, req)
    x_new_const = sm.add_constant(x_new, has_constant="add")
    frame = model.get_prediction(x_new_const).summary_frame(alpha=0.05)

    inputs = {col: getattr(req, col, None) for col in meta.continuous_ranges}
    extrap_level, assessments, warnings = assess_prediction(
        meta.continuous_ranges,
        inputs,
        labels=_CONT_LABELS,
    )
    if verdict.tier == "caution":
        warnings.insert(0, f"{provision_note(verdict)} · 예측구간 넓음")
    ident = identification_note(verdict)
    if ident:
        warnings.insert(1 if verdict.tier == "caution" else 0, ident)
    row = frame.iloc[0]
    # log 계열 역변환 (D-074): 점추정·평균CI는 Duan smearing으로 평균 하향편향을 보정한다.
    # exp(ŷ)만 쓰면 조건부 중앙값에 가깝고, MAPE·CV-MAPE는 이미 보정값 기준으로 계산되므로
    # 화면 숫자와 그 옆의 오차율이 서로 다른 추정량을 가리키게 된다.
    # 예측구간은 분위수여서 단조변환에 보존되므로 보정하지 않는다 (집합 엔진과 동일).
    duan = _duan_smearing(model.resid.to_numpy()) if _uses_log_y(scale) else None
    smear = duan if duan is not None else 1.0

    if _is_loglog(scale):
        warnings.insert(0, "log-log 모형 — 면적·금액 log, 연식·더미는 선형")
    elif scale == "log":
        warnings.insert(0, "semi-log — 금액만 log (극단 외삽 주의)")
    if duan is not None:
        warnings.insert(
            1,
            f"역변환 평균 보정 ×{duan:.3f} — 추정값은 exp(ŷ)에 이 계수를 곱한 조건부 평균입니다. "
            "예측구간은 분위수여서 보정하지 않으므로 추정값이 구간의 가운데는 아닙니다.",
        )
    if year_index is not None:
        note = (
            f"{year_index.base_year}년 기준 — 과거 거래가를 시군구 가격지수로 "
            f"{year_index.base_year}년 수준으로 환산한 뒤 적합했습니다."
        )
        if year_index.shrink_keep_ratio < 0.3:
            note += " 연도별 거래가 얇아 보정 폭은 작습니다."
        warnings.insert(0, note)

    y_hat = _back_transform(float(row["mean"]), scale) * smear
    suppressed = should_suppress_y_hat(extrap_level, scale)
    pi_lower = _back_transform(float(row["obs_ci_lower"]), scale)
    ci_lower = _back_transform(float(row["mean_ci_lower"]), scale) * smear
    nonpositive, negative_lower, sign_warnings = nonpositive_estimate_flags(
        y_hat, ci_lower=ci_lower, pi_lower=pi_lower
    )
    for idx, text_ in enumerate(sign_warnings):
        warnings.insert(idx, text_)

    cont_out = [
        ContinuousExtrapolation(
            name=a.name,
            label=a.label,
            min=a.lo,
            max=a.hi,
            value=a.value,
            level=a.level,
            bound_ratio=a.bound_ratio,
        )
        for a in assessments
    ]

    return RegressionPredictResponse(
        admin_level=req.admin_level,
        scope_label=scope_label,
        n=n,
        y_hat=y_hat,
        pi_lower=pi_lower,
        pi_upper=_back_transform(float(row["obs_ci_upper"]), scale),
        ci_lower=ci_lower,
        ci_upper=_back_transform(float(row["mean_ci_upper"]), scale) * smear,
        duan_factor=duan,
        price_base_year=year_index.base_year if year_index is not None else None,
        response_scale=scale,
        extrapolation_level=extrap_level,
        y_hat_suppressed=suppressed,
        nonpositive_estimate=nonpositive,
        negative_lower_bound=negative_lower,
        continuous_assessments=cont_out,
        warnings=warnings,
    )
