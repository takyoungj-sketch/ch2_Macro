"""집합 지역회귀 엔진 — building_stats ⋈ building_attributes, 단지 1행.

주거 단지 그레인 전용. 비주거(도로명 cluster)는 단지속성이 달라 이 모달을 쓰지 않는다.
속성이 있으면 출처(K-apt·표제부)로 빼지 않는다. 구조·시공사 결측은 (미상) 더미.
"""

from __future__ import annotations

from typing import Any, Literal

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.collective.asset_scope import (
    RESIDENTIAL_ASSET_TYPES,
    includes_presale,
    parse_asset_types,
    without_presale_asset_param,
)
from app.collective.building_stats_query import (
    _mart_region_where,
    latest_mart_snapshot,
    stats_as_of_label,
)
from app.collective.danji_attributes import ATTRIBUTES_TABLE, TIER_META
from app.collective.regional_regression.schemas import (
    BlockContribution,
    FittedBuildingRow,
    FunnelReason,
    FunnelStep,
    RegionalRegressionPredictInputs,
    RegionalRegressionRunRequest,
    RegionalRegressionRunResponse,
    RegionalRegressionVariables,
    SampleBreakdown,
)
from app.collective.regression.engine import _duan_smearing, _orig_scale_metrics
from app.collective.regression.presentation import enrich_regression_response
from app.collective.schemas import RegressionCoeff

# 값이 있으면 출처(K-apt vs 표제부)로 빼지 않는다. E는 이름 오탐 위험, Z·공란은 속성 없음.
USABLE_TIERS = frozenset({"A", "B", "C", "D", "F", "T", "P"})
TITLE_USABLE_TIERS = USABLE_TIERS  # 아파트·연립·오피 동일. 예전 연립 전용 별칭.
MIN_FIT_N = 20
MIN_TX = 5
WEIGHT_N0 = 10.0
HOLD_FRAC = 0.25
HOLD_MIN_N = 40
DUMMY_MIN = 5
FITTED_CAP = 400
ASSET_TYPE_ORDER = ("apartment", "rowhouse", "officetel")
ASSET_TYPE_LABELS = {
    "apartment": "아파트",
    "rowhouse": "연립·다세대",
    "officetel": "오피스텔",
    "presale": "분양권",
}
WEAK_NOTE = {
    "structure": "구조는 144개 시군구 실측에서 예측을 개선하지 못했습니다.",
    "builder": "시공사는 144개 시군구 실측에서 예측을 개선하지 못했습니다.",
}
LABELS = {
    "const": "절편",
    "households": "세대수",
    "max_floor": "최고층",
    "building_age": "연식",
    "parking_per_household": "세대당 주차",
    "assessed_land_price": "개별공시지가 (원/㎡, 최신 대표 필지)",
}

ModelType = Literal["linear", "log"]
WeightMode = Literal["equal", "tx"]


def _regression_asset_param(asset_type: str | None) -> str | None:
    """분양권 제외. 분양권만이면 None."""
    raw = (asset_type or "apartment").strip() or "apartment"
    return without_presale_asset_param(raw)


def _selected_regression_types(asset_type: str | None) -> list[str]:
    param = _regression_asset_param(asset_type)
    if not param:
        return []
    parsed = parse_asset_types(param, allowed=RESIDENTIAL_ASSET_TYPES)
    if parsed is None:
        return [t for t in ASSET_TYPE_ORDER]
    return [t for t in ASSET_TYPE_ORDER if t in parsed]


def _is_unified_types(types: list[str]) -> bool:
    return len(types) >= 2


def _is_usable_tier(asset_type: Any, match_tier: Any) -> bool:
    del asset_type  # 유형과 무관. 시그니처는 테스트·호출부 호환.
    t = "" if match_tier is None or (isinstance(match_tier, float) and np.isnan(match_tier)) else str(match_tier).strip()
    if not t:
        return False
    return t in USABLE_TIERS


def _usable_tier_mask(df: pd.DataFrame) -> pd.Series:
    if df.empty or "match_tier" not in df.columns:
        return pd.Series(dtype=bool, index=df.index)
    if "asset_type" not in df.columns:
        return df["match_tier"].isin(USABLE_TIERS)
    vals = [
        _is_usable_tier(at, t) for at, t in zip(df["asset_type"], df["match_tier"])
    ]
    return pd.Series(vals, index=df.index)


def _tx_weights(n_tx: pd.Series) -> np.ndarray:
    n = pd.to_numeric(n_tx, errors="coerce").fillna(0).clip(lower=0).astype(float)
    w = (n / (n + WEIGHT_N0)).to_numpy()
    return np.where(np.isfinite(w) & (w > 0), w, 1e-6)


def _row_weights(work: pd.DataFrame, weight_mode: WeightMode) -> np.ndarray | None:
    if weight_mode != "tx":
        return None
    if "n_tx" not in work.columns:
        return np.ones(len(work), dtype=float)
    return _tx_weights(work["n_tx"])


def _duan_smearing_w(resid: Any, weights: np.ndarray | None) -> float:
    if weights is None:
        return _duan_smearing(resid)
    arr = np.asarray(resid, dtype=float)
    w = np.asarray(weights, dtype=float)
    m = np.isfinite(arr) & np.isfinite(w) & (w > 0)
    if not m.any():
        return 1.0
    return float(np.sum(w[m] * np.exp(arr[m])) / np.sum(w[m]))


def _orig_scale_metrics_w(
    y_price: np.ndarray,
    y_pred: np.ndarray,
    k_params: int,
    weights: np.ndarray | None,
) -> tuple[float | None, float | None, float | None]:
    if weights is None:
        return _orig_scale_metrics(y_price, y_pred, k_params)
    y = np.asarray(y_price, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    w = np.asarray(weights, dtype=float)
    mask = np.isfinite(y) & np.isfinite(p) & np.isfinite(w) & (w > 0)
    y, p, w = y[mask], p[mask], w[mask]
    n = y.size
    if n < 2:
        return None, None, None
    err = y - p
    wsum = float(np.sum(w))
    ybar = float(np.sum(w * y) / wsum)
    ss_res = float(np.sum(w * err**2))
    ss_tot = float(np.sum(w * (y - ybar) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else None
    adj = r2
    if r2 is not None and n - k_params - 1 > 0:
        adj = 1.0 - (1.0 - r2) * (n - 1) / (n - k_params - 1)
    nz = y != 0
    mape = (
        float(np.sum(w[nz] * np.abs(err[nz]) / y[nz]) / np.sum(w[nz])) * 100 if nz.any() else None
    )
    rmse = float(np.sqrt(np.sum(w * err**2) / wsum))
    return (
        round(adj, 4) if adj is not None else None,
        round(mape, 2) if mape is not None else None,
        round(rmse, 1) if rmse is not None else None,
    )


def _latest_snapshot_ym(conn: Connection) -> str | None:
    row = conn.execute(text(f"SELECT MAX(snapshot_ym) FROM {ATTRIBUTES_TABLE}")).scalar()
    return str(row) if row else None


def _flags(raw: Any) -> set[str]:
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return set()
    return {p.strip() for p in str(raw).split(",") if p.strip()}


def load_danji_frame(
    conn: Connection,
    req: RegionalRegressionRunRequest,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    as_of, _ = latest_mart_snapshot(conn)
    snap = _latest_snapshot_ym(conn)
    if as_of is None:
        raise RuntimeError("collective_building_stats 스냅샷이 없습니다")
    if not snap:
        raise RuntimeError("collective_building_attributes 스냅샷이 없습니다")

    asset_param = _regression_asset_param(req.asset_type)
    empty_cols = [
        "building_key",
        "display_name",
        "median",
        "n_tx",
        "building_year",
        "asset_type",
        "match_tier",
        "households",
        "max_floor",
        "parking_per_household",
        "approved_year",
        "structure_group",
        "builder_group",
        "attr_quality_flags",
        "assessed_land_price",
        "assessed_land_price_year",
        "assessed_land_price_pnu",
    ]
    if not asset_param:
        meta = {
            "as_of_month": as_of.isoformat(),
            "as_of_label": stats_as_of_label(as_of),
            "snapshot_ym": snap,
            "scope_label": _scope_label(req),
            "presale_only": True,
            "dropped_presale": True,
        }
        return pd.DataFrame(columns=empty_cols), meta

    region_sql, params = _mart_region_where(
        conn,
        asset_type=asset_param,
        addr1=req.addr1,
        addr2=req.addr2,
        addr3=None,
        addr3_list=req.addr3_list or None,
        addr4_list=req.addr4_list or None,
        region_codes=req.region_codes or None,
        region_code_level=req.region_code_level,
        region_addrs=req.region_addrs or None,
        emd_code_col=None,
    )
    params["as_of"] = as_of
    params["window_years"] = int(req.window_years)
    params["snap"] = snap
    land_price_select, land_price_join = _assessed_land_price_sql(conn)

    rows = conn.execute(
        text(
            f"""
            SELECT m.building_key, m.display_name, m.median, m.count AS n_tx,
                   m.building_year, m.addr3, m.addr4, m.asset_type,
                   a.match_tier, a.households, a.max_floor, a.parking_per_household,
                   a.approved_year, a.structure_group, a.builder_group,
                   a.attr_quality_flags,
                   {land_price_select}
            FROM collective_building_stats m
            LEFT JOIN {ATTRIBUTES_TABLE} a
              ON a.building_key = m.building_key
             AND a.asset_type = m.asset_type
             AND a.snapshot_ym = :snap
            {land_price_join}
            WHERE m.as_of_month = :as_of
              AND m.window_years = :window_years
              AND {region_sql}
            """
        ),
        params,
    ).mappings().all()

    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=empty_cols)
    else:
        as_of_year = int(as_of.year)
        appr = pd.to_numeric(df["approved_year"], errors="coerce")
        by = pd.to_numeric(df["building_year"], errors="coerce")
        vintage = appr.fillna(by)
        df["building_age"] = as_of_year - vintage
        df.loc[(df["building_age"] < 0) | (df["building_age"] > 80), "building_age"] = np.nan
        for col in (
            "households",
            "max_floor",
            "parking_per_household",
            "assessed_land_price",
            "median",
        ):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["n_tx"] = pd.to_numeric(df["n_tx"], errors="coerce").fillna(0)
        df["asset_type"] = df["asset_type"].fillna("apartment").astype(str)
        df["households_raw"] = df["households"]
        df["max_floor_raw"] = df["max_floor"]
        df["parking_raw"] = df["parking_per_household"]
        flags = df["attr_quality_flags"].map(_flags)
        df["quality_flags"] = flags
        df.loc[flags.map(lambda s: "hh_zero" in s or "scale_inconsistent" in s), "households"] = np.nan
        df.loc[flags.map(lambda s: "floor_implausible" in s or "scale_inconsistent" in s), "max_floor"] = np.nan
        df.loc[flags.map(lambda s: "parking_implausible" in s), "parking_per_household"] = np.nan
        df.loc[df["households"] <= 0, "households"] = np.nan
        df.loc[df["max_floor"] <= 0, "max_floor"] = np.nan
        df.loc[df["parking_per_household"] < 0, "parking_per_household"] = np.nan

    selected = _selected_regression_types(req.asset_type)
    dropped_presale = includes_presale(req.asset_type or "apartment")

    meta = {
        "as_of_month": as_of.isoformat(),
        "as_of_label": stats_as_of_label(as_of),
        "snapshot_ym": snap,
        "scope_label": _scope_label(req),
        "presale_only": False,
        "dropped_presale": dropped_presale,
        "regression_types": selected,
    }
    return df, meta


def _assessed_land_price_sql(conn: Connection) -> tuple[str, str]:
    """공시지가 mart가 아직 없는 환경에서도 기존 회귀를 계속 동작시킨다."""
    exists = conn.execute(
        text("SELECT to_regclass(:table_name)"),
        {"table_name": "public.collective_building_assessed_land_price"},
    ).scalar()
    if not exists:
        return (
            "NULL::numeric AS assessed_land_price, "
            "NULL::smallint AS assessed_land_price_year, "
            "NULL::char(19) AS assessed_land_price_pnu",
            "",
        )
    return (
        "lp.assessed_land_price, lp.assessed_land_price_year, "
        "lp.representative_pnu AS assessed_land_price_pnu",
        """
            LEFT JOIN collective_building_assessed_land_price lp
              ON lp.building_key = m.building_key
             AND lp.asset_type = m.asset_type
        """,
    )


def _scope_label(req: RegionalRegressionRunRequest) -> str:
    bits = [req.addr1, req.addr2]
    if req.addr3_list:
        bits.append("·".join(req.addr3_list[:4]) + ("…" if len(req.addr3_list) > 4 else ""))
    if req.addr4_list:
        bits.append(f"읍면동 {len(req.addr4_list)}곳")
    if req.region_codes:
        bits.append(f"인접 {len(req.region_codes)}곳")
    types = _selected_regression_types(req.asset_type)
    if types:
        bits.append("·".join(ASSET_TYPE_LABELS.get(t, t) for t in types))
    bits.append(f"{req.window_years}년 창")
    return " · ".join(b for b in bits if b)


def _collapse_dummy(series: pd.Series, *, min_n: int = DUMMY_MIN) -> pd.Series:
    s = series.fillna("").astype(str).str.strip().replace({"": "(미상)", "nan": "(미상)"})
    counts = s.value_counts()
    rare = set(counts[counts < min_n].index) - {"(미상)"}
    if rare:
        s = s.where(~s.isin(rare), "기타")
    return s


def _pick_dummy_ref(raw: pd.Series) -> str:
    """더미 기준 = 표본 최다 범주. 동점이면 이름순."""
    counts = raw.value_counts()
    if counts.empty:
        return "(미상)"
    top = int(counts.max())
    tied = sorted(str(v) for v in counts[counts == top].index)
    return tied[0] if tied else "(미상)"


MATCH_REASON_ORDER = ("no_attr", "tier_Z", "tier_E", "tier_P", "tier_T", "tier_D", "tier_F")
VAR_REASON_ORDER = (
    "no_price",
    "households_flag",
    "households_missing",
    "max_floor_flag",
    "max_floor_missing",
    "building_age_missing",
    "parking_flag",
    "parking_missing",
    "assessed_land_price_missing",
    "structure_missing",
    "builder_missing",
    "other",
)


def _tier_drop_reason(tier: Any) -> tuple[str, str]:
    t = "" if tier is None or (isinstance(tier, float) and np.isnan(tier)) else str(tier).strip()
    if not t:
        return "no_attr", "단지정보 없음 (K-apt 미연결)"
    meta = TIER_META.get(t, {})
    label = meta.get("label") or f"매칭 {t}"
    return f"tier_{t}", f"매칭 {t} · {label}"


def _var_drop_reason(row: pd.Series, v: RegionalRegressionVariables) -> tuple[str, str]:
    """사용 가능 매칭인데 적합에서 빠진 한 행의 첫 사유. 한 행은 한 칸만 탄다."""
    flags: set[str] = row["quality_flags"] if isinstance(row.get("quality_flags"), set) else _flags(row.get("attr_quality_flags"))
    median = row.get("median")
    if pd.isna(median):
        return "no_price", "단가 없음"
    try:
        if float(median) <= 0:
            return "no_price", "단가 없음"
    except (TypeError, ValueError):
        return "no_price", "단가 없음"

    if v.households:
        if "hh_zero" in flags:
            return "households_flag", "세대수 0 (원본 이상값)"
        if "scale_inconsistent" in flags:
            return "households_flag", "세대수·동수·층수 불일치 (원본 이상값)"
        if pd.isna(row.get("households")):
            return "households_missing", "세대수 결측"

    if v.max_floor:
        if "floor_implausible" in flags:
            return "max_floor_flag", "최고층 이상값"
        if "scale_inconsistent" in flags:
            return "max_floor_flag", "세대수·동수·층수 불일치 (원본 이상값)"
        if pd.isna(row.get("max_floor")):
            return "max_floor_missing", "최고층 결측"

    if v.building_age and pd.isna(row.get("building_age")):
        return "building_age_missing", "연식 결측"

    if v.parking:
        if "parking_implausible" in flags:
            return "parking_flag", "세대당 주차 이상값"
        if pd.isna(row.get("parking_per_household")):
            return "parking_missing", "세대당 주차 결측"

    if v.assessed_land_price and pd.isna(row.get("assessed_land_price")):
        return "assessed_land_price_missing", "개별공시지가 미매칭"

    return "other", "기타"


def _count_reasons(
    pairs: list[tuple[str, str]],
    *,
    preferred: tuple[str, ...] = (),
) -> list[FunnelReason]:
    labels: dict[str, str] = {}
    counts: dict[str, int] = {}
    seen: list[str] = []
    for code, label in pairs:
        if code not in counts:
            seen.append(code)
            labels[code] = label
            counts[code] = 0
        counts[code] += 1
    ordered = [c for c in preferred if c in counts] + [c for c in seen if c not in preferred]
    return [FunnelReason(code=c, label=labels[c], n=counts[c]) for c in ordered]


def build_sample_funnel(
    df: pd.DataFrame,
    v: RegionalRegressionVariables,
    *,
    train_idx: pd.Index,
    hold_idx: pd.Index,
) -> SampleBreakdown:
    """원본 → 매칭 → 변수 결측 → 분석 표본 → 학습/hold. hold 는 탈락이 아니다."""
    n_pool = int(len(df))
    if n_pool == 0 or "match_tier" not in df.columns:
        empty = SampleBreakdown(
            n_pool=n_pool,
            n_with_attributes=0,
            n_usable_tier=0,
            n_analysis=0,
            n_fit=int(len(train_idx)),
            n_hold=int(len(hold_idx)),
            n_missing_attr=0,
            n_weak_tier=0,
            n_no_price=0,
            funnel=[FunnelStep(code="pool", label="원본 단지", n=n_pool, kind="remain")],
        )
        return empty

    has_attr = df["match_tier"].notna()
    usable = _usable_tier_mask(df)
    elig = _eligible_mask(df, v)
    n_usable = int(usable.sum())
    n_analysis = int(elig.sum())
    n_fit = int(len(train_idx))
    n_hold = int(len(hold_idx))

    n_tx = pd.to_numeric(df["n_tx"], errors="coerce").fillna(0) if "n_tx" in df.columns else pd.Series(0, index=df.index)
    thin = usable & (n_tx < MIN_TX)
    n_thin = int(thin.sum())
    after_thin = usable & ~thin
    var_drop_mask = after_thin & ~elig
    n_var_drop = int(var_drop_mask.sum())

    match_pairs = [_tier_drop_reason(t) for t in df.loc[~usable, "match_tier"]]
    var_pairs = [_var_drop_reason(row, v) for _, row in df.loc[var_drop_mask].iterrows()]
    thin_pairs: list[tuple[str, str]] = []
    if n_thin:
        if "asset_type" in df.columns:
            for at, cnt in df.loc[thin, "asset_type"].fillna("apartment").astype(str).value_counts().items():
                label = ASSET_TYPE_LABELS.get(at, at)
                thin_pairs.extend([(f"thin_{at}", label)] * int(cnt))
        else:
            thin_pairs.append(("thin_tx", f"거래 {MIN_TX}건 미만"))

    funnel = [
        FunnelStep(code="pool", label="원본 단지", n=n_pool, kind="remain"),
        FunnelStep(code="usable", label=_usable_funnel_label(df), n=n_usable, kind="remain"),
        FunnelStep(
            code="match_drop",
            label="매칭 불확실·불가",
            n=n_pool - n_usable,
            kind="drop",
            note=_match_drop_note(df),
            reasons=_count_reasons(match_pairs, preferred=MATCH_REASON_ORDER),
        ),
        FunnelStep(
            code="thin_tx",
            label=f"최소 거래수 미달(<{MIN_TX})",
            n=n_thin,
            kind="drop",
            note="창 중앙값을 단지 시세로 보기 어렵습니다. 유형과 관계없이 제외합니다.",
            reasons=_count_reasons(thin_pairs),
        ),
        FunnelStep(
            code="var_drop",
            label="선택 변수 결측",
            n=n_var_drop,
            kind="drop",
            note="세대수·층·연식·주차·공시지가처럼 켠 연속변수에 값이 없어 빠진 단지입니다. 구조·시공사 결측은 미상 더미로 남고 여기서는 빠지지 않습니다.",
            reasons=_count_reasons(var_pairs, preferred=VAR_REASON_ORDER),
        ),
        FunnelStep(
            code="analysis",
            label="최종 분석 표본",
            n=n_analysis,
            kind="remain",
            note="학습과 hold 를 나눈 전체입니다. hold 는 탈락이 아닙니다.",
        ),
        FunnelStep(code="train", label="학습", n=n_fit, kind="split"),
        FunnelStep(code="hold", label="Holdout", n=n_hold, kind="split"),
    ]

    return SampleBreakdown(
        n_pool=n_pool,
        n_with_attributes=int(has_attr.sum()),
        n_usable_tier=n_usable,
        n_analysis=n_analysis,
        n_fit=n_fit,
        n_hold=n_hold,
        n_missing_attr=int((~has_attr).sum()),
        n_weak_tier=int((has_attr & ~usable).sum()),
        n_no_price=int((pd.to_numeric(df["median"], errors="coerce").fillna(0) <= 0).sum()),
        funnel=funnel,
    )


def _usable_funnel_label(df: pd.DataFrame) -> str:
    del df
    return "속성 연결됨"


def _match_drop_note(df: pd.DataFrame) -> str:
    del df
    return (
        "세대수·층·구조 등 속성이 연결된 단지(K-apt A·B·C·D·F, 표제부 T, PNU 유일 P)를 넣습니다. "
        "E(이름 부분일치 오탐 위험)·Z·단지정보 없음만 제외합니다."
    )


def _needed_columns(v: RegionalRegressionVariables) -> list[str]:
    cols: list[str] = ["median"]
    if v.households:
        cols.append("households")
    if v.max_floor:
        cols.append("max_floor")
    if v.building_age:
        cols.append("building_age")
    if v.parking:
        cols.append("parking_per_household")
    if v.assessed_land_price:
        cols.append("assessed_land_price")
    return cols


def _design(
    work: pd.DataFrame,
    v: RegionalRegressionVariables,
    *,
    struct_levels: list[str] | None = None,
    builder_levels: list[str] | None = None,
    struct_ref: str | None = None,
    builder_ref: str | None = None,
    type_levels: list[str] | None = None,
    type_ref: str | None = None,
) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    """X (no const), name→label, warnings."""
    x = pd.DataFrame(index=work.index)
    labels: dict[str, str] = {}
    warnings: list[str] = []

    if v.households:
        x["households"] = work["households"].astype(float)
        labels["households"] = LABELS["households"]
    if v.max_floor:
        x["max_floor"] = work["max_floor"].astype(float)
        labels["max_floor"] = LABELS["max_floor"]
    if v.building_age:
        x["building_age"] = work["building_age"].astype(float)
        labels["building_age"] = LABELS["building_age"]
    if v.parking:
        x["parking_per_household"] = work["parking_per_household"].astype(float)
        labels["parking_per_household"] = LABELS["parking_per_household"]
    if v.assessed_land_price:
        x["assessed_land_price"] = work["assessed_land_price"].astype(float)
        labels["assessed_land_price"] = LABELS["assessed_land_price"]

    if v.asset_type_dummy and "asset_type" in work.columns:
        raw = work["asset_type"].fillna("").astype(str).str.strip()
        if type_levels is not None:
            levels = [lv for lv in type_levels if lv]
            raw = raw.where(raw.isin(levels), levels[0] if levels else raw)
        else:
            present = set(raw.unique())
            levels = [t for t in ASSET_TYPE_ORDER if t in present]
            levels.extend(sorted(t for t in present if t and t not in levels))
        if len(levels) >= 2:
            ref = type_ref if type_ref is not None else _asset_type_ref(levels)
            used = 0
            counts = raw.value_counts()
            for lv in levels:
                if lv == ref:
                    continue
                col = f"atype_{lv}"
                x[col] = (raw == lv).astype(float)
                labels[col] = f"유형 {ASSET_TYPE_LABELS.get(lv, lv)} (기준 대비)"
                used += 1
                n_lv = int(counts.get(lv, 0))
                if n_lv < DUMMY_MIN:
                    warnings.append(
                        f"{ASSET_TYPE_LABELS.get(lv, lv)} 표본이 {n_lv}곳뿐입니다. "
                        "유형 더미가 불안정할 수 있습니다."
                    )
            if used:
                labels["_atype_ref"] = ref
        # 한 유형만 남으면 더미를 조용히 생략 (아파트 기본값에서 경고가 나지 않게)

    if v.structure:
        if struct_levels is not None:
            raw = work["structure_group"].fillna("").astype(str).str.strip()
            raw = raw.where(raw.isin(struct_levels), "기타")
            levels = struct_levels
        else:
            raw = _collapse_dummy(work["structure_group"])
            levels = sorted(raw.unique())
        ref = struct_ref if struct_ref is not None else _pick_dummy_ref(raw)
        used = 0
        for lv in levels:
            if lv == ref:
                continue
            col = f"struct_{lv}"
            x[col] = (raw == lv).astype(float)
            labels[col] = f"구조 {lv} (기준 대비)"
            used += 1
        if used == 0:
            warnings.append("구조 범주가 한 종류뿐이라 더미를 넣지 않았습니다.")
        else:
            labels["_struct_ref"] = ref

    if v.builder:
        if builder_levels is not None:
            raw = work["builder_group"].fillna("").astype(str).str.strip()
            raw = raw.where(raw.isin(builder_levels), "기타")
            levels = builder_levels
        else:
            raw = _collapse_dummy(work["builder_group"])
            levels = sorted(raw.unique())
        ref = builder_ref if builder_ref is not None else _pick_dummy_ref(raw)
        used = 0
        for lv in levels:
            if lv == ref:
                continue
            col = f"builder_{lv}"
            x[col] = (raw == lv).astype(float)
            labels[col] = f"시공사 {lv} (기준 대비)"
            used += 1
        if used == 0:
            warnings.append("시공사군이 한 종류뿐이라 더미를 넣지 않았습니다.")
        else:
            labels["_builder_ref"] = ref

    return x, labels, warnings


def _asset_type_ref(levels: list[str]) -> str:
    for t in ASSET_TYPE_ORDER:
        if t in levels:
            return t
    return levels[0] if levels else "apartment"


def _reference_categories(labels: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    if labels.get("_struct_ref"):
        out["structure_group"] = labels["_struct_ref"]
    if labels.get("_builder_ref"):
        out["builder_group"] = labels["_builder_ref"]
    if labels.get("_atype_ref"):
        out["asset_type"] = labels["_atype_ref"]
    return out


def _fit_ols(
    work: pd.DataFrame,
    x: pd.DataFrame,
    *,
    model_type: ModelType,
    weight_mode: WeightMode = "equal",
    train_idx: pd.Index | None = None,
    hold_idx: pd.Index | None = None,
) -> dict[str, Any] | None:
    y_price_all = work["median"].astype(float)
    ok = y_price_all > 0
    work = work.loc[ok]
    x = x.loc[ok]
    if train_idx is None:
        train_idx = work.index
    else:
        train_idx = train_idx.intersection(work.index)
    train = work.loc[train_idx]
    x_train = x.loc[train_idx]
    y_price = train["median"].astype(float).to_numpy()
    if len(train) < MIN_FIT_N or x_train.shape[1] == 0:
        return None
    y_fit = np.log(y_price) if model_type == "log" else y_price
    x_const = sm.add_constant(x_train, has_constant="add")
    keep = [c for c in x_const.columns if c == "const" or float(x_const[c].std(ddof=0) or 0) > 0]
    x_const = x_const[keep]
    if x_const.shape[1] <= 1:
        return None
    w_train = _row_weights(train, weight_mode)
    try:
        if w_train is None:
            model = sm.OLS(y_fit, x_const, missing="drop").fit()
        else:
            model = sm.WLS(y_fit, x_const, weights=w_train, missing="drop").fit()
    except Exception:
        return None

    fitted_price = np.asarray(model.predict(x_const), dtype=float)
    smear = 1.0
    if model_type == "log":
        smear = _duan_smearing_w(model.resid, w_train)
        fitted_price = np.exp(fitted_price) * smear

    k = int(model.df_model)
    adj, mape, rmse = _orig_scale_metrics_w(y_price, fitted_price, k, w_train)
    r2 = float(model.rsquared) if np.isfinite(model.rsquared) else None

    hold_mape = None
    if hold_idx is not None:
        hold_idx = hold_idx.intersection(work.index)
        if len(hold_idx) >= 5:
            xh = sm.add_constant(x.reindex(hold_idx), has_constant="add").reindex(
                columns=x_const.columns, fill_value=0
            )
            ph = np.asarray(model.predict(xh), dtype=float)
            if model_type == "log":
                ph = np.exp(ph) * smear
            yh = work.loc[hold_idx, "median"].astype(float).to_numpy()
            w_hold = _row_weights(work.loc[hold_idx], weight_mode)
            _, hold_mape, _ = _orig_scale_metrics_w(yh, ph, k, w_hold)

    coefs: list[RegressionCoeff] = []
    for name in x_const.columns:
        coefs.append(
            RegressionCoeff(
                name="const" if name == "const" else name,
                label=LABELS.get(name, name),
                coef=float(model.params[name]),
                se=float(model.bse[name]) if name in model.bse else None,
                t=float(model.tvalues[name]) if name in model.tvalues else None,
                p=float(model.pvalues[name]) if name in model.pvalues else None,
            )
        )
    fp = None
    try:
        fp = float(model.f_pvalue) if model.f_pvalue is not None else None
    except Exception:
        fp = None
    n_eff = float(np.sum(w_train)) if w_train is not None else float(len(train))
    return {
        "model": model,
        "x_cols": list(x_const.columns),
        "smear": smear,
        "y_hat": fitted_price,
        "work_index": train.index,
        "adj_r_squared": adj,
        "r_squared": round(r2, 4) if r2 is not None else None,
        "mape": mape,
        "hold_mape": hold_mape,
        "rmse": rmse,
        "f_p_value": round(fp, 5) if fp is not None and np.isfinite(fp) else None,
        "coefficients": coefs,
        "n": int(len(train)),
        "n_effective": round(n_eff, 1),
        "weight_mode": weight_mode,
    }


def _eligible_mask(df: pd.DataFrame, v: RegionalRegressionVariables) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=bool, index=df.index)
    n_tx = pd.to_numeric(df["n_tx"], errors="coerce").fillna(0) if "n_tx" in df.columns else pd.Series(0, index=df.index)
    m = (
        df["median"].notna()
        & (df["median"] > 0)
        & _usable_tier_mask(df)
        & (n_tx >= MIN_TX)
    )
    for col in _needed_columns(v):
        if col == "median":
            continue
        m = m & df[col].notna()
    return m


def _split_hold(index: pd.Index, *, seed: int = 42) -> tuple[pd.Index, pd.Index]:
    n = len(index)
    if n < HOLD_MIN_N:
        return index, index[:0]
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)
    n_hold = max(int(round(n * HOLD_FRAC)), 8)
    hold = index[perm[:n_hold]]
    train = index[perm[n_hold:]]
    if len(train) < MIN_FIT_N:
        return index, index[:0]
    return train, hold


def run_regional_regression(
    conn: Connection,
    req: RegionalRegressionRunRequest,
) -> RegionalRegressionRunResponse:
    df, meta = load_danji_frame(conn, req)
    v = req.variables
    warnings: list[str] = []
    types = list(meta.get("regression_types") or _selected_regression_types(req.asset_type))
    unified = _is_unified_types(types)

    if meta.get("presale_only"):
        warnings.append("분양권만 선택되어 지역회귀를 돌릴 수 없습니다. 매매 유형을 함께 고르세요.")
    elif meta.get("dropped_presale"):
        warnings.append("분양권은 권리 가격이라 표본에서 뺐습니다.")

    if v.assessed_land_price:
        n_land_price = int(df["assessed_land_price"].notna().sum()) if not df.empty else 0
        if n_land_price == 0:
            warnings.append("이 지역에 연결된 개별공시지가가 없습니다.")
        elif n_land_price < len(df):
            warnings.append(
                f"개별공시지가가 연결된 단지는 {n_land_price}/{len(df)}곳입니다. "
                "미연결 단지는 깔때기에서 제외됩니다."
            )

    if v.structure:
        warnings.append(WEAK_NOTE["structure"])
    if v.builder:
        warnings.append(WEAK_NOTE["builder"])
        warnings.append("시공사 결측은 (미상) 더미로 넣고 단지를 빼지 않습니다.")
    if v.parking and not df.empty:
        n_park_na = int(df["parking_per_household"].isna().sum())
        if n_park_na:
            warnings.append(
                f"세대당 주차 값이 없는 단지가 {n_park_na}곳입니다. "
                "표제부(T)에는 주차 칸이 없어 주차를 켜면 이 단지들은 빠집니다."
            )
    elif v.parking and unified:
        warnings.append("세대당 주차는 연립·오피스텔에 거의 없습니다. 켜면 그 유형이 결측으로 빠질 수 있습니다.")

    if unified and not v.asset_type_dummy:
        warnings.append(
            "여러 유형을 한 식에 넣었지만 유형 더미가 꺼져 있습니다. "
            "아파트·오피스텔 가격 수준 차이를 통제하지 않습니다."
        )

    elig = _eligible_mask(df, v) if not df.empty else pd.Series(dtype=bool)
    work = df.loc[elig].copy() if not df.empty else df
    if unified and v.asset_type_dummy and not work.empty and "asset_type" in work.columns:
        if work["asset_type"].astype(str).nunique() < 2:
            warnings.append(
                "기본통계는 여러 유형이지만 적합 표본에 한 유형만 남아 유형 더미를 넣지 않았습니다."
            )
    train_idx, hold_idx = _split_hold(work.index)

    sample = build_sample_funnel(df, v, train_idx=train_idx, hold_idx=hold_idx)

    if len(train_idx) < MIN_FIT_N:
        warnings.append(
            f"적합 단지가 {len(train_idx)}곳뿐입니다. 최소 {MIN_FIT_N}곳이 필요합니다. "
            "지역을 넓히거나 변수를 줄여 보세요."
        )
        return RegionalRegressionRunResponse(
            n=len(train_idx),
            model_type=req.model_type,
            weight_mode=req.weight_mode,
            warnings=warnings,
            sample=sample,
            as_of_month=meta.get("as_of_month"),
            snapshot_ym=meta.get("snapshot_ym"),
            scope_label=meta.get("scope_label"),
        )

    x, labels, d_warn = _design(work, v)
    warnings.extend(d_warn)
    fitted = _fit_ols(
        work,
        x,
        model_type=req.model_type,
        weight_mode=req.weight_mode,
        train_idx=train_idx,
        hold_idx=hold_idx,
    )
    if fitted is None:
        warnings.append("회귀를 적합하지 못했습니다. 변수가 서로 겹치거나 표본이 부족합니다.")
        return RegionalRegressionRunResponse(
            n=len(train_idx),
            model_type=req.model_type,
            weight_mode=req.weight_mode,
            warnings=warnings,
            sample=sample,
            as_of_month=meta.get("as_of_month"),
            snapshot_ym=meta.get("snapshot_ym"),
            scope_label=meta.get("scope_label"),
        )

    train = work.loc[fitted["work_index"]]

    for c in fitted["coefficients"]:
        if c.name in labels:
            c.label = labels[c.name]
        elif c.name == "const":
            c.label = "절편"

    equation, enriched, price_adj = enrich_regression_response(
        fitted["coefficients"],
        model_type=req.model_type,
        price_adj_r_squared=fitted["adj_r_squared"],
    )
    coeffs = [RegressionCoeff(**row) if isinstance(row, dict) else row for row in enriched]

    # 표본 내 예측 (train)
    y_hat_map = dict(zip(fitted["work_index"], fitted["y_hat"]))
    rows: list[FittedBuildingRow] = []
    for i, r in train.iterrows():
        yh = y_hat_map.get(i)
        if yh is None:
            continue
        y = float(r["median"])
        ape = abs(y - float(yh)) / y * 100 if y else None
        rows.append(
            FittedBuildingRow(
                building_key=str(r["building_key"]),
                display_name=str(r["display_name"] or ""),
                y=round(y, 1),
                y_hat=round(float(yh), 1),
                ape=round(ape, 1) if ape is not None else None,
                asset_type=str(r["asset_type"]) if "asset_type" in r and pd.notna(r["asset_type"]) else None,
                assessed_land_price=(
                    round(float(r["assessed_land_price"]), 1)
                    if "assessed_land_price" in r and pd.notna(r["assessed_land_price"])
                    else None
                ),
            )
        )
    rows.sort(key=lambda x: x.display_name)
    rows = rows[:FITTED_CAP]

    blocks = _block_contrib(
        work, train_idx, hold_idx, v, req.model_type, req.weight_mode, core_hold=fitted.get("hold_mape")
    )

    struct_opts: list[str] = []
    builder_opts: list[str] = []
    type_opts: list[str] = []
    if v.structure:
        struct_opts = sorted(_collapse_dummy(train["structure_group"]).unique().tolist())
    if v.builder:
        builder_opts = sorted(_collapse_dummy(train["builder_group"]).unique().tolist())
    if v.asset_type_dummy and "asset_type" in train.columns:
        present = set(train["asset_type"].astype(str))
        type_opts = [t for t in ASSET_TYPE_ORDER if t in present]
        type_opts.extend(sorted(t for t in present if t and t not in type_opts))

    if sample.n_missing_attr:
        warnings.append(
            f"단지 정보가 없는 행 {sample.n_missing_attr}곳은 식에서 빠집니다 "
            f"(풀 {sample.n_pool}곳 중 속성 {sample.n_with_attributes}곳)."
        )
    return RegionalRegressionRunResponse(
        n=fitted["n"],
        model_type=req.model_type,
        weight_mode=req.weight_mode,
        n_effective=fitted.get("n_effective"),
        r_squared=fitted["r_squared"],
        adj_r_squared=price_adj,
        mape=fitted["mape"],
        hold_mape=fitted["hold_mape"],
        rmse=fitted["rmse"],
        f_p_value=fitted["f_p_value"],
        equation=equation,
        coefficients=coeffs,
        warnings=warnings,
        sample=sample,
        blocks=blocks,
        fitted=rows,
        predict_options={
            "structure_group": struct_opts,
            "builder_group": builder_opts,
            "asset_type": type_opts,
        },
        reference_categories=_reference_categories(labels),
        as_of_month=meta.get("as_of_month"),
        snapshot_ym=meta.get("snapshot_ym"),
        scope_label=meta.get("scope_label"),
    )


def _block_contrib(
    work: pd.DataFrame,
    train_idx: pd.Index,
    hold_idx: pd.Index,
    v: RegionalRegressionVariables,
    model_type: ModelType,
    weight_mode: WeightMode,
    *,
    core_hold: float | None,
) -> list[BlockContribution]:
    out: list[BlockContribution] = []
    core = RegionalRegressionVariables(
        households=v.households,
        max_floor=v.max_floor,
        building_age=v.building_age,
        parking=v.parking,
        structure=False,
        builder=False,
        asset_type_dummy=v.asset_type_dummy,
        assessed_land_price=False,
    )
    x_core, _, _ = _design(work, core)
    fit_core = _fit_ols(
        work,
        x_core,
        model_type=model_type,
        weight_mode=weight_mode,
        train_idx=train_idx,
        hold_idx=hold_idx,
    )
    if fit_core:
        out.append(
            BlockContribution(
                block="core",
                label="규모·연식·주차",
                weak=False,
                hold_mape=fit_core.get("hold_mape"),
                in_sample_mape=fit_core.get("mape"),
            )
        )
        core_hold = fit_core.get("hold_mape")

    for key, label, flag, weak, base_note in (
        (
            "assessed_land_price",
            "개별공시지가",
            v.assessed_land_price,
            False,
            "기존 핵심식에 최신 대표 필지 개별공시지가를 원값으로 추가한 비교입니다.",
        ),
        ("structure", "구조", v.structure, True, WEAK_NOTE["structure"]),
        ("builder", "시공사", v.builder, True, WEAK_NOTE["builder"]),
    ):
        if not flag:
            continue
        extra = core.model_copy(update={key: True})
        x, _, _ = _design(work, extra)
        fit = _fit_ols(
            work, x, model_type=model_type, weight_mode=weight_mode, train_idx=train_idx, hold_idx=hold_idx
        )
        if not fit:
            continue
        hm = fit.get("hold_mape")
        delta = None
        if hm is not None and core_hold is not None:
            delta = round(float(hm) - float(core_hold), 2)
        note = base_note
        if delta is not None and delta > 0:
            note = f"{note} 이 지역 hold MAPE가 핵심 블록 대비 {delta:.1f}%p 높아졌습니다."
        elif delta is not None and delta < 0:
            note = f"{note} 이 지역에서는 hold MAPE가 {abs(delta):.1f}%p 낮아졌습니다."
        out.append(
            BlockContribution(
                block=key,
                label=label,
                weak=weak,
                hold_mape=hm,
                in_sample_mape=fit.get("mape"),
                delta_mape_vs_core=delta,
                note=note,
            )
        )
    return out


def predict_regional(
    conn: Connection,
    req: RegionalRegressionRunRequest,
    inputs: RegionalRegressionPredictInputs,
) -> dict[str, Any]:
    """같은 스코프·변수로 다시 적합하고 입력 한 건을 예측한다. 표본이 작아 매번 재적합해도 부담이 없다."""
    result = run_regional_regression(conn, req)
    if result.n < MIN_FIT_N or not result.coefficients:
        raise ValueError(result.warnings[0] if result.warnings else "적합된 식이 없습니다")

    df, _ = load_danji_frame(conn, req)
    v = req.variables
    work = df.loc[_eligible_mask(df, v)].copy()
    train_idx, _hold = _split_hold(work.index)
    x, labels, _ = _design(work, v)
    fitted = _fit_ols(
        work, x, model_type=req.model_type, weight_mode=req.weight_mode, train_idx=train_idx, hold_idx=None
    )
    if not fitted:
        raise ValueError("예측용 식을 적합하지 못했습니다")

    struct_ref = labels.get("_struct_ref")
    builder_ref = labels.get("_builder_ref")
    atype_ref = labels.get("_atype_ref")
    row = {
        "households": inputs.households,
        "max_floor": inputs.max_floor,
        "building_age": inputs.building_age,
        "parking_per_household": inputs.parking_per_household,
        "assessed_land_price": inputs.assessed_land_price,
        "structure_group": inputs.structure_group or struct_ref or "",
        "builder_group": inputs.builder_group or builder_ref or "",
        "asset_type": inputs.asset_type or atype_ref or "apartment",
        "median": 1.0,  # unused
        "n_tx": MIN_TX,
    }
    one = pd.DataFrame([row])
    struct_levels = sorted(_collapse_dummy(work["structure_group"]).unique().tolist()) if v.structure else []
    builder_levels = sorted(_collapse_dummy(work["builder_group"]).unique().tolist()) if v.builder else []
    type_levels: list[str] = []
    if v.asset_type_dummy and "asset_type" in work.columns:
        present = set(work["asset_type"].astype(str))
        type_levels = [t for t in ASSET_TYPE_ORDER if t in present]
        type_levels.extend(sorted(t for t in present if t and t not in type_levels))
    x1, _, _ = _design(
        one,
        v,
        struct_levels=struct_levels or None,
        builder_levels=builder_levels or None,
        struct_ref=struct_ref,
        builder_ref=builder_ref,
        type_levels=type_levels or None,
        type_ref=atype_ref,
    )
    x1c = sm.add_constant(x1, has_constant="add").reindex(columns=fitted["x_cols"], fill_value=0)
    raw = float(np.asarray(fitted["model"].predict(x1c), dtype=float)[0])
    y_hat = float(np.exp(raw) * fitted["smear"]) if req.model_type == "log" else raw

    contrib: list[dict[str, Any]] = []
    params = fitted["model"].params
    for name in fitted["x_cols"]:
        val = float(x1c.iloc[0][name]) if name in x1c.columns else (1.0 if name == "const" else 0.0)
        coef = float(params[name])
        contrib.append(
            {
                "name": name,
                "label": labels.get(name, LABELS.get(name, name)),
                "value": val,
                "coef": coef,
                "product": coef * val,
            }
        )
    warnings = list(result.warnings)
    return {
        "n": result.n,
        "model_type": req.model_type,
        "weight_mode": req.weight_mode,
        "y_hat": round(y_hat, 1),
        "unit": "만원/㎡",
        "warnings": warnings,
        "contributions": contrib,
    }
