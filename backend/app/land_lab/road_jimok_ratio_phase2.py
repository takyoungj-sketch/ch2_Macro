"""도로 지목 2차 — 연도별 중앙값 비, 읍면동×용도 안 회귀.

연도별 r은 1차와 같은 비다. 그 해의 거래만 쓰고, 양쪽 건수 컷도 그 해에 적용한다.
회귀는 같은 읍면동·용도 안에서 log 단가 ~ 도로 지목 + log 면적 + 도로조건 + 계약 연도.
지목 계수의 배수는 1차 칸 중앙값 비와 다른 숫자다.

네 분포는 나누어 추정한다. 개발제한구역은 넣지 않는다.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from typing import Any, Iterable

import numpy as np
import pandas as pd
import statsmodels.api as sm

from app.land_lab.road_jimok_ratio import (
    BANDS,
    PRIMARY_MIN_N,
    ROAD,
    SENSITIVITY_MIN_N,
    build_screen,
    canonical_jimok,
    canonical_zone,
    zone_class,
)
from app.land_regression import _pick_reference_road


def _year_partial(year: int, period_start: str, period_end: str) -> bool:
    start = date.fromisoformat(period_start)
    end = date.fromisoformat(period_end)
    return date(year, 1, 1) < start or date(year, 12, 31) > end


def build_yearly(
    aggs: Iterable[dict[str, Any]],
    *,
    as_of_month: str,
    period_start: str,
    period_end: str,
    window_years: int = 5,
) -> list[dict[str, Any]]:
    """연도별 집계 행으로 네 분포의 25%·중앙·75%를 만든다. 칸 목록은 넣지 않는다."""
    by_year: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in aggs:
        raw = row.get("contract_year")
        if raw is None or str(raw).strip() == "":
            continue
        by_year[int(raw)].append(row)
    out: list[dict[str, Any]] = []
    for year in sorted(by_year):
        screen = build_screen(
            by_year[year],
            as_of_month=as_of_month,
            period_start=period_start,
            period_end=period_end,
            window_years=window_years,
        )
        out.append(
            {
                "year": year,
                "partial": _year_partial(year, period_start, period_end),
                "bands": [
                    {"id": b["id"], "title": b["title"], "cuts": b["cuts"]}
                    for b in screen["bands"]
                ],
            }
        )
    return out


def _as_frame(rows: Iterable[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    if isinstance(rows, pd.DataFrame):
        df = rows.copy()
    else:
        df = pd.DataFrame(list(rows))
    if df.empty:
        return df
    df["eup_code"] = df["eup_code"].astype(str).str.strip()
    df["zone"] = df["zone_type"].map(lambda v: canonical_zone(str(v)))
    df["jimok"] = df["land_category"].map(lambda v: canonical_jimok(str(v)))
    df["year"] = pd.to_numeric(df["contract_year"], errors="coerce")
    df["area"] = pd.to_numeric(df["area_sqm"], errors="coerce")
    df["price"] = pd.to_numeric(df["unit_price_per_sqm"], errors="coerce")
    road = df["road_condition"] if "road_condition" in df.columns else ""
    df["road"] = road.fillna("미상").astype(str).str.strip().replace({"": "미상"})
    df["klass"] = df["zone"].map(zone_class)
    df = df.dropna(subset=["year", "area", "price"])
    df = df[(df["area"] > 0) & (df["price"] > 0) & (df["eup_code"] != "")]
    df["year"] = df["year"].astype(int)
    return df


def _fit_one(df: pd.DataFrame) -> dict[str, Any]:
    """읍면동×용도 고정. 표준오차는 그 칸으로 군집."""
    work = df.copy()
    work["is_road"] = (work["jimok"] == ROAD).astype(float)
    work["log_price"] = np.log(work["price"].astype(float))
    work["log_area"] = np.log(work["area"].astype(float).clip(lower=0.01))
    work["cell"] = work["eup_code"] + "|" + work["zone"]

    x_cols = ["is_road", "log_area"]
    pieces = [work[["is_road", "log_area"]]]

    year_ref = str(int(work["year"].value_counts().idxmax()))
    year_dum = pd.get_dummies(work["year"].astype(int).astype(str), prefix="year")
    year_keep = [c for c in year_dum.columns if c != f"year_{year_ref}"]
    if year_keep:
        pieces.append(year_dum[year_keep].astype(float))
        x_cols.extend(year_keep)

    road_ref = None
    road_dum, road_ref = _road_dummies(work["road"])
    if not road_dum.empty:
        pieces.append(road_dum.astype(float))
        x_cols.extend(list(road_dum.columns))

    x = pd.concat(pieces, axis=1)
    y = work["log_price"]
    cell = work["cell"]
    means_x = x.groupby(cell).transform("mean")
    y_d = y - y.groupby(cell).transform("mean")
    x_d = x - means_x
    keep = [c for c in x_d.columns if float(x_d[c].std(ddof=0) or 0) > 1e-8]
    x_d = x_d[keep]
    if "is_road" not in x_d.columns or x_d.shape[0] < 30:
        return {"error": "칸 안 도로 지목 대비가 식별되지 않음"}

    n_cells = int(cell.nunique())
    try:
        if n_cells > x_d.shape[1] + 1:
            res = sm.OLS(y_d, x_d).fit(
                cov_type="cluster",
                cov_kwds={"groups": cell},
            )
            se_type = "cluster_cell"
        else:
            res = sm.OLS(y_d, x_d).fit(cov_type="HC1")
            se_type = "HC1"
    except Exception as exc:
        return {"error": str(exc)}

    beta = float(res.params["is_road"])
    se = float(res.bse["is_road"])
    p = float(res.pvalues["is_road"])
    area_beta = float(res.params["log_area"]) if "log_area" in res.params.index else None
    area_se = float(res.bse["log_area"]) if "log_area" in res.bse.index else None
    n_road = int((work["jimok"] == ROAD).sum())
    n_base = int((work["jimok"] != ROAD).sum())
    return {
        "n_cells": n_cells,
        "n_trades": int(len(work)),
        "n_road": n_road,
        "n_base": n_base,
        "beta": round(beta, 4),
        "se": round(se, 4),
        "p": round(p, 6),
        "factor": round(math.exp(beta), 4),
        "log_area": None if area_beta is None else round(area_beta, 4),
        "log_area_se": None if area_se is None else round(area_se, 4),
        "year_ref": year_ref,
        "road_ref": road_ref,
        "r2": round(float(res.rsquared), 4),
        "se_type": se_type,
        "error": None,
    }


def _road_dummies(series: pd.Series) -> tuple[pd.DataFrame, str | None]:
    col = series.fillna("미상").astype(str).str.strip()
    cats = sorted(col.unique())
    if len(cats) < 2:
        return pd.DataFrame(index=series.index), None
    ref = _pick_reference_road(cats)
    dummies = pd.get_dummies(col, prefix="roadc", drop_first=False).astype(float)
    dummies = dummies.drop(columns=[f"roadc_{ref}"], errors="ignore")
    dummies.columns = [c.replace(" ", "_") for c in dummies.columns]
    return dummies, ref


def _empty_cut() -> dict[str, Any]:
    return {
        "n_cells": 0,
        "n_trades": 0,
        "n_road": 0,
        "n_base": 0,
        "beta": None,
        "se": None,
        "p": None,
        "factor": None,
        "log_area": None,
        "log_area_se": None,
        "year_ref": None,
        "road_ref": None,
        "r2": None,
        "se_type": None,
        "error": "통과 칸 없음",
    }


def fit_regressions(
    rows: Iterable[dict[str, Any]] | pd.DataFrame,
    *,
    cuts: tuple[int, ...] = SENSITIVITY_MIN_N,
) -> dict[str, Any]:
    """네 분포를 따로 맞춘다. 컷은 그 창에서 양쪽 건수."""
    df = _as_frame(rows)
    df = df[df["klass"].isin(["urban", "nonurban"])]
    bands_out = []
    for bid, title, klass, base in BANDS:
        pool = df[(df["klass"] == klass) & (df["jimok"].isin([ROAD, base]))]
        cuts_out: dict[str, Any] = {}
        for cut in cuts:
            if pool.empty:
                cuts_out[str(cut)] = _empty_cut()
                continue
            counts = pool.groupby(["eup_code", "zone", "jimok"]).size().unstack(fill_value=0)
            if ROAD not in counts.columns or base not in counts.columns:
                cuts_out[str(cut)] = _empty_cut()
                continue
            keep = counts.index[(counts[ROAD] >= cut) & (counts[base] >= cut)]
            if len(keep) == 0:
                cuts_out[str(cut)] = _empty_cut()
                continue
            keyed = pool.set_index(["eup_code", "zone"])
            sub = keyed.loc[keyed.index.isin(keep)].reset_index()
            fitted = _fit_one(sub)
            if fitted.get("error"):
                cuts_out[str(cut)] = {**_empty_cut(), "error": fitted["error"]}
            else:
                cuts_out[str(cut)] = fitted
        bands_out.append({"id": bid, "title": title, "base_jimok": base, "cuts": cuts_out})
    return {
        "formula": "log 단가 ~ 도로 지목 + log 면적 + 도로조건 + 계약 연도",
        "fixed": "읍면동 × 용도지역",
        "se": "읍면동×용도 군집",
        "primary_min_n": PRIMARY_MIN_N,
        "note": "통제 후 배수는 같은 칸에서 면적·접면·연도를 맞춘 거래 한 건의 배수다. 1차 중앙값 비와 다른 숫자다.",
        "bands": bands_out,
    }
