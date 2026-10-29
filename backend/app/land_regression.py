"""토지 단가 헤도닉 OLS 회귀·예측 엔진.

입력: _fetch_matrix_cell_filtered_transactions 결과(list[dict])
출력: LandRegressionResponse / LandRegressionPredictResponse
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm

from app.regression_missing import (
    categorical_dummies,
    drop_unknown_rows,
    normalize_categories,
    pick_reference,
    treatment_label,
)
from app.regression_contracts import build_analysis_context, grouped_sample_details

if TYPE_CHECKING:
    from app.schemas import (
        LandRegressionPredictRequest,
        LandRegressionPredictResponse,
        LandRegressionRequest,
        LandRegressionResponse,
    )

MIN_N = 10  # 절대 최소 (요청 min_n보다 우선 낮게 설정 불가)

_COEF_LABELS: dict[str, str] = {
    "const": "상수(기준)",
    "log_area": "log(면적)",
    "area_sqm": "면적(㎡)",
    "year_trend": "연도 추세",
    "log_assessed_land_price": "log(개별공시지가)",
}


def _duan_smearing(residuals: Any) -> float:
    """log(y) 모형 역변환 시 Duan smearing (E[exp(e)])."""
    r = np.asarray(residuals, dtype=float)
    r = r[np.isfinite(r)]
    if r.size == 0:
        return 1.0
    return float(np.mean(np.exp(r)))


@dataclass
class _DesignBundle:
    y_fit: pd.Series
    X_const: pd.DataFrame
    model_type: str
    reference_categories: dict[str, str]
    warnings: list[str]
    year_mean: float
    area_min: float
    area_max: float
    year_min: int
    year_max: int
    road_cats: list[str] = field(default_factory=list)
    deal_cats: list[str] = field(default_factory=list)
    beop_cats: list[str] = field(default_factory=list)
    use_log_area: bool = False
    use_area: bool = False
    use_year: bool = False
    use_road: bool = False
    use_deal: bool = False
    use_partial: bool = False
    use_beop: bool = False
    use_assessed: bool = False


def _prepare_df(rows: list[dict], req: "LandRegressionRequest") -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    df = pd.DataFrame(rows)
    if "id" in df.columns:
        df = df.sort_values("id", kind="stable").reset_index(drop=True)
    df = df.dropna(subset=["unit_price_per_sqm", "area_sqm"])
    df["unit_price_per_sqm"] = df["unit_price_per_sqm"].astype(float)
    df["area_sqm"] = df["area_sqm"].astype(float)
    df["contract_year"] = df["contract_year"].astype(int)

    if req.exclude_outliers_iqr:
        px = df["unit_price_per_sqm"].values
        q1, q3 = np.percentile(px, 25), np.percentile(px, 75)
        iqr = q3 - q1
        mult = float(req.outlier_iqr_multiplier)
        mask = (px >= q1 - mult * iqr) & (px <= q3 + mult * iqr)
        n_removed = int((~mask).sum())
        df = df[mask].copy()
        if n_removed:
            warnings.append(f"IQR 이상치 {n_removed}건 제외 (배수 {mult})")
    return df, warnings


def _exclude_assessed_shares(df: pd.DataFrame, warnings: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """공시지가 분석 및 그 후보 탐색에서 보강 불가 지분거래를 제외한다."""
    out = list(warnings)
    if "is_partial_ownership" in df.columns:
        shares = df["is_partial_ownership"].fillna(False).astype(bool)
        n_share = int(shares.sum())
        df = df.loc[~shares].copy()
        if n_share:
            out.append(f"지분거래 {n_share}건 제외 — 대장 보강이 불가능해 공시지가 모형에 사용하지 않습니다.")
    return df, out


def _apply_assessed_case(
    df: pd.DataFrame, req: "LandRegressionRequest", warnings: list[str]
) -> tuple[pd.DataFrame, list[str]]:
    """공시지가 모형은 연결된 전체면적 거래만 사용하며 값을 보충하지 않는다."""
    if not req.variables.assessed_land_price:
        return df, warnings
    df, out = _exclude_assessed_shares(df, warnings)
    if "official_price_won" not in df.columns:
        df = df.copy()
        df["official_price_won"] = np.nan
    price = pd.to_numeric(df["official_price_won"], errors="coerce")
    keep = price > 0
    n_drop = int((~keep).sum())
    df = df.loc[keep].copy()
    if not df.empty:
        df["official_price_won"] = price.loc[keep].astype(float)
    if n_drop:
        out.append(f"개별공시지가 결측 {n_drop}건 제외")
    return df, out


def _build_design(df: pd.DataFrame, req: "LandRegressionRequest", base_warnings: list[str]) -> _DesignBundle:
    warnings = list(base_warnings)
    y = df["unit_price_per_sqm"].copy()
    model_type = req.model_type
    if model_type == "log" and (y <= 0).any():
        model_type = "linear"
        warnings.append("단가 ≤ 0인 행이 있어 선형 모델로 전환했습니다.")
    y_fit = np.log(y) if model_type == "log" else y

    X_parts: list[pd.DataFrame] = []
    reference_categories: dict[str, str] = {}
    v = req.variables

    use_log_area = False
    use_area = False
    if v.area_sqm:
        if v.log_area:
            log_a = np.log(df["area_sqm"].clip(lower=0.01))
            X_parts.append(log_a.rename("log_area").to_frame())
            use_log_area = True
        else:
            X_parts.append(df[["area_sqm"]].copy())
            use_area = True

    year_mean = float(df["contract_year"].mean())
    use_year = False
    if v.year_trend:
        yr_centered = (df["contract_year"] - year_mean).rename("year_trend")
        X_parts.append(yr_centered.to_frame())
        use_year = True

    use_assessed = False
    if v.assessed_land_price and "official_price_won" in df.columns and len(df):
        X_parts.append(np.log(df["official_price_won"].astype(float)).rename("log_assessed_land_price").to_frame())
        use_assessed = True

    road_cats: list[str] = []
    use_road = False
    if v.road_condition:
        dummies, cats, ref = categorical_dummies(df["road_condition"], "road")
        if ref and not dummies.empty:
            reference_categories["도로조건"] = ref
            road_cats = cats
            dummies.columns = [c.replace(" ", "_") for c in dummies.columns]
            X_parts.append(dummies.astype(float))
            use_road = True
        else:
            warnings.append("도로조건 범주가 1개 이하 — 더미 제외")

    deal_cats: list[str] = []
    use_deal = False
    if v.deal_type:
        dummies, cats, ref = categorical_dummies(df["deal_type"], "deal")
        if ref and not dummies.empty:
            reference_categories["거래유형"] = ref
            deal_cats = cats
            X_parts.append(dummies.astype(float))
            use_deal = True
        else:
            warnings.append("거래유형 범주가 1개 이하 — 더미 제외")

    use_partial = False
    if v.partial_ownership:
        col = df["partial_ownership_label"].fillna("").astype(str).str.strip()
        has_partial = col.str.len() > 0
        if has_partial.sum() > 0 and (~has_partial).sum() > 0:
            X_parts.append(has_partial.astype(float).rename("partial_own").to_frame())
            use_partial = True
        else:
            warnings.append("지분 여부 단일값 — 더미 제외")

    beop_cats: list[str] = []
    use_beop = False
    if v.beopjungri_fe:
        col = normalize_categories(df["beopjungri_name"])
        n_beop = col.nunique()
        ref = pick_reference(col)
        if n_beop >= 2 and ref:
            reference_categories["법정동"] = str(ref)
            dummies = pd.get_dummies(col, prefix="beop", drop_first=False)
            ref_col = f"beop_{ref}"
            dummies = dummies.drop(columns=[ref_col], errors="ignore")
            small = [c for c in dummies.columns if dummies[c].sum() < 3]
            if small:
                dummies = dummies.drop(columns=small)
                warnings.append(f"법정동 FE: {len(small)}개 소수집단 제외")
            if not dummies.empty:
                X_parts.append(dummies.astype(float))
                use_beop = True
                beop_cats = [str(ref)] + [str(c)[len("beop_") :] for c in dummies.columns]
        else:
            warnings.append("법정동이 1개 — FE 제외")

    if not X_parts:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="투입 변수가 없습니다. 하나 이상의 변수를 선택하세요.")

    X = pd.concat(X_parts, axis=1)
    X = X.loc[:, X.nunique() > 1]
    X_const = sm.add_constant(X, has_constant="add")
    aligned_y = y_fit.loc[X_const.index]

    # 상수항·분산 제거 후 실제 남은 더미만 예측 옵션에 반영
    colset = set(X_const.columns)
    if use_road and road_cats:
        ref_r = reference_categories.get("도로조건")
        road_lookup = {r.replace(" ", "_"): r for r in road_cats}
        rebuilt: list[str] = []
        if ref_r:
            rebuilt.append(ref_r)
        for c in X_const.columns:
            if not str(c).startswith("road_"):
                continue
            raw = str(c)[len("road_") :]
            rebuilt.append(road_lookup.get(raw, raw.replace("_", " ")))
        road_cats = rebuilt
        use_road = any(str(c).startswith("road_") for c in colset) or bool(ref_r)
    if use_deal and deal_cats:
        ref_d = reference_categories.get("거래유형")
        deal_kept = [ref_d] if ref_d else []
        for c in X_const.columns:
            if str(c).startswith("deal_"):
                deal_kept.append(str(c)[len("deal_") :])
        deal_cats = deal_kept
        use_deal = any(str(c).startswith("deal_") for c in colset) or bool(ref_d)
    if use_beop and beop_cats:
        ref_b = reference_categories.get("법정동")
        beop_kept = [ref_b] if ref_b else []
        for c in X_const.columns:
            if str(c).startswith("beop_"):
                beop_kept.append(str(c)[len("beop_") :])
        beop_cats = beop_kept
        use_beop = any(str(c).startswith("beop_") for c in colset) or bool(ref_b)
    use_partial = use_partial and "partial_own" in colset
    use_log_area = use_log_area and "log_area" in colset
    use_area = use_area and "area_sqm" in colset
    use_year = use_year and "year_trend" in colset
    use_assessed = use_assessed and "log_assessed_land_price" in colset

    return _DesignBundle(
        y_fit=aligned_y,
        X_const=X_const,
        model_type=model_type,
        reference_categories=reference_categories,
        warnings=warnings,
        year_mean=year_mean,
        area_min=float(df["area_sqm"].min()),
        area_max=float(df["area_sqm"].max()),
        year_min=int(df["contract_year"].min()),
        year_max=int(df["contract_year"].max()),
        road_cats=road_cats,
        deal_cats=deal_cats,
        beop_cats=beop_cats,
        use_log_area=use_log_area,
        use_area=use_area,
        use_year=use_year,
        use_road=use_road,
        use_deal=use_deal,
        use_partial=use_partial,
        use_beop=use_beop,
        use_assessed=use_assessed,
    )


def _to_predict_options(bundle: _DesignBundle) -> "Any":
    from app.schemas import LandPredictContinuous, LandPredictOptions

    continuous: list[LandPredictContinuous] = []
    if bundle.use_area or bundle.use_log_area:
        continuous.append(
            LandPredictContinuous(
                name="area_sqm",
                label="면적(㎡)",
                min=bundle.area_min,
                max=bundle.area_max,
            )
        )
    if bundle.use_year:
        continuous.append(
            LandPredictContinuous(
                name="contract_year",
                label="계약연도",
                min=float(bundle.year_min),
                max=float(bundle.year_max),
            )
        )

    return LandPredictOptions(
        continuous=continuous,
        road_conditions=bundle.road_cats,
        road_reference=bundle.reference_categories.get("도로조건"),
        deal_types=bundle.deal_cats,
        deal_reference=bundle.reference_categories.get("거래유형"),
        beopjungri_names=bundle.beop_cats if bundle.use_beop else [],
        beopjungri_reference=bundle.reference_categories.get("법정동"),
        partial_ownership_enabled=bundle.use_partial,
    )


def _subsample_points(xv: pd.Series, yv: pd.Series, *, max_pts: int = 500) -> list:
    from app.schemas import CorrelationPoint

    step = max(1, len(xv) // max_pts)
    return [
        CorrelationPoint(x=float(xv.iloc[i]), y=float(yv.iloc[i]))
        for i in range(0, len(xv), step)
    ]


def _raw_plot_specs(bundle: _DesignBundle) -> list[tuple[str, str]]:
    """탐색용 산점도 — 원자료 스케일(면적㎡·계약연도)."""
    specs: list[tuple[str, str]] = []
    if bundle.use_area or bundle.use_log_area:
        specs.append(("area_sqm", "면적"))
    if bundle.use_year:
        specs.append(("contract_year", "계약연도"))
    return specs


def _partial_plot_specs(bundle: _DesignBundle) -> list[tuple[str, str]]:
    """부분회귀도 — 설계행렬 연속 열."""
    specs: list[tuple[str, str]] = []
    if bundle.use_log_area:
        specs.append(("log_area", "log(면적)"))
    elif bundle.use_area:
        specs.append(("area_sqm", "면적"))
    if bundle.use_year:
        specs.append(("year_trend", "연도 추세"))
    return specs


def _land_correlations(df: pd.DataFrame, bundle: _DesignBundle) -> list:
    from app.schemas import CorrelationSeries

    out: list = []
    y = pd.to_numeric(df["unit_price_per_sqm"], errors="coerce")
    for col, label in _raw_plot_specs(bundle):
        x = pd.to_numeric(df[col], errors="coerce")
        m = x.notna() & y.notna()
        if int(m.sum()) < 2:
            continue
        xv, yv = x[m], y[m]
        r = float(xv.corr(yv)) if float(xv.std()) > 0 else None
        out.append(
            CorrelationSeries(
                variable=col,
                label=label,
                pearson_r=r,
                points=_subsample_points(xv, yv),
                y_axis_label="단가(만원/㎡)",
            )
        )
    return out


def _land_partial_plots(bundle: _DesignBundle) -> list:
    from app.schemas import PartialRegressionSeries

    y = bundle.y_fit
    X_const = bundle.X_const
    X = X_const.drop(columns=["const"], errors="ignore")
    if len(y) < 10 or X.empty:
        return []

    model = sm.OLS(y, X_const, missing="drop").fit()
    y_label = "log(단가) 잔차" if bundle.model_type == "log" else "단가 잔차"
    out: list = []

    for col, label in _partial_plot_specs(bundle):
        if col not in X.columns:
            continue
        other_cols = [c for c in X.columns if c != col]
        if not other_cols:
            # 연속·더미가 이 변수뿐이면 상수만 통제
            X_other = pd.DataFrame({"const": np.ones(len(X), dtype=float)}, index=X.index)
        else:
            X_other = sm.add_constant(X[other_cols], has_constant="add")

        y_res = sm.OLS(y, X_other, missing="drop").fit().resid
        x_res = sm.OLS(X[col], X_other, missing="drop").fit().resid

        pr2: float | None = None
        if float(x_res.std()) > 0 and float(y_res.std()) > 0:
            pr2 = round(float(x_res.corr(y_res) ** 2), 4)

        beta = float(model.params[col]) if col in model.params else None
        p_val = float(model.pvalues[col]) if col in model.pvalues else None

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


def run_land_regression(
    rows: list[dict],
    req: "LandRegressionRequest",
) -> "LandRegressionResponse":
    from fastapi import HTTPException

    from app.schemas import LandRegressionCoeff, LandRegressionResponse

    min_n = max(MIN_N, int(req.min_n))
    df, warnings = _prepare_df(rows, req)
    n_prepared = len(df)
    n_shares = int(df["is_partial_ownership"].fillna(False).astype(bool).sum()) if req.variables.assessed_land_price and "is_partial_ownership" in df.columns else 0
    df, warnings = _apply_assessed_case(df, req, warnings)
    n_assessed = len(df)
    n_excluded = 0
    if req.categorical_missing == "drop":
        cat_cols: list[str] = []
        if req.variables.road_condition:
            cat_cols.append("road_condition")
        if req.variables.deal_type:
            cat_cols.append("deal_type")
        if req.variables.beopjungri_fe:
            cat_cols.append("beopjungri_name")
        df, n_excluded = drop_unknown_rows(df, cat_cols)
    n = len(df)
    if n < min_n:
        note = " ".join(w for w in warnings if w.startswith("개별공시지가"))
        detail = f"회귀 최소 표본({min_n}건) 미충족: 현재 {n}건. 필터 조건을 완화해 주세요."
        if note:
            detail = f"{detail} {note}"
        raise HTTPException(status_code=422, detail=detail)

    bundle = _build_design(df, req, warnings)
    model = sm.OLS(bundle.y_fit, bundle.X_const, missing="drop").fit()
    from app.regression_sample_judge import judge_exog, sample_notes

    verdict = judge_exog(model.model.exog)
    notes = sample_notes(verdict)
    if verdict.tier == "blocked":
        raise HTTPException(status_code=422, detail=notes[0] if notes else "계산 불가")
    for note in reversed(notes):
        bundle.warnings.insert(0, note)

    coefs: list[LandRegressionCoeff] = []
    for name in model.params.index:
        coefs.append(
            LandRegressionCoeff(
                name=str(name),
                label=_make_label(str(name)),
                coef=float(model.params[name]),
                se=float(model.bse[name]),
                t=float(model.tvalues[name]),
                p=float(model.pvalues[name]),
            )
        )

    # 산점도는 설계행렬과 동일 표본(df ∉ bundle 인덱스 정렬)
    scatter_df = df.loc[bundle.X_const.index]
    correlations = _land_correlations(scatter_df, bundle)
    partial_regressions = _land_partial_plots(bundle)

    source_frame = pd.DataFrame(rows)
    group_details = grouped_sample_details(source_frame, df.loc[model.model.data.row_labels], key="beopjungri_name",
        reference=bundle.reference_categories.get("법정동") if bundle.use_beop else None,
        effects=[name.removeprefix("beop_") for name in bundle.X_const.columns if name.startswith("beop_")])
    if req.variables.assessed_land_price:
        for group in group_details:
            raw = source_frame.loc[source_frame.beopjungri_name.fillna("미확인").astype(str) == group["key"]]
            shares = raw["is_partial_ownership"].fillna(False).astype(bool) if "is_partial_ownership" in raw else pd.Series(False, index=raw.index)
            price = pd.to_numeric(raw["official_price_won"], errors="coerce") if "official_price_won" in raw else pd.Series(np.nan, index=raw.index)
            group.update(structural_excluded_n=int(shares.sum()),
                linked_n=int(((~shares) & (price > 0)).sum()),
                unlinked_n=int(((~shares) & ~(price > 0)).sum()))
    return LandRegressionResponse(
        analysis=build_analysis_context(request=req, rows=df.loc[model.model.data.row_labels],
            sample_groups=group_details,
            reference_categories=bundle.reference_categories,
            sample_steps=[dict(label="조회 조건에 맞는 입력 거래", n=len(rows), excluded=0),
                dict(label="기본 값·이상치 필터 확인 후", n=n_prepared, excluded=len(rows)-n_prepared),
                *([dict(label="공시지가 분석: 보강 불가 지분 제외 후", n=n_prepared-n_shares, excluded=n_shares),
                    dict(label="공시지가 연결값 확인 후", n=n_assessed, excluded=n_prepared-n_shares-n_assessed)] if req.variables.assessed_land_price else []),
                dict(label="범주 결측·설계행렬 확인 후 적합", n=int(model.nobs), excluded=n_assessed-int(model.nobs))],
            coefficients=coefs, observation_unit="transaction", target="unit_price", target_unit="만원/㎡",
            response_scale=bundle.model_type, fit_n=int(model.nobs), exog=model.model.exog, source_n=len(rows)),
        n=int(model.nobs),
        model_type=bundle.model_type,  # type: ignore[arg-type]
        r_squared=float(model.rsquared),
        adj_r_squared=float(model.rsquared_adj),
        coefficients=coefs,
        reference_categories=bundle.reference_categories,
        warnings=bundle.warnings,
        f_p_value=float(model.f_pvalue),
        significant_count=sum(1 for c in coefs if c.name != "const" and c.p < 0.1),
        predict_options=_to_predict_options(bundle),
        correlations=correlations,
        partial_regressions=partial_regressions,
        correlation_n=int(len(scatter_df)),
        categorical_missing=req.categorical_missing,
        n_excluded_missing=n_excluded,
        missing_treatment_label=treatment_label(req.categorical_missing, n_excluded),
    )


def suggest_land_regression(
    rows: list[dict],
    req: "LandRegressionRequest",
) -> "LandRegressionSuggestResponse":
    """변수 블록 조합을 동일 complete-case 표본에서 비교한다."""
    from app.schemas import LandModelCandidate, LandRegressionSuggestResponse

    base, warnings = _prepare_df(rows, req)
    excluded_blocks = ["assessed_land_price"] if req.variables.assessed_land_price else []
    if excluded_blocks:
        base, warnings = _exclude_assessed_shares(base, warnings)
        warnings.append("공시지가 제외 탐색입니다. 현재 공시지가 모형과 표본이 다르므로 지표를 직접 비교할 수 없습니다.")
        req = req.model_copy(update={"variables": req.variables.model_copy(update={"assessed_land_price": False})})
    block_fields = [
        "area_sqm",
        "road_condition",
        "deal_type",
        "partial_ownership",
        "year_trend",
        "beopjungri_fe",
    ]
    enabled = [field for field in block_fields if getattr(req.variables, field, False)]
    if not enabled:
        raise ValueError("추천 후보 변수를 하나 이상 선택하세요.")

    source_columns = ["unit_price_per_sqm", "area_sqm"]
    for field in enabled:
        column = {
            "road_condition": "road_condition",
            "deal_type": "deal_type",
            "partial_ownership": "partial_ownership_label",
            "year_trend": "contract_year",
            "beopjungri_fe": "beopjungri_name",
        }.get(field)
        if column and column in base.columns:
            source_columns.append(column)
    sample = base.dropna(subset=list(dict.fromkeys(source_columns))).copy()
    selection_n = len(sample)
    results: list[LandModelCandidate] = []
    max_subsets = min((1 << len(enabled)) - 1, 64)
    for mask in range(1, max_subsets + 1):
        chosen = [enabled[i] for i in range(len(enabled)) if mask & (1 << i)]
        variables = req.variables.model_copy(
            update={field: field in chosen for field in block_fields}
        )
        candidate_req = req.model_copy(update={"variables": variables})
        try:
            bundle = _build_design(sample, candidate_req, [])
            model = sm.OLS(bundle.y_fit, bundle.X_const, missing="drop").fit()
        except Exception:
            continue
        y_price = sample.loc[bundle.X_const.index, "unit_price_per_sqm"].astype(float).to_numpy()
        fitted = np.asarray(model.fittedvalues, dtype=float)
        if bundle.model_type == "log":
            fitted = np.exp(fitted) * _duan_smearing(model.resid)
        valid = np.isfinite(y_price) & np.isfinite(fitted) & (y_price != 0)
        mape = (
            round(float(np.mean(np.abs(y_price[valid] - fitted[valid]) / np.abs(y_price[valid]))) * 100, 2)
            if valid.any()
            else None
        )
        results.append(
            LandModelCandidate(
                rank=0,
                blocks=chosen,
                variables=variables,
                model_type=bundle.model_type,  # type: ignore[arg-type]
                aic=float(model.aic),
                bic=float(model.bic),
                adj_r_squared=float(model.rsquared_adj),
                mape=mape,
                n=int(model.nobs),
            )
        )

    def ranked(key: str) -> list[LandModelCandidate]:
        valid = [candidate for candidate in results if getattr(candidate, key) is not None]
        valid.sort(key=lambda candidate: float(getattr(candidate, key)))
        return [candidate.model_copy(update={"rank": i + 1}) for i, candidate in enumerate(valid[:5])]

    return LandRegressionSuggestResponse(
        candidates_by_aic=ranked("aic"),
        candidates_by_mape=ranked("mape"),
        n=selection_n,
        selection_n=selection_n,
        warnings=warnings,
        excluded_blocks=excluded_blocks,
    )


def _back_transform(v: float, model_type: str) -> float:
    if model_type == "log":
        return float(math.exp(v))
    return float(v)


def _input_to_x_row(bundle: _DesignBundle, req: "LandRegressionPredictRequest") -> pd.DataFrame:
    from fastapi import HTTPException

    cols = list(bundle.X_const.columns)
    row: dict[str, float] = {c: 0.0 for c in cols}
    if "const" in row:
        row["const"] = 1.0

    if bundle.use_area or bundle.use_log_area:
        if req.area_sqm is None:
            raise HTTPException(status_code=400, detail="면적(area_sqm)을 입력해 주세요.")
        area = float(req.area_sqm)
        if area <= 0:
            raise HTTPException(status_code=400, detail="면적은 0보다 커야 합니다.")
        if bundle.use_log_area and "log_area" in row:
            row["log_area"] = float(np.log(max(area, 0.01)))
        if bundle.use_area and "area_sqm" in row:
            row["area_sqm"] = area

    if bundle.use_year and "year_trend" in row:
        if req.contract_year is None:
            raise HTTPException(status_code=400, detail="계약연도를 입력해 주세요.")
        row["year_trend"] = float(req.contract_year) - bundle.year_mean

    if bundle.use_road:
        road = (req.road_condition or bundle.reference_categories.get("도로조건") or "").strip()
        if not road:
            raise HTTPException(status_code=400, detail="도로조건을 선택해 주세요.")
        ref = bundle.reference_categories.get("도로조건")
        if road != ref:
            key = f"road_{road}".replace(" ", "_")
            if key not in row:
                raise HTTPException(status_code=400, detail=f"알 수 없는 도로조건: {road}")
            row[key] = 1.0

    if bundle.use_deal:
        deal = (req.deal_type or bundle.reference_categories.get("거래유형") or "").strip()
        if not deal:
            raise HTTPException(status_code=400, detail="거래유형을 선택해 주세요.")
        ref = bundle.reference_categories.get("거래유형")
        if deal != ref:
            key = f"deal_{deal}"
            if key not in row:
                raise HTTPException(status_code=400, detail=f"알 수 없는 거래유형: {deal}")
            row[key] = 1.0

    if bundle.use_partial and "partial_own" in row:
        row["partial_own"] = 1.0 if req.partial_ownership else 0.0

    if bundle.use_assessed and "log_assessed_land_price" in row:
        if req.assessed_land_price is None or float(req.assessed_land_price) <= 0:
            raise HTTPException(status_code=400, detail="개별공시지가(원/㎡)를 입력해 주세요.")
        row["log_assessed_land_price"] = float(np.log(float(req.assessed_land_price)))

    if bundle.use_beop:
        beop = (req.beopjungri_name or bundle.reference_categories.get("법정동") or "").strip()
        if not beop:
            raise HTTPException(status_code=400, detail="법정동을 선택해 주세요.")
        ref = bundle.reference_categories.get("법정동")
        if beop != ref:
            key = f"beop_{beop}"
            if key not in row:
                raise HTTPException(status_code=400, detail=f"알 수 없는 법정동: {beop}")
            row[key] = 1.0

    return pd.DataFrame([row], columns=cols)


def _extrapolation_warnings(bundle: _DesignBundle, req: "LandRegressionPredictRequest") -> list[str]:
    out: list[str] = []
    if req.area_sqm is not None:
        a = float(req.area_sqm)
        if a < bundle.area_min or a > bundle.area_max:
            out.append(
                f"면적 {a:g}㎡ 는 학습 범위({bundle.area_min:g}~{bundle.area_max:g}) 밖 — 외삽"
            )
    if req.contract_year is not None and bundle.use_year:
        y = int(req.contract_year)
        if y < bundle.year_min or y > bundle.year_max:
            out.append(
                f"연도 {y} 는 학습 범위({bundle.year_min}~{bundle.year_max}) 밖 — 외삽"
            )
    return out


def predict_land_regression(
    rows: list[dict],
    req: "LandRegressionPredictRequest",
) -> "LandRegressionPredictResponse":
    from fastapi import HTTPException

    from app.schemas import LandRegressionPredictResponse

    if req.variables.assessed_land_price and req.partial_ownership:
        raise HTTPException(status_code=400, detail="지분거래는 대장 보강이 불가능해 공시지가 모형으로 추정할 수 없습니다.")

    min_n = max(MIN_N, int(req.min_n))
    df, warnings = _prepare_df(rows, req)
    df, warnings = _apply_assessed_case(df, req, warnings)
    n = len(df)
    if n < min_n:
        raise HTTPException(
            status_code=422,
            detail=f"예측 최소 표본({min_n}건) 미충족: 현재 {n}건.",
        )

    bundle = _build_design(df, req, warnings)
    model = sm.OLS(bundle.y_fit, bundle.X_const, missing="drop").fit()
    from app.regression_sample_judge import identification_note, judge_exog, provision_note
    if getattr(req, "expected_model_signature", None) is not None:
        from app.regression_contracts import require_model_signature
        context = build_analysis_context(request={}, rows=df.loc[model.model.data.row_labels],
            coefficients=[dict(name=str(name), coef=float(value)) for name, value in model.params.items()],
            observation_unit="transaction", target="unit_price", target_unit="만원/㎡",
            response_scale=bundle.model_type, fit_n=int(model.nobs))
        require_model_signature(req.expected_model_signature, context.model_signature)

    verdict = judge_exog(model.model.exog)
    if verdict.tier == "blocked":
        raise HTTPException(status_code=422, detail="계산 불가: " + ", ".join(verdict.reasons))
    x_new = _input_to_x_row(bundle, req)
    frame = model.get_prediction(x_new).summary_frame(alpha=0.05)
    row = frame.iloc[0]

    warn = list(bundle.warnings)
    if verdict.tier == "caution":
        warn.insert(0, f"{provision_note(verdict)} · 예측구간 넓음")
    ident = identification_note(verdict)
    if ident:
        warn.insert(1 if verdict.tier == "caution" else 0, ident)
    if bundle.model_type == "log":
        warn.insert(0, "로그 모형의 원단가 평균 추정값입니다. 평균 추정범위는 역변환 보정에 따른 근사 범위입니다.")
    warn.extend(_extrapolation_warnings(bundle, req))

    smear = _duan_smearing(model.resid) if bundle.model_type == "log" else 1.0
    return LandRegressionPredictResponse(
        n=int(model.nobs),
        model_type=bundle.model_type,  # type: ignore[arg-type]
        y_hat=_back_transform(float(row["mean"]), bundle.model_type) * smear,
        pi_lower=_back_transform(float(row["obs_ci_lower"]), bundle.model_type),
        pi_upper=_back_transform(float(row["obs_ci_upper"]), bundle.model_type),
        ci_lower=_back_transform(float(row["mean_ci_lower"]), bundle.model_type) * smear,
        ci_upper=_back_transform(float(row["mean_ci_upper"]), bundle.model_type) * smear,
        log_smearing_factor=smear,
        warnings=warn,
    )


def _pick_reference_road(cats: list[str]) -> str:
    priority = ["8미만", "세로(불)", "맹지", "소로", "세로", "세로(가)", "25미만", "25이상"]
    for p in priority:
        if p in cats:
            return p
    return cats[0]


def _make_label(name: str) -> str:
    if name in _COEF_LABELS:
        return _COEF_LABELS[name]
    if name.startswith("road_"):
        return f"도로:{name[5:].replace('_', ' ')}"
    if name.startswith("deal_"):
        return f"유형:{name[5:].replace('_', ' ')}"
    if name.startswith("beop_"):
        return f"지역:{name[5:].replace('_', ' ')}"
    if name == "partial_own":
        return "지분거래"
    return name
