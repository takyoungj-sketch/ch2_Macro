"""토지 단가 헤도닉 OLS 회귀 엔진.

입력: _fetch_matrix_cell_filtered_transactions 결과(list[dict])
출력: LandRegressionResponse
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import statsmodels.api as sm

if TYPE_CHECKING:
    from app.schemas import LandRegressionRequest, LandRegressionResponse

MIN_N = 10  # 절대 최소 (요청 min_n보다 우선 낮게 설정 불가)

# 사람이 읽기 좋은 변수 라벨
_COEF_LABELS: dict[str, str] = {
    "const": "상수(기준)",
    "log_area": "log(면적)",
    "area_sqm": "면적(㎡)",
    "year_trend": "연도 추세",
}


def _road_label(v: str) -> str:
    return f"도로:{v}"


def _deal_label(v: str) -> str:
    return f"유형:{v}"


def _beop_label(v: str) -> str:
    return f"지역:{v}"


def run_land_regression(
    rows: list[dict],
    req: "LandRegressionRequest",
) -> "LandRegressionResponse":
    from app.schemas import LandRegressionCoeff, LandRegressionResponse

    warnings: list[str] = []
    min_n = max(MIN_N, int(req.min_n))

    # ── 데이터프레임 생성 ──────────────────────────────────────────────
    df = pd.DataFrame(rows)
    df = df.dropna(subset=["unit_price_per_sqm", "area_sqm"])
    df["unit_price_per_sqm"] = df["unit_price_per_sqm"].astype(float)
    df["area_sqm"] = df["area_sqm"].astype(float)
    df["contract_year"] = df["contract_year"].astype(int)

    # IQR 이상치 제거 (요청 옵션)
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

    n = len(df)
    if n < min_n:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=422,
            detail=f"회귀 최소 표본({min_n}건) 미충족: 현재 {n}건. 필터 조건을 완화해 주세요.",
        )

    # ── 종속변수 ──────────────────────────────────────────────────────
    y = df["unit_price_per_sqm"].copy()
    model_type = req.model_type
    if model_type == "log" and (y <= 0).any():
        model_type = "linear"
        warnings.append("단가 ≤ 0인 행이 있어 선형 모델로 전환했습니다.")
    y_fit = np.log(y) if model_type == "log" else y

    # ── 설계행렬 구성 ─────────────────────────────────────────────────
    X_parts: list[pd.DataFrame] = []
    reference_categories: dict[str, str] = {}
    v = req.variables

    # 면적 (연속)
    if v.area_sqm:
        if v.log_area:
            log_a = np.log(df["area_sqm"].clip(lower=0.01))
            X_parts.append(log_a.rename("log_area").to_frame())
        else:
            X_parts.append(df[["area_sqm"]].copy())

    # 연도 추세 (선형)
    if v.year_trend:
        yr_centered = (df["contract_year"] - df["contract_year"].mean()).rename("year_trend")
        X_parts.append(yr_centered.to_frame())

    # 도로조건 더미
    if v.road_condition:
        col = df["road_condition"].fillna("미상").astype(str).str.strip()
        cats = sorted(col.unique())
        if len(cats) >= 2:
            ref = _pick_reference_road(cats)
            reference_categories["도로조건"] = ref
            dummies = pd.get_dummies(col, prefix="road", drop_first=False)
            ref_col = f"road_{ref}"
            dummies = dummies.drop(columns=[ref_col], errors="ignore")
            dummies.columns = [c.replace(" ", "_") for c in dummies.columns]
            X_parts.append(dummies.astype(float))
        else:
            warnings.append("도로조건 범주가 1개 이하 — 더미 제외")

    # 유형 더미 (직거래/중개거래)
    if v.deal_type:
        col = df["deal_type"].fillna("중개거래").astype(str).str.strip()
        cats = sorted(col.unique())
        if len(cats) >= 2:
            ref = "중개거래" if "중개거래" in cats else cats[0]
            reference_categories["거래유형"] = ref
            dummies = pd.get_dummies(col, prefix="deal", drop_first=False)
            ref_col = f"deal_{ref}"
            dummies = dummies.drop(columns=[ref_col], errors="ignore")
            X_parts.append(dummies.astype(float))
        else:
            warnings.append("거래유형 범주가 1개 이하 — 더미 제외")

    # 지분 더미
    if v.partial_ownership:
        col = df["partial_ownership_label"].fillna("").astype(str).str.strip()
        has_partial = col.str.len() > 0
        if has_partial.sum() > 0 and (~has_partial).sum() > 0:
            X_parts.append(has_partial.astype(float).rename("partial_own").to_frame())
        else:
            warnings.append("지분 여부 단일값 — 더미 제외")

    # 법정동 고정효과 (복수 법정동 시)
    if v.beopjungri_fe:
        col = df["beopjungri_name"].fillna("미상").astype(str).str.strip()
        n_beop = col.nunique()
        if n_beop >= 2:
            ref = col.value_counts().idxmax()
            reference_categories["법정동"] = ref
            dummies = pd.get_dummies(col, prefix="beop", drop_first=False)
            ref_col = f"beop_{ref}"
            dummies = dummies.drop(columns=[ref_col], errors="ignore")
            # n < 3 법정동 제외
            small = [c for c in dummies.columns if dummies[c].sum() < 3]
            if small:
                dummies = dummies.drop(columns=small)
                warnings.append(f"법정동 FE: {len(small)}개 소수집단 제외")
            if not dummies.empty:
                X_parts.append(dummies.astype(float))
        else:
            warnings.append("법정동이 1개 — FE 제외")

    if not X_parts:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="투입 변수가 없습니다. 하나 이상의 변수를 선택하세요.")

    X = pd.concat(X_parts, axis=1)

    # 완전분리·상수열 제거
    X = X.loc[:, X.nunique() > 1]

    # ── OLS 적합 ─────────────────────────────────────────────────────
    X_const = sm.add_constant(X, has_constant="add")
    aligned_y = y_fit.loc[X_const.index]
    model = sm.OLS(aligned_y, X_const, missing="drop").fit()

    # ── 계수 추출 ─────────────────────────────────────────────────────
    coefs: list[LandRegressionCoeff] = []
    for name in model.params.index:
        label = _make_label(name)
        coefs.append(
            LandRegressionCoeff(
                name=str(name),
                label=label,
                coef=float(model.params[name]),
                se=float(model.bse[name]),
                t=float(model.tvalues[name]),
                p=float(model.pvalues[name]),
            )
        )

    return LandRegressionResponse(
        n=int(model.nobs),
        model_type=model_type,
        r_squared=float(model.rsquared),
        adj_r_squared=float(model.rsquared_adj),
        coefficients=coefs,
        reference_categories=reference_categories,
        warnings=warnings,
    )


def _pick_reference_road(cats: list[str]) -> str:
    """도로조건 기준 범주: '8미만' 또는 '세로(불)' 등 가장 낮은 등급 우선."""
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
