"""MAPE 분해 — 복합부동산 회귀 (CH2 engine과 동일 역변환·IQR).

Usage (ch2_Macro 루트):
  py pipeline/built/verify_mape_decomposition.py ^
    --addr1 서울특별시 --addr2 강북구 --addr4-list 비산동 ^
    --asset-type commercial --scale log --iqr ^
    --blocks gross_area,land_area,building_age,road_width,zone_type,building_use

  # 두 모형 공정 비교 (동일 적합 행)
  py pipeline/built/verify_mape_decomposition.py ... ^
    --compare-blocks gross_area,land_area,building_age,road_width
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm

_MACRO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_MACRO / "backend"))
sys.path.insert(0, str(_MACRO / "pipeline" / "built"))

from app.built.asset_scope import is_unified
from app.built.regression.engine import (  # noqa: E402
    _build_design_matrix,
    _duan_smearing,
    _fit_ols,
    _focus_admin_level,
    _insample_mape_pct,
    _prepare_regression_scope,
    _scope_for_level,
)
from app.built.regression.selection.blocks import spec_from_blocks
from app.built.schemas import RegressionRunRequest, RegressionVariableSpec, ResponseScale
from db_utils import get_built_engine

ALL_BLOCK_IDS = (
    "gross_area",
    "land_area",
    "building_age",
    "road_width",
    "zone_type",
    "building_use",
    "asset_type",
    "region_leaf",
)


@dataclass
class QuantileBin:
    label: str
    n: int
    mape_pct: float | None
    median_price: float | None
    share_of_total_abs_error: float | None


@dataclass
class MapeDecomposition:
    label: str
    response_scale: str
    n_fit: int
    n_common: int | None
    adj_r_squared_log: float | None
    mape_overall_pct: float | None
    mape_common_pct: float | None
    rmse_won: float | None
    price_min: float | None
    price_p10: float | None
    price_median: float | None
    price_p90: float | None
    price_max: float | None
    n_price_le_3000: int
    n_price_le_5000: int
    by_quantile: list[QuantileBin]
    top_worst: list[dict[str, Any]]
    engine_mape_pct: float | None


def _parse_list(raw: str) -> list[str]:
    if not raw:
        return []
    return [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]


def _parse_blocks(raw: str | None) -> list[str]:
    return _parse_list(raw or "")


def _blocks_to_spec(blocks: list[str]) -> RegressionVariableSpec:
    return spec_from_blocks(blocks)


def _price_predictions(
    y_price: np.ndarray,
    model,
    *,
    response_scale: ResponseScale,
) -> np.ndarray:
    fitted = np.asarray(model.fittedvalues, dtype=float)
    if response_scale == "log":
        return np.exp(fitted) * _duan_smearing(model.resid.to_numpy())
    return fitted


def _fit_on_index(
    df: pd.DataFrame,
    spec: RegressionVariableSpec,
    *,
    unified: bool,
    response_scale: ResponseScale,
    region_col: str | None,
    index: pd.Index,
) -> tuple[object, np.ndarray, np.ndarray] | None:
    sub = df.loc[index]
    y, X, _ = _build_design_matrix(
        sub,
        spec,
        unified=unified,
        response_scale=response_scale,
        region_col=region_col,
    )
    if len(y) < 5 or X.empty:
        return None
    x_const = sm.add_constant(X.astype(float), has_constant="add")
    model = sm.OLS(y.astype(float), x_const).fit()
    y_price = pd.to_numeric(sub["price"], errors="coerce").loc[y.index].astype(float).to_numpy()
    pred = _price_predictions(y_price, model, response_scale=response_scale)
    return model, y_price, pred


def _design_index(
    df: pd.DataFrame,
    spec: RegressionVariableSpec,
    *,
    unified: bool,
    response_scale: ResponseScale,
    region_col: str | None,
) -> pd.Index:
    y, X, _ = _build_design_matrix(
        df,
        spec,
        unified=unified,
        response_scale=response_scale,
        region_col=region_col,
    )
    return y.index


def _pct_errors(y: np.ndarray, pred: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mask = np.isfinite(y) & np.isfinite(pred) & (y != 0)
    err_pct = np.full(len(y), np.nan, dtype=float)
    err_pct[mask] = np.abs(y[mask] - pred[mask]) / np.abs(y[mask]) * 100
    return err_pct, mask


def _mape_from_errors(err_pct: np.ndarray, mask: np.ndarray) -> float | None:
    if not mask.any():
        return None
    return round(float(np.nanmean(err_pct[mask])), 2)


def decompose_mape(
    y_price: np.ndarray,
    pred: np.ndarray,
    *,
    label: str,
    response_scale: ResponseScale,
    model,
    n_common: int | None = None,
    mape_common: float | None = None,
) -> MapeDecomposition:
    err_pct, mask = _pct_errors(y_price, pred)
    y = y_price[mask]
    p = pred[mask]
    overall = _mape_from_errors(err_pct, mask)

    abs_err = np.abs(y - p)
    total_abs = float(abs_err.sum()) if len(abs_err) else 0.0

    qs = [0.1, 0.25, 0.5, 0.75, 0.9]
    quantiles = np.quantile(y, qs) if len(y) else [np.nan] * len(qs)

    bins: list[QuantileBin] = []
    edges = [-np.inf, quantiles[0], quantiles[1], quantiles[2], quantiles[3], quantiles[4], np.inf]
    bin_labels = [
        f"하위 ~p10 (<={quantiles[0]:,.0f})",
        "p10-p25",
        "p25-p50",
        "p50-p75",
        "p75-p90",
        f"상위 p90+ (>{quantiles[4]:,.0f})",
    ]
    for i in range(6):
        lo, hi = edges[i], edges[i + 1]
        if i == 0:
            bmask = mask & (y_price <= hi)
        elif i == 5:
            bmask = mask & (y_price > lo)
        else:
            bmask = mask & (y_price > lo) & (y_price <= hi)
        bn = int(bmask.sum())
        if bn == 0:
            bins.append(QuantileBin(bin_labels[i], 0, None, None, None))
            continue
        bm = _mape_from_errors(err_pct, bmask)
        med = float(np.median(y_price[bmask]))
        share = float(np.nansum(np.abs(y_price[bmask] - pred[bmask])) / total_abs * 100) if total_abs else None
        bins.append(QuantileBin(bin_labels[i], bn, bm, med, round(share, 1) if share is not None else None))

    # 저가 건수는 overall mask 기준
    worst_idx = np.argsort(-np.nan_to_num(err_pct, nan=-1.0))
    top_worst: list[dict[str, Any]] = []
    for i in worst_idx[:8]:
        if not mask[i]:
            continue
        top_worst.append(
            {
                "price": round(float(y_price[i]), 0),
                "predicted": round(float(pred[i]), 0),
                "pct_error": round(float(err_pct[i]), 1),
                "abs_error": round(float(abs(y_price[i] - pred[i])), 0),
            }
        )

    rmse = round(float(np.sqrt(np.mean((y - p) ** 2))), 1) if len(y) else None
    engine_mape = _insample_mape_pct(y_price, model, response_scale=response_scale)

    return MapeDecomposition(
        label=label,
        response_scale=response_scale,
        n_fit=int(mask.sum()),
        n_common=n_common,
        adj_r_squared_log=float(model.rsquared_adj) if model.rsquared_adj is not None else None,
        mape_overall_pct=overall,
        mape_common_pct=mape_common,
        rmse_won=rmse,
        price_min=round(float(y.min()), 0) if len(y) else None,
        price_p10=round(float(quantiles[0]), 0) if len(y) else None,
        price_median=round(float(quantiles[2]), 0) if len(y) else None,
        price_p90=round(float(quantiles[4]), 0) if len(y) else None,
        price_max=round(float(y.max()), 0) if len(y) else None,
        n_price_le_3000=int((mask & (y_price <= 3000)).sum()),
        n_price_le_5000=int((mask & (y_price <= 5000)).sum()),
        by_quantile=bins,
        top_worst=top_worst,
        engine_mape_pct=engine_mape,
    )


def analyze_model(
    df: pd.DataFrame,
    blocks: list[str],
    *,
    label: str,
    unified: bool,
    response_scale: ResponseScale,
    region_col: str | None,
    common_index: pd.Index | None = None,
) -> MapeDecomposition | None:
    spec = _blocks_to_spec(blocks)
    if common_index is not None and len(common_index):
        fit = _fit_on_index(
            df,
            spec,
            unified=unified,
            response_scale=response_scale,
            region_col=region_col,
            index=common_index,
        )
        if fit is None:
            return None
        model, y_price, pred = fit
        err_pct, mask = _pct_errors(y_price, pred)
        mape_common = _mape_from_errors(err_pct, mask)
        own_index = _design_index(
            df, spec, unified=unified, response_scale=response_scale, region_col=region_col
        )
        full_fit = _fit_on_index(
            df,
            spec,
            unified=unified,
            response_scale=response_scale,
            region_col=region_col,
            index=own_index,
        )
        if full_fit is None:
            return None
        model_f, y_f, pred_f = full_fit
        decomp = decompose_mape(
            y_f,
            pred_f,
            label=label,
            response_scale=response_scale,
            model=model_f,
            n_common=int(common_index.size),
            mape_common=mape_common,
        )
        return decomp

    own_index = _design_index(
        df, spec, unified=unified, response_scale=response_scale, region_col=region_col
    )
    fit = _fit_on_index(
        df,
        spec,
        unified=unified,
        response_scale=response_scale,
        region_col=region_col,
        index=own_index,
    )
    if fit is None:
        return None
    model, y_price, pred = fit
    return decompose_mape(y_price, pred, label=label, response_scale=response_scale, model=model)


def _region_col(spec: RegressionVariableSpec, admin_level: str, addr4_city: bool) -> str | None:
    from app.built.regression.engine import _eup_leaf_column

    if spec.region_leaf_dummy and admin_level == "eupmyeondong":
        return _eup_leaf_column(addr4_city)
    return None


def build_request(args: argparse.Namespace) -> RegressionRunRequest:
    blocks = _parse_blocks(args.blocks) or list(ALL_BLOCK_IDS[:6])
    spec = _blocks_to_spec(blocks)
    return RegressionRunRequest(
        asset_type=args.asset_type,
        addr1=args.addr1,
        addr2=args.addr2,
        addr3_list=_parse_list(args.addr3_list),
        addr4_list=_parse_list(args.addr4_list),
        contract_year_from=args.year_from,
        contract_year_to=args.year_to,
        window_years=args.window_years,
        variables=spec,
        response_scale=args.scale,
        exclude_outliers_iqr=args.iqr,
        outlier_iqr_multiplier=args.iqr_k,
        leaf_level=args.leaf_level,
    )


def print_report(reports: list[MapeDecomposition], *, common_n: int | None) -> None:
    print("=" * 72)
    print("MAPE 분해 (CH2 engine: Duan smearing · 원척도 금액 만원)")
    print("=" * 72)
    if common_n is not None:
        print(f"공정 비교 행 n={common_n} (모형 간 design matrix 교집합)")
        print()

    for r in reports:
        print(f"--- {r.label} ---")
        print(f"  scale={r.response_scale}  n_fit={r.n_fit}  Adj R²(log)={r.adj_r_squared_log}")
        print(f"  MAPE overall={r.mape_overall_pct}%  (engine={r.engine_mape_pct}%)")
        if r.n_common is not None and r.mape_common_pct is not None:
            print(f"  MAPE common-n={r.mape_common_pct}%  (동일 {r.n_common}행)")
        print(f"  RMSE={r.rmse_won}만원")
        print(
            f"  가격 분포: min={r.price_min} p10={r.price_p10} med={r.price_median} "
            f"p90={r.price_p90} max={r.price_max} (만원)"
        )
        print(f"  저가 건수: <=3천={r.n_price_le_3000}  <=5천={r.n_price_le_5000}")
        print("  구간별 MAPE (|오차| 기여%):")
        for b in r.by_quantile:
            m = f"{b.mape_pct:.1f}%" if b.mape_pct is not None else "N/A"
            sh = f"{b.share_of_total_abs_error:.1f}%" if b.share_of_total_abs_error is not None else "N/A"
            print(f"    {b.label:28} n={b.n:4}  MAPE={m:>8}  abs_err기여={sh}")
        print("  worst 8 (% 오차):")
        for w in r.top_worst:
            print(
                f"    actual={w['price']:>8,.0f}  pred={w['predicted']:>8,.0f}  "
                f"err={w['pct_error']:>7.1f}%  Δ={w['abs_error']:>8,.0f}"
            )
        print()

    if len(reports) == 2:
        a, b = reports
        print("--- delta (B − A) ---")
        if a.mape_common_pct is not None and b.mape_common_pct is not None:
            print(f"  MAPE common-n: {a.mape_common_pct}% → {b.mape_common_pct}%  "
                  f"(Δ {b.mape_common_pct - a.mape_common_pct:+.1f}%p)")
        if a.adj_r_squared_log is not None and b.adj_r_squared_log is not None:
            print(f"  Adj R²(log): {a.adj_r_squared_log:.3f} → {b.adj_r_squared_log:.3f}  "
                  f"(Δ {b.adj_r_squared_log - a.adj_r_squared_log:+.3f})")
        print()


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser(description="복합부동산 회귀 MAPE 분해")
    p.add_argument("--addr1", required=True)
    p.add_argument("--addr2", default=None)
    p.add_argument("--addr3-list", default="", help="구 (쉼표/공백)")
    p.add_argument("--addr4-list", default="", help="동 (쉼표/공백)")
    p.add_argument("--asset-type", default="commercial", choices=["commercial", "factory", "detached", "unified"])
    p.add_argument("--blocks", default="", help="baseline 블록 (쉼표). 기본=6블록 전체")
    p.add_argument(
        "--compare-blocks",
        default="",
        help="비교 모형 블록 (쉼표). 예: gross_area,land_area,building_age,road_width",
    )
    p.add_argument("--scale", default="log", choices=["log", "linear"])
    p.add_argument("--iqr", action="store_true", help="IQR 금액 이상치 제외 (UI와 동일)")
    p.add_argument("--iqr-k", type=float, default=3.0)
    p.add_argument("--year-from", type=int, default=None)
    p.add_argument("--year-to", type=int, default=None)
    p.add_argument("--window-years", type=int, default=None)
    p.add_argument("--leaf-level", default=None, choices=["addr3", "addr4"],
                   help="미지정 + --addr4-list 있으면 addr4 자동")
    p.add_argument("--json", dest="json_out", action="store_true")
    args = p.parse_args()
    if args.addr4_list and not args.leaf_level:
        args.leaf_level = "addr4"

    req = build_request(args)
    engine = get_built_engine()
    with engine.connect() as conn:
        wide_df, req, addr4_city, _mode, _partial_tx_count = _prepare_regression_scope(conn, req)
        level = _focus_admin_level(req, addr4_city)
        df = _scope_for_level(wide_df, req, level, addr4_city, _mode)

    if df.empty:
        print("표본 0건 - scope/필터 확인")
        sys.exit(1)

    unified = is_unified(req.asset_type)
    baseline_blocks = _parse_blocks(args.blocks) or [
        b for b in ALL_BLOCK_IDS if b != "asset_type" or unified
    ][:6]
    compare_blocks = _parse_blocks(args.compare_blocks)

    indices = []
    for blocks in (baseline_blocks, compare_blocks):
        if not blocks:
            continue
        spec_b = _blocks_to_spec(blocks)
        rc = _region_col(spec_b, level, addr4_city)
        indices.append(
            _design_index(
                df,
                spec_b,
                unified=unified,
                response_scale=args.scale,
                region_col=rc,
            )
        )
    common_index = indices[0]
    if len(indices) > 1:
        common_index = indices[0].intersection(indices[1])

    reports: list[MapeDecomposition] = []
    labels = [
        (baseline_blocks, "baseline (현재 블록)"),
        (compare_blocks, "compare (비교 블록)"),
    ]
    for blocks, lbl in labels:
        if not blocks:
            continue
        rc = _region_col(_blocks_to_spec(blocks), level, addr4_city)
        r = analyze_model(
            df,
            blocks,
            label=lbl,
            unified=unified,
            response_scale=args.scale,
            region_col=rc,
            common_index=common_index if len(indices) > 1 else None,
        )
        if r is None:
            print(f"적합 실패: {lbl} blocks={blocks}")
            sys.exit(2)
        reports.append(r)

    # OLS cross-check via engine
    ols = _fit_ols(
        df,
        _blocks_to_spec(baseline_blocks),
        level,
        scope_label="verify",
        unified=unified,
        response_scale=args.scale,
        addr4_city=addr4_city,
    )
    print(f"scope rows={len(df)}  focus={level}  IQR={args.iqr}  engine baseline n={ols.n} mape={ols.mape}")
    print()

    if args.json_out:
        print(json.dumps([asdict(r) for r in reports], ensure_ascii=False, indent=2))
    else:
        print_report(reports, common_n=int(common_index.size) if len(indices) > 1 else None)


if __name__ == "__main__":
    main()
