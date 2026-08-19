"""트랙 A 실험 번들 — M2 기준식, 학습 셀, 구/연도 hold-out, APE 태깅."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.collective.new_apt.constants import (
    APE_OUTLIER_PCT,
    COMMERCIAL_ZONES,
    DAEJEON_SIGUNGU,
    LAND_THIN_N,
)
from app.collective.new_apt.error_audit import audit_m2_errors
from app.collective.new_apt.models import (
    fit_spec,
    fit_wls,
    holdout_buildings,
    land_dispersion,
    m2_complete,
    predict_unit_price,
    prepare_track_a,
    run_comparison,
)


def land_join_summary(df: pd.DataFrame) -> dict[str, Any]:
    n = int(len(df))
    land = df["land_p50"].notna() if "land_p50" in df.columns else pd.Series(False, index=df.index)
    res = df["zone_resolution"].fillna("missing").astype(str) if "zone_resolution" in df.columns else pd.Series(
        "missing", index=df.index
    )
    thin = pd.Series(False, index=df.index)
    if "land_n" in df.columns:
        thin = land & (df["land_n"].fillna(0).astype(float) < LAND_THIN_N)
    return {
        "n_cells": n,
        "n_buildings": int(df["building_key"].nunique()) if n else 0,
        "n_land": int(land.sum()),
        "land_join_pct": round(float(land.mean() * 100), 1) if n else 0.0,
        "n_missing_land": int((~land).sum()),
        "n_thin_land": int(thin.sum()),
        "zone_resolution": {str(k): int(v) for k, v in res.value_counts().items()},
        "note": "토지 P50은 필지 실거래가 아니라 읍×용도지역×대 5년 중앙값",
    }


def _iqr_outlier(s: pd.Series) -> pd.Series:
    q1 = s.quantile(0.25)
    q3 = s.quantile(0.75)
    iqr = q3 - q1
    if not np.isfinite(iqr) or iqr == 0:
        return pd.Series(False, index=s.index)
    return (s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)


def leave_one_group_out(
    df: pd.DataFrame,
    *,
    group_col: str,
    min_hold: int = 10,
    min_train: int = 80,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if df.empty or group_col not in df.columns:
        return rows
    work = df.copy()
    work["_g"] = work[group_col].astype(str)
    for g, hold in work.groupby("_g"):
        train = work[work["_g"] != g]
        if len(train) < min_train or len(hold) < min_hold:
            rows.append(
                {
                    "group": str(g),
                    "n_train": int(len(train)),
                    "n_hold": int(len(hold)),
                    "n_hold_buildings": int(hold["building_key"].nunique()),
                    "mae": None,
                    "mape": None,
                    "land_coef": None,
                    "skipped": True,
                    "reason": "표본 부족",
                }
            )
            continue
        hold_fit = hold
        if group_col == "calendar_year":
            train_years = sorted(train["calendar_year"].astype(int).unique())
            hold_fit = hold.copy()
            hold_fit["calendar_year"] = hold_fit["calendar_year"].astype(int).map(
                lambda y: min(train_years, key=lambda t: abs(int(t) - int(y)))
            )
        fitted = fit_spec(train, hold_fit, product="M2", location="land", track="val")
        rows.append(
            {
                "group": str(g),
                "n_train": fitted["n_train"],
                "n_hold": fitted["n_holdout"],
                "n_hold_buildings": int(hold["building_key"].nunique()),
                "mae": fitted["holdout_mae"],
                "mape": fitted["holdout_mape"],
                "land_coef": fitted["land_coef"],
                "skipped": bool(fitted["warnings"]),
                "reason": "; ".join(fitted["warnings"]) if fitted["warnings"] else None,
            }
        )
    rows.sort(key=lambda r: (r["mape"] is None, -(r["mape"] or 0)))
    return rows


def _cell_records(
    work: pd.DataFrame,
    *,
    yhat: pd.Series,
    hold_keys: set[str],
    m2_ok: pd.Series,
) -> list[dict[str, Any]]:
    y = work["y_median_unit_price"].astype(float)
    outlier_y = _iqr_outlier(y[m2_ok])
    records: list[dict[str, Any]] = []
    for idx, row in work.iterrows():
        pred = float(yhat[idx]) if idx in yhat.index else None
        actual = float(row["y_median_unit_price"]) if pd.notna(row["y_median_unit_price"]) else None
        resid = (actual - pred) if actual is not None and pred is not None else None
        ape = (abs(resid) / actual * 100) if resid is not None and actual else None
        land = row["land_p50"] if pd.notna(row.get("land_p50")) else None
        records.append(
            {
                "building_key": str(row["building_key"]),
                "calendar_year": int(row["calendar_year"]) if pd.notna(row["calendar_year"]) else None,
                "sigungu_code": str(row["sigungu_code"]) if pd.notna(row.get("sigungu_code")) else None,
                "y": round(actual, 2) if actual is not None else None,
                "yhat": round(pred, 2) if pred is not None else None,
                "residual": round(resid, 2) if resid is not None else None,
                "ape": round(ape, 1) if ape is not None else None,
                "land_p50": round(float(land), 1) if land is not None else None,
                "land_n": int(row["land_n"]) if pd.notna(row.get("land_n")) else None,
                "zone_compact": row.get("zone_compact") if pd.notna(row.get("zone_compact")) else None,
                "zone_resolution": str(row.get("zone_resolution") or "missing"),
                "uqa_label": row.get("uqa_label") if pd.notna(row.get("uqa_label")) else None,
                "households": int(row["households"]) if pd.notna(row.get("households")) else None,
                "max_floor": int(row["max_floor"]) if pd.notna(row.get("max_floor")) else None,
                "parking_per_household": round(float(row["parking_per_household"]), 3)
                if pd.notna(row.get("parking_per_household"))
                else None,
                "vintage": row.get("vintage") if pd.notna(row.get("vintage")) else None,
                "age": int(row["age"]) if pd.notna(row.get("age")) else None,
                "n_tx": int(row["n_tx"]) if pd.notna(row.get("n_tx")) else None,
                "builder_group": row.get("builder_group") if pd.notna(row.get("builder_group")) else None,
                "brand": row.get("brand") if pd.notna(row.get("brand")) else None,
                "danji_class": row.get("danji_class") if pd.notna(row.get("danji_class")) else None,
                "attr_quality_flags": row.get("attr_quality_flags")
                if pd.notna(row.get("attr_quality_flags"))
                else None,
                "in_holdout": str(row["building_key"]) in hold_keys,
                "in_m2": bool(m2_ok.loc[idx]),
                "outlier_y": bool(idx in outlier_y.index and outlier_y.loc[idx]),
                "outlier_ape": bool(ape is not None and ape >= APE_OUTLIER_PCT),
            }
        )
    records.sort(key=lambda r: (-(r["ape"] or -1), str(r["building_key"]), r["calendar_year"] or 0))
    return records


def data_fix_sensitivity(
    work: pd.DataFrame,
    hold_keys: set[str],
    baseline_mape: float | None,
) -> dict[str, Any]:
    """상업지역·얇은 토지 셀을 뺀 M2 — 본체는 바꾸지 않고 hold-out만 비교."""
    zone = work["zone_compact"].astype(str) if "zone_compact" in work.columns else pd.Series("", index=work.index)
    commercial = zone.isin(COMMERCIAL_ZONES)
    thin = work["land_n"].fillna(0).astype(float) < LAND_THIN_N if "land_n" in work.columns else False
    ok = m2_complete(work) & ~commercial & ~thin
    train = work[~work["building_key"].astype(str).isin(hold_keys) & ok]
    hold = work[work["building_key"].astype(str).isin(hold_keys) & ok]
    fitted = fit_spec(train, hold, product="M2", location="land", track="data_fix")
    mape = fitted.get("holdout_mape")
    delta = None
    if mape is not None and baseline_mape is not None:
        delta = round(float(mape) - float(baseline_mape), 2)
    return {
        "label": "상업지역·얇은 토지 셀 제외 후 M2",
        "n_train": fitted.get("n_train"),
        "n_dropped": int((m2_complete(work) & (commercial | thin)).sum()),
        "n_holdout": fitted.get("n_holdout"),
        "adj_r_squared": fitted.get("adj_r_squared"),
        "holdout_mape": mape,
        "holdout_mae": fitted.get("holdout_mae"),
        "baseline_holdout_mape": baseline_mape,
        "delta_mape": delta,
        "replaces_baseline": False,
        "note": "M2 본체는 유지. 음수 delta는 정제 표본이 hold-out을 개선했다는 뜻.",
    }


def run_experiment(df: pd.DataFrame) -> dict[str, Any]:
    work = prepare_track_a(df)
    comparison = run_comparison(df)
    hold_keys = holdout_buildings(work)
    m2_ok = m2_complete(work)
    train = work[~work["building_key"].astype(str).isin(hold_keys) & m2_ok]
    hold_new = work[work["building_key"].astype(str).isin(hold_keys) & m2_ok]
    model = fit_wls(train, product="M2", location="land")
    yhat = predict_unit_price(model, work[m2_ok], product="M2", location="land") if model is not None else pd.Series(
        dtype=float
    )

    m2_row = next((r for r in comparison["table"] if r.get("is_baseline")), None)
    if m2_row is None:
        m2_row = fit_spec(train, hold_new, product="M2", location="land", track="main")
        m2_row["is_baseline"] = True
        m2_row["sample"] = "A-1-land"

    m2_df = work[m2_ok]
    gu_rows = leave_one_group_out(m2_df, group_col="sigungu_code")
    for row in gu_rows:
        row["label"] = DAEJEON_SIGUNGU.get(row["group"], row["group"])
    year_rows = leave_one_group_out(m2_df, group_col="calendar_year")
    for row in year_rows:
        row["label"] = row["group"]

    latest_year = None
    if not m2_df.empty:
        ly = int(m2_df["calendar_year"].astype(int).max())
        latest_year = next((r for r in year_rows if r["group"] == str(ly)), None)

    pooled_mape = None
    measured = [r for r in gu_rows if r.get("mape") is not None]
    if measured:
        weights = [max(r["n_hold"] or 0, 1) for r in measured]
        pooled_mape = round(float(np.average([r["mape"] for r in measured], weights=weights)), 2)

    cells = _cell_records(work, yhat=yhat, hold_keys=hold_keys, m2_ok=m2_ok)
    cells, error_audit = audit_m2_errors(cells)
    error_audit["data_fix_sensitivity"] = data_fix_sensitivity(work, hold_keys, m2_row.get("holdout_mape"))
    n_outlier_y = sum(1 for c in cells if c["outlier_y"])
    n_outlier_ape = sum(1 for c in cells if c["outlier_ape"])

    return {
        "sido_code": str(work["sido_code"].iloc[0]) if not work.empty else None,
        "baseline": "M2",
        "baseline_role": "대전 잠정 기준식(연도+토지+상품). 충북 검증 전 최종 확정 아님. M3는 시공사 탐색만",
        "land_join": land_join_summary(work),
        "land_dispersion": land_dispersion(work[work["land_p50"].notna()]),
        "comparison": comparison,
        "m2": m2_row,
        "cells": cells,
        "error_audit": error_audit,
        "cell_summary": {
            "n_cells": len(cells),
            "n_m2": int(m2_ok.sum()),
            "n_holdout_cells": sum(1 for c in cells if c["in_holdout"] and c["in_m2"]),
            "n_outlier_y": n_outlier_y,
            "n_outlier_ape": n_outlier_ape,
            "ape_outlier_threshold": APE_OUTLIER_PCT,
        },
        "validation": {
            "random_new_buildings": {
                "label": "준공 0~5년 단지 20% 랜덤",
                "mae": m2_row.get("holdout_mae"),
                "mape": m2_row.get("holdout_mape"),
                "n_hold": m2_row.get("n_holdout"),
                "n_hold_buildings": comparison.get("n_holdout_buildings"),
            },
            "leave_one_gu": gu_rows,
            "leave_one_gu_pooled_mape": pooled_mape,
            "leave_one_year": year_rows,
            "latest_year": latest_year,
            "year_holdout_note": "빠진 연도의 시장더미는 가장 가까운 학습 연도로 대체한다",
        },
        "notes": [
            "M2는 대전 잠정 기준식이다. 충북 복제·전이 실험 전에는 최종으로 확정하지 않는다.",
            "토지 P50은 시 전체 입지 수준을 잡는 변수이지, 동 내부 단지 차이를 맞히는 변수가 아니다.",
            "점추정만으로 분양가를 단정하지 않는다. 식·계수·n·경고·hold-out을 같이 본다.",
            "기존 건물 「회귀 분석」 탭(거래 단위 OLS)과 숫자가 다르다.",
            "오차는 단지 단위로 묶어 태깅한다. 반복(≥5단지)만 다음 변수 후보다.",
            "시공사·M4는 충북 확장 다음이다. 지금 식을 키우지 않는다.",
        ],
    }
