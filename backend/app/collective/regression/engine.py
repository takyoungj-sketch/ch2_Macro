"""단일·코호트 OLS — 층·동 더미, 단지 FE, 예측."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm

from app.collective.regression.presentation import enrich_regression_response
from app.collective.schemas import (
    BuildingFeOption,
    CollectivePredictOptions,
    CollectiveRegressionPredictInputs,
    CollectiveRegressionRequest,
    CollectiveRegressionResponse,
    CollectiveRegressionSpec,
    CollectiveModelCandidate,
    ContinuousRange,
    DongOption,
    ModelComparison,
    ModelMetrics,
    RegressionCoeff,
)

MIN_BUILDING_FE_GROUP = 5
CV_MIN_N = 40  # 이 이상이면 5-fold 교차검증으로 MAPE/RMSE 산정

_ASSET_TYPE_LABELS = {
    "apartment": "아파트",
    "rowhouse": "연립·다세대",
    "officetel": "오피스텔",
    "presale": "분양권",
}
_ATTR_CONTINUOUS = ("households", "parking_per_household", "assessed_land_price")
_ATTR_FLAG_COLS: tuple[tuple[str, str, str], ...] = (
    ("households", "households", "세대수"),
    ("parking", "parking_per_household", "세대당 주차"),
    ("assessed_land_price", "assessed_land_price", "개별공시지가"),
    ("structure", "structure_group", "구조"),
    ("asset_type_dummy", "asset_type", "유형"),
)


def _duan_smearing(resid: pd.Series | np.ndarray) -> float:
    """로그모델 역변환 편의 보정계수 = mean(exp(residual))."""
    arr = np.asarray(resid, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return 1.0
    return float(np.mean(np.exp(arr)))


def _insample_price_pred(model, x_const: pd.DataFrame, model_type: str) -> np.ndarray:
    """적합 모델의 표본내 예측을 원척도(price)로 환산."""
    pred = np.asarray(model.predict(x_const), dtype=float)
    if model_type == "log":
        return np.exp(pred) * _duan_smearing(model.resid)
    return pred


def _orig_scale_metrics(
    y_price: np.ndarray, y_pred: np.ndarray, k_params: int
) -> tuple[float | None, float | None, float | None]:
    """원척도 조정 R²·MAPE(%)·RMSE(만원)."""
    y = np.asarray(y_price, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    mask = np.isfinite(y) & np.isfinite(p)
    y, p = y[mask], p[mask]
    n = y.size
    if n < 2:
        return None, None, None
    err = y - p
    ss_res = float(np.sum(err**2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else None
    adj = r2
    if r2 is not None and n - k_params - 1 > 0:
        adj = 1.0 - (1.0 - r2) * (n - 1) / (n - k_params - 1)
    nz = y != 0
    mape = float(np.mean(np.abs(err[nz]) / y[nz])) * 100 if nz.any() else None
    rmse = float(np.sqrt(np.mean(err**2)))
    return (
        round(adj, 4) if adj is not None else None,
        round(mape, 2) if mape is not None else None,
        round(rmse, 1) if rmse is not None else None,
    )


def _cv_price_metrics(
    y_price: np.ndarray, x_const: np.ndarray, model_type: str, *, k: int = 5, seed: int = 42
) -> tuple[float | None, float | None]:
    """5-fold 교차검증 MAPE(%)·RMSE(만원), 원척도."""
    y = np.asarray(y_price, dtype=float)
    X = np.asarray(x_const, dtype=float)
    n = y.size
    if n < CV_MIN_N:
        return None, None
    idx = np.arange(n)
    rng = np.random.default_rng(seed)
    rng.shuffle(idx)
    folds = np.array_split(idx, k)
    preds = np.full(n, np.nan)
    y_fit = np.log(y) if model_type == "log" else y
    for fold in folds:
        test = fold
        train = np.setdiff1d(idx, fold, assume_unique=False)
        if train.size <= X.shape[1] + 1:
            continue
        try:
            m = sm.OLS(y_fit[train], X[train]).fit()
            p = np.asarray(m.predict(X[test]), dtype=float)
            if model_type == "log":
                p = np.exp(p) * _duan_smearing(m.resid)
            preds[test] = p
        except Exception:
            continue
    mask = np.isfinite(preds) & np.isfinite(y)
    if mask.sum() < 2:
        return None, None
    err = y[mask] - preds[mask]
    nz = y[mask] != 0
    mape = float(np.mean(np.abs(err[nz]) / y[mask][nz])) * 100 if nz.any() else None
    rmse = float(np.sqrt(np.mean(err**2)))
    return (
        round(mape, 2) if mape is not None else None,
        round(rmse, 1) if rmse is not None else None,
    )


def _confidence_rating(mape: float | None, n: int) -> tuple[int, str]:
    """권장 모델 MAPE·표본수 기반 신뢰등급(별 1~5)."""
    if mape is None:
        return 0, "평가 불가"
    if mape <= 5 and n >= 100:
        return 5, "매우 높음"
    if mape <= 8 and n >= 50:
        return 4, "높음"
    if mape <= 12:
        return 3, "보통"
    if mape <= 20:
        return 2, "낮음"
    return 1, "매우 낮음"


def fit_model_price_metrics(
    y: pd.Series,
    x_const: pd.DataFrame,
    model,
    model_type: str,
) -> dict[str, float | str | None]:
    """선택 모델 1회 적합 기준 원척도 MAPE·adj R² (이중 OLS 비교 없음)."""
    k_params = max(x_const.shape[1] - 1, 0)
    pred = _insample_price_pred(model, x_const, model_type)
    adj, mape, rmse = _orig_scale_metrics(y.to_numpy(), pred, k_params)
    cv_mape, cv_rmse = _cv_price_metrics(y.to_numpy(), x_const.to_numpy(), model_type)
    basis: str = "cv" if cv_mape is not None else "insample"
    return {
        "price_adj_r_squared": adj,
        "mape": cv_mape if cv_mape is not None else mape,
        "rmse": cv_rmse if cv_rmse is not None else rmse,
        "metric_basis": basis,
    }


def count_significant_coefficients(coefs: list[RegressionCoeff], *, p_threshold: float = 0.1) -> int:
    return sum(
        1
        for c in coefs
        if c.name != "const" and c.p is not None and c.p < p_threshold
    )


def _build_model_comparison(
    y_price: pd.Series, x_const: pd.DataFrame
) -> ModelComparison | None:
    """로그·선형 모델을 모두 적합해 원척도 지표로 비교·권장."""
    y = y_price.astype(float)
    if y.shape[0] < 5 or x_const.empty:
        return None
    k_params = max(x_const.shape[1] - 1, 0)  # const 제외
    n = int(y.shape[0])
    metrics: dict[str, ModelMetrics] = {}
    cv_mape: dict[str, float | None] = {}

    for mt in ("linear", "log"):
        if mt == "log" and (y <= 0).any():
            continue
        try:
            y_fit = np.log(y) if mt == "log" else y
            model = sm.OLS(y_fit, x_const, missing="drop").fit()
        except Exception:
            continue
        pred = _insample_price_pred(model, x_const, mt)
        adj, mape, rmse = _orig_scale_metrics(y.to_numpy(), pred, k_params)
        cmape, crmse = _cv_price_metrics(y.to_numpy(), x_const.to_numpy(), mt)
        cv_mape[mt] = cmape
        metrics[mt] = ModelMetrics(
            model_type=mt,
            adj_r_squared=adj,
            mape=mape,
            rmse=rmse,
            cv_mape=cmape,
            cv_folds=5 if cmape is not None else 0,
            cv_method="kfold_random" if cmape is not None else None,
        )

    if not metrics:
        return None
    basis = "cv" if any(v is not None for v in cv_mape.values()) else "insample"

    def _mape_of(mt: str) -> float:
        m = metrics.get(mt)
        if not m:
            return float("inf")
        return (
            m.cv_mape
            if m.cv_mape is not None
            else m.mape
            if m.mape is not None
            else float("inf")
        )

    if "log" in metrics and "linear" in metrics:
        recommended = "log" if _mape_of("log") <= _mape_of("linear") else "linear"
    else:
        recommended = next(iter(metrics))
    stars, label = _confidence_rating(_mape_of(recommended), n)
    return ModelComparison(
        log=metrics.get("log"),
        linear=metrics.get("linear"),
        recommended=recommended,
        metric_basis=basis,
        confidence_stars=stars,
        confidence_label=label,
    )

# 상대 층(단지 max 층 대비)
_REL_FLOOR_LABELS: dict[str, str] = {
    "floor_rel_1": "1층",
    "floor_rel_top": "최상층",
    "floor_rel_low": "저층부",
    "floor_rel_mid": "중층부",
    "floor_rel_high": "고층부",
}


def relative_floor_group(floor: float, max_floor: float) -> str:
    if pd.isna(floor):
        return "floor_rel_mid"
    f = float(floor)
    mx = float(max_floor) if pd.notna(max_floor) and float(max_floor) > 0 else f
    if f == 1:
        return "floor_rel_1"
    if f == mx:
        return "floor_rel_top"
    ratio = f / mx if mx > 0 else 0.5
    if f > 1 and ratio <= 0.3:
        return "floor_rel_low"
    if 0.3 < ratio <= 0.7:
        return "floor_rel_mid"
    if ratio > 0.7 and f < mx:
        return "floor_rel_high"
    return "floor_rel_mid"


def _floor_group_label(floor: float) -> str:
    if floor <= 5:
        return "floor_grp_1-5"
    if floor <= 15:
        return "floor_grp_6-15"
    return "floor_grp_16+"


def _sanitize_key(key: str, prefix: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", str(key).strip())[:40]
    return f"{prefix}_{s}" if s else f"{prefix}_unknown"


def _clean_dong_values(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip()


def _dong_cats(series: pd.Series) -> list[str]:
    return sorted(c for c in series.dropna().unique() if c and c not in ("nan", "None"))


def _nested_dong_col(building_key: str, dong: str) -> str:
    token = hashlib.sha1(f"{building_key}|{dong}".encode("utf-8")).hexdigest()[:12]
    return f"dong_{token}"


def _add_pooled_dong_columns(
    work: pd.DataFrame,
    series: pd.Series,
    meta: RegressionDesignMeta,
    labels: dict[str, str],
) -> pd.DataFrame:
    cats = _dong_cats(series)
    if len(cats) < 2:
        return pd.DataFrame(index=work.index)
    meta.dong_categories = cats
    meta.dong_reference = cats[0]
    meta.dong_options = [
        DongOption(dong=c, label=c, is_reference=(c == cats[0])) for c in cats
    ]
    dummies = pd.get_dummies(series, prefix="dong", drop_first=True)
    if dummies.empty:
        return pd.DataFrame(index=work.index)
    for c in dummies.columns:
        labels[c] = f"동 {c.replace('dong_', '')}"
    return dummies


def _add_nested_dong_columns(
    work: pd.DataFrame,
    meta: RegressionDesignMeta,
    labels: dict[str, str],
    warnings: list[str],
) -> pd.DataFrame:
    """단지마다 동을 따로 두고, 단지별 기준동 1개는 단지 FE에 흡수한다."""
    keys = work["building_key"].astype(str)
    dongs = _clean_dong_values(work["dong"])
    parts: list[pd.DataFrame] = []
    options: list[DongOption] = []
    for bk in sorted(keys.unique()):
        mask = keys == bk
        series = dongs[mask]
        cats = _dong_cats(series)
        if not cats:
            continue
        counts = series[series.isin(cats)].value_counts()
        ref = str(counts.idxmax())
        meta.dong_reference_by_building[bk] = ref
        bname = meta.building_labels.get(bk, bk[:12])
        if len(cats) < 2:
            warnings.append(f"동 더미 없음 — {bname} 동 1개 (단지 FE에 흡수)")
        for dong in sorted(cats):
            is_ref = dong == ref
            options.append(
                DongOption(
                    dong=dong,
                    label=f"{bname} {dong}",
                    building_key=bk,
                    is_reference=is_ref,
                )
            )
            if is_ref:
                continue
            col = _nested_dong_col(bk, dong)
            work[col] = ((keys == bk) & (dongs == dong)).astype(float)
            parts.append(work[[col]])
            labels[col] = f"동 {bname} {dong}"
            meta.dong_fe_map[(bk, dong)] = col
    meta.dong_options = options
    meta.dong_categories = [o.label for o in options]
    ref_labels = [o.label for o in options if o.is_reference]
    meta.dong_reference = ref_labels[0] if len(ref_labels) == 1 else None
    if parts:
        warnings.append("동 더미는 단지별로 구분 (같은 동 번호라도 단지가 다르면 별개)")
        return pd.concat(parts, axis=1)
    return pd.DataFrame(index=work.index)


@dataclass
class RegressionDesignMeta:
    column_labels: dict[str, str] = field(default_factory=dict)
    floor_mode: str = "relative"
    max_floor: float | None = None
    dong_reference: str | None = None
    dong_categories: list[str] = field(default_factory=list)
    dong_options: list[DongOption] = field(default_factory=list)
    dong_fe_map: dict[tuple[str, str], str] = field(default_factory=dict)
    dong_reference_by_building: dict[str, str] = field(default_factory=dict)
    housing_subtype_reference: str | None = None
    housing_subtype_categories: list[str] = field(default_factory=list)
    building_reference_key: str | None = None
    building_fe_map: dict[str, str] = field(default_factory=dict)  # building_key -> col
    building_labels: dict[str, str] = field(default_factory=dict)
    building_counts: dict[str, int] = field(default_factory=dict)
    continuous_ranges: dict[str, tuple[float | None, float | None]] = field(default_factory=dict)
    floor_dummy_cols: list[str] = field(default_factory=list)
    structure_reference: str | None = None
    structure_dummy_cols: list[str] = field(default_factory=list)
    asset_type_reference: str | None = None
    asset_type_dummy_cols: list[str] = field(default_factory=list)
    used_building_attrs: bool = False


def _add_floor_columns(
    work: pd.DataFrame,
    mode: str,
    *,
    max_floor: float | None = None,
) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    """Returns dummies, labels, dummy column names (excl. reference)."""
    labels: dict[str, str] = {}
    if not work["floor"].notna().any():
        return pd.DataFrame(index=work.index), labels, []

    if mode == "linear":
        fl = work["floor"].astype(float).fillna(0)
        out = fl.to_frame("floor")
        labels["floor"] = "층(선형)"
        return out, labels, ["floor"]

    fl = work["floor"].astype(float)

    if mode == "relative":
        mx = float(max_floor if max_floor is not None else fl.max())
        grp = fl.apply(lambda x: relative_floor_group(x, mx) if pd.notna(x) else "floor_rel_mid")
        dummies = pd.get_dummies(grp, prefix="", prefix_sep="", drop_first=True)
        dummy_cols = list(dummies.columns)
        for c in dummies.columns:
            base = _REL_FLOOR_LABELS.get(c, c)
            labels[c] = f"{base} (기준 대비)"
        return dummies, labels, dummy_cols

    if mode == "grouped":
        grp = fl.apply(lambda x: _floor_group_label(x) if pd.notna(x) else "floor_grp_unknown")
        dummies = pd.get_dummies(grp, prefix="", prefix_sep="", drop_first=True)
    else:
        floor_str = fl.apply(
            lambda x: (
                str(int(x))
                if pd.notna(x) and float(x) == int(float(x))
                else (f"{float(x):g}" if pd.notna(x) else None)
            )
        )
        dummies = pd.get_dummies(floor_str, prefix="floor", drop_first=True)

    dummy_cols = list(dummies.columns)
    if dummies.empty:
        return pd.DataFrame(index=work.index), labels, []

    for c in dummies.columns:
        if c.startswith("floor_grp_"):
            labels[c] = c.replace("floor_grp_", "층 ") + " (기준 대비)"
        elif c.startswith("floor_rel_"):
            labels[c] = _REL_FLOOR_LABELS.get(c, c) + " (기준 대비)"
        else:
            labels[c] = f"층 {c.replace('floor_', '')} (기준 대비)"
    return dummies, labels, dummy_cols


def _floor_row_for_predict(
    floor: float | None,
    mode: str,
    max_floor: float,
    dummy_cols: list[str],
) -> dict[str, float]:
    out = {c: 0.0 for c in dummy_cols}
    if floor is None or pd.isna(floor):
        return out
    f = float(floor)
    if mode == "linear":
        if "floor" in out:
            out["floor"] = f
        return out
    if mode == "relative":
        code = relative_floor_group(f, max_floor)
        if code in out:
            out[code] = 1.0
        return out
    if mode == "grouped":
        grp = _floor_group_label(f)
        if grp in out:
            out[grp] = 1.0
        return out
    key = str(int(f)) if f == int(f) else f"{f:g}"
    col = f"floor_{key}"
    if col in out:
        out[col] = 1.0
    return out


def _prepare_work(df: pd.DataFrame, req: CollectiveRegressionRequest) -> pd.DataFrame:
    work = df.copy()
    work = work.dropna(subset=["price"])
    if req.exclude_outliers_iqr and len(work) >= 4:
        up = work["unit_price"].astype(float)
        q1, q3 = up.quantile(0.25), up.quantile(0.75)
        iqr = q3 - q1
        mult = req.outlier_iqr_multiplier
        lo, hi = q1 - mult * iqr, q3 + mult * iqr
        work = work[(up >= lo) & (up <= hi)]
    return work


def _continuous_range(work: pd.DataFrame, col: str) -> ContinuousRange | None:
    if col not in work.columns or not work[col].notna().any():
        return None
    s = work[col].astype(float)
    return ContinuousRange(name=col, min=float(s.min()), max=float(s.max()))


def _normalize_structure(series: pd.Series) -> pd.Series:
    s = series.where(series.notna(), "미상").astype(str).str.strip()
    return s.replace({"": "미상", "nan": "미상", "None": "미상"})


def _building_level_values(work: pd.DataFrame, col: str) -> pd.Series:
    if col not in work.columns:
        return pd.Series(dtype=object)
    if col == "structure_group":
        tmp = work.assign(_v=_normalize_structure(work[col]))
        col = "_v"
        work = tmp
    else:
        work = work.loc[work[col].notna()]
        if work.empty:
            return pd.Series(dtype=object)
    if "building_key" not in work.columns:
        return work[col]
    return work.groupby("building_key")[col].first()


def _resolve_entering_attrs(
    work: pd.DataFrame,
    req: CollectiveRegressionRequest,
    warnings: list[str],
) -> tuple[pd.DataFrame, set[str]]:
    v = req.variables
    entering: set[str] = set()
    for flag, col, label in _ATTR_FLAG_COLS:
        if not getattr(v, flag, False):
            continue
        if col not in work.columns:
            warnings.append(f"{label} 데이터 없음 — 생략")
            continue
        grain = _building_level_values(work, col)
        n_unique = int(grain.nunique(dropna=True))
        if n_unique < 2:
            if "building_key" not in work.columns or work["building_key"].nunique() <= 1:
                warnings.append(f"{label} — 단지 상수라 단일 단지에서는 식별되지 않습니다")
            else:
                warnings.append(f"{label} — 단지 간 차이가 없어 생략")
            continue
        entering.add(col)

    drop_cols = [c for c in entering if c in _ATTR_CONTINUOUS]
    if drop_cols:
        n0 = len(work)
        work = work.dropna(subset=drop_cols)
        dropped = n0 - len(work)
        if dropped:
            warnings.append(f"단지 속성 결측 {dropped}건 제외")
        still: set[str] = set()
        for col in entering:
            grain = _building_level_values(work, col)
            if int(grain.nunique(dropna=True)) >= 2:
                still.add(col)
            else:
                label = next(lb for _, c, lb in _ATTR_FLAG_COLS if c == col)
                warnings.append(f"{label} — 결측 제외 후 단지 간 차이가 없어 생략")
        entering = still
    return work, entering


def _add_building_fe(
    work: pd.DataFrame,
    meta: RegressionDesignMeta,
    labels: dict[str, str],
    parts: list[pd.DataFrame],
    warnings: list[str],
) -> None:
    keys = work["building_key"].astype(str)
    ref = str(work.groupby("building_key").size().idxmax())
    meta.building_reference_key = ref
    ref_name = meta.building_labels.get(ref, ref[:12])
    warnings.append(f"단지 FE 기준: {ref_name} (거래 최다)")
    for bk in sorted(keys.unique()):
        if bk == ref:
            continue
        cnt = meta.building_counts.get(bk, 0)
        bk_name = meta.building_labels.get(bk, bk[:12])
        if cnt < MIN_BUILDING_FE_GROUP:
            warnings.append(f"단지 FE 제외 — {bk_name} n={cnt} (최소 {MIN_BUILDING_FE_GROUP}건)")
            continue
        col = _sanitize_key(bk, "bld")
        work[col] = (keys == bk).astype(float)
        parts.append(work[[col]])
        labels[col] = f"단지 {bk_name}"
        meta.building_fe_map[bk] = col


def _add_structure_dummies(
    work: pd.DataFrame,
    meta: RegressionDesignMeta,
    labels: dict[str, str],
    parts: list[pd.DataFrame],
    warnings: list[str],
) -> None:
    raw = _normalize_structure(work["structure_group"])
    grain = work.assign(_s=raw).groupby("building_key")["_s"].first() if "building_key" in work.columns else raw
    levels = [str(x) for x in grain.dropna().unique() if str(x)]
    if len(levels) < 2:
        warnings.append("구조 범주가 한 종류뿐이라 더미를 넣지 않았습니다")
        return
    counts = raw.value_counts()
    ref = str(counts.idxmax()) if not counts.empty else levels[0]
    meta.structure_reference = ref
    dummy_cols: list[str] = []
    for lv in sorted(levels):
        if lv == ref:
            continue
        col = f"struct_{lv}"
        work[col] = (raw == lv).astype(float)
        parts.append(work[[col]])
        labels[col] = f"구조 {lv} (기준 대비)"
        dummy_cols.append(col)
    meta.structure_dummy_cols = dummy_cols


def _warn_type_floor_split(work: pd.DataFrame, warnings: list[str]) -> None:
    """한 건물에서 층으로 유형이 갈리면 유형 계수는 층 효과를 포함함."""
    if "asset_type" not in work.columns or "floor" not in work.columns:
        return
    ranges: dict[str, tuple[float, float]] = {}
    tmp = work.assign(
        _at=work["asset_type"].fillna("").astype(str).str.strip(),
        _fl=pd.to_numeric(work["floor"], errors="coerce"),
    )
    for at, g in tmp.groupby("_at"):
        fl = g["_fl"].dropna()
        if not at or fl.empty:
            continue
        ranges[str(at)] = (float(fl.min()), float(fl.max()))
    if len(ranges) < 2:
        return
    types = list(ranges)
    overlap = False
    for i, a in enumerate(types):
        for b in types[i + 1 :]:
            lo = max(ranges[a][0], ranges[b][0])
            hi = min(ranges[a][1], ranges[b][1])
            if lo <= hi:
                overlap = True
    if overlap:
        return
    bits = " · ".join(
        f"{_ASSET_TYPE_LABELS.get(t, t)} {int(lo)}–{int(hi)}층"
        for t, (lo, hi) in sorted(ranges.items(), key=lambda x: x[1][0])
    )
    warnings.append(
        f"유형이 층으로 갈립니다 ({bits}). 같은 층에 두 유형이 없어 "
        "유형 계수는 층 구간 차이를 포함합니다. 순수 유형 효과로 읽지 마세요."
    )


def _add_asset_type_dummies(
    work: pd.DataFrame,
    meta: RegressionDesignMeta,
    labels: dict[str, str],
    parts: list[pd.DataFrame],
    warnings: list[str],
) -> None:
    raw = work["asset_type"].fillna("").astype(str).str.strip()
    levels = [lv for lv in raw.unique() if lv]
    if len(levels) < 2:
        warnings.append("유형이 한 종류뿐이라 더미를 넣지 않았습니다")
        return
    counts = raw.value_counts()
    ref = str(counts.idxmax())
    meta.asset_type_reference = ref
    dummy_cols: list[str] = []
    for lv in sorted(levels):
        if lv == ref:
            continue
        col = f"atype_{lv}"
        work[col] = (raw == lv).astype(float)
        parts.append(work[[col]])
        labels[col] = f"유형 {_ASSET_TYPE_LABELS.get(lv, lv)} (기준 대비)"
        dummy_cols.append(col)
    meta.asset_type_dummy_cols = dummy_cols


def _build_design_matrix(
    work: pd.DataFrame,
    req: CollectiveRegressionRequest,
    *,
    cohort_mode: bool = False,
    building_display_names: dict[str, str] | None = None,
) -> tuple[pd.Series, pd.DataFrame, dict[str, str], RegressionDesignMeta, list[str]]:
    warnings: list[str] = []
    meta = RegressionDesignMeta(floor_mode=req.variables.floor_mode)
    labels: dict[str, str] = {"const": "절편"}
    parts: list[pd.DataFrame] = []

    work, entering_attrs = _resolve_entering_attrs(work, req, warnings)
    meta.used_building_attrs = bool(entering_attrs)
    if work.empty:
        return (
            pd.Series(dtype=float),
            pd.DataFrame(),
            labels,
            meta,
            warnings + ["단지 속성 결측으로 표본이 없습니다"],
        )

    display_names = building_display_names or {}
    if "building_key" in work.columns:
        for bk, cnt in work.groupby("building_key").size().items():
            meta.building_counts[str(bk)] = int(cnt)
            meta.building_labels[str(bk)] = display_names.get(str(bk), str(bk))

    use_fe = (
        cohort_mode
        and "building_key" in work.columns
        and work["building_key"].nunique() > 1
        and not entering_attrs
    )
    if entering_attrs and cohort_mode and "building_key" in work.columns and work["building_key"].nunique() > 1:
        names = "·".join(
            lb for _, col, lb in _ATTR_FLAG_COLS if col in entering_attrs
        )
        warnings.append(f"단지 FE 생략 — 단지 속성({names})으로 단지 간 차이를 설명")
    if use_fe:
        _add_building_fe(work, meta, labels, parts, warnings)

    if req.variables.exclusive_area:
        parts.append(work[["exclusive_area"]].astype(float))
        labels["exclusive_area"] = "전용면적"
        rng = _continuous_range(work, "exclusive_area")
        if rng:
            meta.continuous_ranges["exclusive_area"] = (rng.min, rng.max)

    if req.variables.building_age:
        parts.append(work[["building_age"]].astype(float))
        labels["building_age"] = "연식"
        rng = _continuous_range(work, "building_age")
        if rng:
            meta.continuous_ranges["building_age"] = (rng.min, rng.max)

    floor_dummy_cols: list[str] = []
    if req.variables.floor and work["floor"].notna().any():
        meta.max_floor = float(work["floor"].astype(float).max())
        floor_part, floor_labels, floor_dummy_cols = _add_floor_columns(
            work, req.variables.floor_mode, max_floor=meta.max_floor
        )
        if not floor_part.empty:
            parts.append(floor_part)
            labels.update(floor_labels)
        rng = _continuous_range(work, "floor")
        if rng:
            meta.continuous_ranges["floor"] = (rng.min, rng.max)

    if req.variables.dong and "dong" in work.columns and work["dong"].notna().any():
        series = _clean_dong_values(work["dong"])
        nested = (
            cohort_mode
            and "building_key" in work.columns
            and work["building_key"].nunique() > 1
        )
        if nested:
            dong_part = _add_nested_dong_columns(work, meta, labels, warnings)
        else:
            dong_part = _add_pooled_dong_columns(work, series, meta, labels)
        if not dong_part.empty:
            parts.append(dong_part)

    if (
        req.variables.housing_subtype
        and "housing_subtype" in work.columns
        and work["housing_subtype"].notna().any()
    ):
        series = work["housing_subtype"].astype(str).str.strip()
        cats = sorted(c for c in series.dropna().unique() if c and c not in ("nan", "None"))
        if len(cats) >= 2:
            meta.housing_subtype_categories = cats
            meta.housing_subtype_reference = cats[0]
            dummies = pd.get_dummies(series, prefix="rights", drop_first=True)
            if not dummies.empty:
                parts.append(dummies)
                for c in dummies.columns:
                    labels[c] = f"권리 {c.replace('rights_', '')}"

    if "households" in entering_attrs:
        parts.append(work[["households"]].astype(float))
        labels["households"] = "세대수"
        rng = _continuous_range(work, "households")
        if rng:
            meta.continuous_ranges["households"] = (rng.min, rng.max)
    if "parking_per_household" in entering_attrs:
        parts.append(work[["parking_per_household"]].astype(float))
        labels["parking_per_household"] = "세대당 주차"
        rng = _continuous_range(work, "parking_per_household")
        if rng:
            meta.continuous_ranges["parking_per_household"] = (rng.min, rng.max)
    if "assessed_land_price" in entering_attrs:
        parts.append(work[["assessed_land_price"]].astype(float))
        labels["assessed_land_price"] = "개별공시지가 (원/㎡)"
        rng = _continuous_range(work, "assessed_land_price")
        if rng:
            meta.continuous_ranges["assessed_land_price"] = (rng.min, rng.max)
    if "structure_group" in entering_attrs:
        _add_structure_dummies(work, meta, labels, parts, warnings)
    if "asset_type" in entering_attrs:
        _add_asset_type_dummies(work, meta, labels, parts, warnings)
        _warn_type_floor_split(work, warnings)

    meta.column_labels = labels
    meta.floor_dummy_cols = floor_dummy_cols

    if not parts:
        empty_x = pd.DataFrame(index=work.index)
        return work["price"].astype(float), empty_x, labels, meta, warnings

    X = pd.concat(parts, axis=1).astype(float)
    y = work["price"].astype(float)
    return y, X, labels, meta, warnings


def _meta_to_predict_options(meta: RegressionDesignMeta, req: CollectiveRegressionRequest) -> CollectivePredictOptions:
    opts = CollectivePredictOptions(floor_mode=req.variables.floor_mode, max_floor=meta.max_floor)

    if req.variables.exclusive_area and "exclusive_area" in meta.continuous_ranges:
        lo, hi = meta.continuous_ranges["exclusive_area"]
        opts.exclusive_area = ContinuousRange(name="exclusive_area", min=lo, max=hi)
    if req.variables.building_age and "building_age" in meta.continuous_ranges:
        lo, hi = meta.continuous_ranges["building_age"]
        opts.building_age = ContinuousRange(name="building_age", min=lo, max=hi)
    if req.variables.floor and "floor" in meta.continuous_ranges:
        lo, hi = meta.continuous_ranges["floor"]
        opts.floor = ContinuousRange(name="floor", min=lo, max=hi)

    if req.variables.dong and (meta.dong_categories or meta.dong_options):
        opts.dongs = [o.dong for o in meta.dong_options] if meta.dong_options else meta.dong_categories
        opts.dong_reference = meta.dong_reference
        opts.dong_options = list(meta.dong_options)

    if req.variables.housing_subtype and meta.housing_subtype_categories:
        opts.housing_subtypes = meta.housing_subtype_categories
        opts.housing_subtype_reference = meta.housing_subtype_reference

    if "households" in meta.continuous_ranges:
        lo, hi = meta.continuous_ranges["households"]
        opts.households = ContinuousRange(name="households", min=lo, max=hi)
    if "parking_per_household" in meta.continuous_ranges:
        lo, hi = meta.continuous_ranges["parking_per_household"]
        opts.parking_per_household = ContinuousRange(name="parking_per_household", min=lo, max=hi)
    if "assessed_land_price" in meta.continuous_ranges:
        lo, hi = meta.continuous_ranges["assessed_land_price"]
        opts.assessed_land_price = ContinuousRange(name="assessed_land_price", min=lo, max=hi)
    if meta.structure_dummy_cols or meta.structure_reference:
        opts.structure_reference = meta.structure_reference
        refs = [meta.structure_reference] if meta.structure_reference else []
        opts.structure_groups = refs + [
            c.replace("struct_", "", 1) for c in meta.structure_dummy_cols
        ]
    if meta.asset_type_dummy_cols or meta.asset_type_reference:
        opts.asset_type_reference = meta.asset_type_reference
        refs = [meta.asset_type_reference] if meta.asset_type_reference else []
        opts.asset_types = refs + [c.replace("atype_", "", 1) for c in meta.asset_type_dummy_cols]

    if len(meta.building_counts) > 1:
        for bk, cnt in sorted(meta.building_counts.items(), key=lambda x: -x[1]):
            opts.buildings.append(
                BuildingFeOption(
                    building_key=bk,
                    display_name=meta.building_labels.get(bk, bk),
                    count=cnt,
                    is_reference=(bk == meta.building_reference_key),
                    has_fe=(bk in meta.building_fe_map),
                )
            )
    return opts


def _fit_regression(
    y: pd.Series,
    X: pd.DataFrame,
    labels: dict[str, str],
    meta: RegressionDesignMeta,
    req: CollectiveRegressionRequest,
    base_warnings: list[str],
) -> tuple[sm.regression.linear_model.RegressionResultsWrapper | None, CollectiveRegressionResponse]:
    if X.empty:
        return None, CollectiveRegressionResponse(
            building_key="",
            display_name="",
            n=len(y),
            warnings=base_warnings + ["선택 변수 없음"],
        )

    X_const = sm.add_constant(X, has_constant="add")
    model_type = req.model_type
    if model_type == "log" and (y <= 0).any():
        base_warnings = base_warnings + ["price≤0 거래가 있어 선형모델로 대체"]
        model_type = "linear"
    y_fit = np.log(y) if model_type == "log" else y
    try:
        model = sm.OLS(y_fit, X_const, missing="drop").fit()
    except Exception as exc:
        return None, CollectiveRegressionResponse(
            building_key="",
            display_name="",
            n=len(y),
            warnings=base_warnings + [f"회귀 실패: {exc}"],
        )

    warnings = list(base_warnings)
    if int(model.nobs) < 30:
        warnings.append(f"n={int(model.nobs)} — 참고용 (권장 n≥30)")

    metrics = fit_model_price_metrics(y, X_const, model, model_type)

    coefs: list[RegressionCoeff] = []
    for name in X_const.columns:
        if name not in model.params.index:
            continue
        coefs.append(
            RegressionCoeff(
                name=name,
                label=labels.get(name, name),
                coef=float(model.params[name]),
                se=float(model.bse[name]) if name in model.bse.index else None,
                t=float(model.tvalues[name]) if name in model.tvalues.index else None,
                p=float(model.pvalues[name]) if name in model.pvalues.index else None,
            )
        )

    equation, enriched, price_adj = enrich_regression_response(
        coefs,
        model_type=model_type,
        price_adj_r_squared=metrics.get("price_adj_r_squared"),
    )
    coefs = [RegressionCoeff(**row) for row in enriched]
    sig_count = count_significant_coefficients(coefs)

    predict_options = _meta_to_predict_options(meta, req)
    return model, CollectiveRegressionResponse(
        building_key="",
        display_name="",
        n=int(model.nobs),
        model_type=model_type,
        r_squared=float(model.rsquared) if model.rsquared is not None else None,
        adj_r_squared=float(model.rsquared_adj) if model.rsquared_adj is not None else None,
        price_adj_r_squared=price_adj,
        mape=metrics.get("mape"),
        f_p_value=float(model.f_pvalue) if model.f_pvalue is not None else None,
        significant_count=sig_count,
        equation=equation,
        coefficients=coefs,
        warnings=warnings,
        predict_options=predict_options,
        model_comparison=None,
    )


def _extrapolation_warnings(meta: RegressionDesignMeta, inputs: CollectiveRegressionPredictInputs) -> list[str]:
    warns: list[str] = []
    for key, val in [
        ("exclusive_area", inputs.exclusive_area),
        ("building_age", inputs.building_age),
        ("floor", inputs.floor),
        ("households", inputs.households),
        ("parking_per_household", inputs.parking_per_household),
        ("assessed_land_price", inputs.assessed_land_price),
    ]:
        if val is None or key not in meta.continuous_ranges:
            continue
        lo, hi = meta.continuous_ranges[key]
        if lo is not None and val < lo:
            warns.append(f"{key}={val} — 표본 하한({lo}) 미만 (외삽)")
        if hi is not None and val > hi:
            warns.append(f"{key}={val} — 표본 상한({hi}) 초과 (외삽)")
    return warns


def _inputs_to_x_row(
    X: pd.DataFrame,
    meta: RegressionDesignMeta,
    req: CollectiveRegressionRequest,
    inputs: CollectiveRegressionPredictInputs,
) -> pd.Series:
    row = {c: 0.0 for c in X.columns}
    if req.variables.exclusive_area and inputs.exclusive_area is not None:
        row["exclusive_area"] = float(inputs.exclusive_area)
    if req.variables.building_age and inputs.building_age is not None:
        row["building_age"] = float(inputs.building_age)

    floor_dummy_cols = meta.floor_dummy_cols
    if req.variables.floor and floor_dummy_cols:
        mx = float(meta.max_floor or inputs.floor or 1)
        floor_vals = _floor_row_for_predict(inputs.floor, req.variables.floor_mode, mx, floor_dummy_cols)
        for c, v in floor_vals.items():
            if c in row:
                row[c] = v

    if req.variables.dong and inputs.dong is not None:
        dong = str(inputs.dong).strip()
        if meta.dong_fe_map:
            bk = str(inputs.building_key or meta.building_reference_key or "")
            ref = meta.dong_reference_by_building.get(bk)
            if dong != ref:
                col = meta.dong_fe_map.get((bk, dong))
                if col and col in row:
                    row[col] = 1.0
        elif meta.dong_reference and dong != meta.dong_reference:
            col = f"dong_{dong}"
            if col in row:
                row[col] = 1.0

    if req.variables.housing_subtype and inputs.housing_subtype is not None:
        hs = str(inputs.housing_subtype).strip()
        if meta.housing_subtype_reference and hs != meta.housing_subtype_reference:
            col = f"rights_{hs}"
            if col in row:
                row[col] = 1.0

    if "households" in row and inputs.households is not None:
        row["households"] = float(inputs.households)
    if "parking_per_household" in row and inputs.parking_per_household is not None:
        row["parking_per_household"] = float(inputs.parking_per_household)
    if "assessed_land_price" in row and inputs.assessed_land_price is not None:
        row["assessed_land_price"] = float(inputs.assessed_land_price)

    if inputs.structure_group is not None and meta.structure_reference:
        sg = str(inputs.structure_group).strip()
        if sg != meta.structure_reference:
            col = f"struct_{sg}"
            if col in row:
                row[col] = 1.0

    if inputs.asset_type is not None and meta.asset_type_reference:
        at = str(inputs.asset_type).strip()
        if at != meta.asset_type_reference:
            col = f"atype_{at}"
            if col in row:
                row[col] = 1.0

    if inputs.building_key and meta.building_reference_key:
        bk = str(inputs.building_key)
        if bk != meta.building_reference_key and bk in meta.building_fe_map:
            col = meta.building_fe_map[bk]
            if col in row:
                row[col] = 1.0

    return pd.Series(row, index=X.columns)


def _run_regression_core(
    df: pd.DataFrame,
    req: CollectiveRegressionRequest,
    *,
    cohort_mode: bool = False,
    building_display_names: dict[str, str] | None = None,
) -> tuple[sm.regression.linear_model.RegressionResultsWrapper | None, pd.DataFrame, RegressionDesignMeta, CollectiveRegressionResponse]:
    if df.empty:
        resp = CollectiveRegressionResponse(
            building_key="",
            display_name="",
            n=0,
            warnings=["거래 표본 없음"],
        )
        return None, pd.DataFrame(), RegressionDesignMeta(), resp

    work = _prepare_work(df, req)
    n = len(work)
    if n < 5:
        resp = CollectiveRegressionResponse(
            building_key="",
            display_name="",
            n=n,
            warnings=[f"n={n} — 회귀 최소 표본 부족"],
        )
        return None, pd.DataFrame(), RegressionDesignMeta(), resp

    y, X, labels, meta, fe_warnings = _build_design_matrix(
        work,
        req,
        cohort_mode=cohort_mode,
        building_display_names=building_display_names,
    )
    model, resp = _fit_regression(y, X, labels, meta, req, fe_warnings)
    return model, X, meta, resp


def run_building_regression(
    df: pd.DataFrame,
    building_key: str,
    display_name: str,
    req: CollectiveRegressionRequest,
) -> CollectiveRegressionResponse:
    _, _, _, resp = _run_regression_core(df, req, cohort_mode=False)
    resp.model_candidates = suggest_collective_regression(df, req, cohort_mode=False)
    resp.building_key = building_key
    resp.display_name = display_name
    return resp


def run_cohort_regression(
    df: pd.DataFrame,
    building_keys: list[str],
    display_label: str,
    req: CollectiveRegressionRequest,
    *,
    building_display_names: dict[str, str] | None = None,
) -> CollectiveRegressionResponse:
    names = building_display_names or {}
    if not names and "display_name" in df.columns and "building_key" in df.columns:
        for _, row in df.drop_duplicates("building_key").iterrows():
            names[str(row["building_key"])] = str(row.get("display_name") or row["building_key"])

    _, _, _, resp = _run_regression_core(
        df,
        req,
        cohort_mode=True,
        building_display_names=names,
    )
    resp.model_candidates = suggest_collective_regression(
        df,
        req,
        cohort_mode=True,
        building_display_names=names,
    )
    if len(building_keys) > 1 and resp.n > 0 and not any("단지 FE" in w for w in resp.warnings):
        resp.warnings.insert(0, f"코호트 {len(building_keys)}개 단지 — 단지 고정효과 적용")
    resp.building_key = building_keys[0] if building_keys else ""
    resp.display_name = display_label
    return resp


def suggest_collective_regression(
    df: pd.DataFrame,
    req: CollectiveRegressionRequest,
    *,
    cohort_mode: bool = False,
    building_display_names: dict[str, str] | None = None,
) -> list[CollectiveModelCandidate]:
    """건물·코호트 회귀의 변수 블록 후보를 비교한다.

    본건 건물 회귀와 코호트 회귀의 기존 경로는 유지하고, 동일 데이터에
    변수 블록 후보만 추가로 적합해 추천 목록으로 제공한다.
    """
    fields = ["exclusive_area", "building_age", "floor", "dong", "housing_subtype"]
    enabled = [field for field in fields if getattr(req.variables, field, False)]
    if not enabled:
        return []
    scored: list[CollectiveModelCandidate] = []
    for mask in range(1, min((1 << len(enabled)) - 1, 64) + 1):
        chosen = [enabled[i] for i in range(len(enabled)) if mask & (1 << i)]
        variables = req.variables.model_copy(
            update={field: field in chosen for field in fields}
        )
        candidate_req = req.model_copy(update={"variables": variables})
        try:
            _, _, _, response = _run_regression_core(
                df,
                candidate_req,
                cohort_mode=cohort_mode,
                building_display_names=building_display_names,
            )
        except Exception:
            continue
        if response.n <= 0:
            continue
        scored.append(
            CollectiveModelCandidate(
                rank=0,
                blocks=chosen,
                variables=variables,
                model_type=response.model_type,
                n=response.n,
                adj_r_squared=response.price_adj_r_squared or response.adj_r_squared,
                mape=response.mape,
                cv_mape=(
                    response.model_comparison.log.cv_mape
                    if response.model_type == "log"
                    and response.model_comparison
                    and response.model_comparison.log
                    else response.model_comparison.linear.cv_mape
                    if response.model_comparison and response.model_comparison.linear
                    else None
                ),
            )
        )
    scored.sort(
        key=lambda item: (
            item.cv_mape if item.cv_mape is not None else float("inf"),
            -(item.adj_r_squared or float("-inf")),
        )
    )
    return [item.model_copy(update={"rank": i + 1}) for i, item in enumerate(scored[:5])]


def predict_regression(
    df: pd.DataFrame,
    req: CollectiveRegressionRequest,
    inputs: CollectiveRegressionPredictInputs,
    *,
    cohort_mode: bool = False,
    building_display_names: dict[str, str] | None = None,
) -> dict:
    model, X, meta, fit_resp = _run_regression_core(
        df,
        req,
        cohort_mode=cohort_mode,
        building_display_names=building_display_names,
    )
    if model is None or X.empty:
        raise ValueError("; ".join(fit_resp.warnings) or "예측 불가 — 회귀 미추정")

    x_row = _inputs_to_x_row(X, meta, req, inputs)
    vals: dict[str, float] = {"const": 1.0}
    vals.update(x_row.to_dict())
    x_df = pd.DataFrame([vals]).reindex(columns=model.params.index, fill_value=0.0)
    frame = model.get_prediction(x_df).summary_frame(alpha=0.05)
    row = frame.iloc[0]

    warnings = _extrapolation_warnings(meta, inputs)
    if fit_resp.n < 30:
        warnings.insert(0, f"n={fit_resp.n} — 참고용 (권장 n≥30, 예측구간 넓음)")

    model_type = fit_resp.model_type
    if model_type == "log":
        # 로그모델: 평균·평균CI는 Duan smearing 보정, 예측구간(PI)은 분위수 환산
        duan = _duan_smearing(model.resid)
        y_hat = float(np.exp(float(row["mean"])) * duan)
        pi_lower = float(np.exp(float(row["obs_ci_lower"])))
        pi_upper = float(np.exp(float(row["obs_ci_upper"])))
        ci_lower = float(np.exp(float(row["mean_ci_lower"])) * duan)
        ci_upper = float(np.exp(float(row["mean_ci_upper"])) * duan)
    else:
        y_hat = float(row["mean"])
        pi_lower = float(row["obs_ci_lower"])
        pi_upper = float(row["obs_ci_upper"])
        ci_lower = float(row["mean_ci_lower"])
        ci_upper = float(row["mean_ci_upper"])

    exclusive = inputs.exclusive_area
    unit_hat = round(y_hat / float(exclusive), 2) if exclusive and float(exclusive) > 0 else None

    return {
        "n": fit_resp.n,
        "model_type": model_type,
        "y_hat": round(y_hat, 1),
        "pi_lower": round(pi_lower, 1),
        "pi_upper": round(pi_upper, 1),
        "ci_lower": round(ci_lower, 1),
        "ci_upper": round(ci_upper, 1),
        "unit_price_hat": unit_hat,
        "warnings": warnings,
    }
