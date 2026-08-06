"""블록 subset OLS 적합."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.built.regression.engine import (
    _build_design_matrix,
    _duan_smearing,
    _insample_mape_pct,
    _uses_log_y,
)
from app.built.regression.selection.blocks import BlockId, spec_from_blocks
from app.built.schemas import JointFTest, RegressionVariableSpec, ResponseScale


@dataclass
class BlockFitResult:
    blocks: list[BlockId]
    variables: RegressionVariableSpec
    response_scale: ResponseScale
    n: int
    n_params: int
    aic: float
    bic: float
    adj_r_squared: float | None
    mape: float | None
    model: object
    x_const: pd.DataFrame
    y_price: np.ndarray
    joint_f_tests: dict[str, JointFTest]
    cv_mape: float | None
    cv_folds: int


def fit_block_subset(
    df: pd.DataFrame,
    blocks: list[BlockId] | list[str],
    *,
    unified: bool,
    response_scale: ResponseScale,
    region_col: str | None,
    admin_level: str,
) -> BlockFitResult | None:
    import statsmodels.api as sm

    spec = spec_from_blocks(blocks)
    y_raw = pd.to_numeric(df["price"], errors="coerce")
    region_col_use = (
        region_col
        if spec.region_leaf_dummy and admin_level in {"eupmyeondong", "beopjungri"}
        else None
    )

    y, X, _meta = _build_design_matrix(
        df,
        spec,
        unified=unified,
        response_scale=response_scale,
        region_col=region_col_use,
    )
    if y_raw.notna().sum() < 5:
        return None

    mask = y_raw.notna()
    y_price = y_raw.loc[mask].astype(float).to_numpy()

    if X.empty:
        y_fit = y_price.copy()
        if _uses_log_y(response_scale):
            if (y_fit <= 0).any():
                return None
            y_fit = np.log(y_fit)
        x_const = pd.DataFrame({"const": np.ones(len(y_fit))})
        try:
            model = sm.OLS(y_fit, x_const).fit()
        except Exception:
            return None
    else:
        if len(y) < max(5, X.shape[1] + 1):
            return None
        y_fit = y.astype(float)
        x_const = sm.add_constant(X.astype(float), has_constant="add")
        try:
            model = sm.OLS(y_fit, x_const).fit()
        except Exception:
            return None
        y_price = pd.to_numeric(df["price"], errors="coerce").loc[y.index].astype(float).to_numpy()

    mape = _insample_mape_pct(y_price, model, response_scale=response_scale)
    cv_mape, cv_folds = _rolling_time_cv_mape(
        df,
        spec,
        unified=unified,
        response_scale=response_scale,
        region_col=region_col_use,
    )
    return BlockFitResult(
        blocks=list(blocks),
        variables=spec,
        response_scale=response_scale,
        n=int(model.nobs),
        n_params=int(len(model.params)),
        aic=float(model.aic),
        bic=float(model.bic),
        adj_r_squared=float(model.rsquared_adj) if model.rsquared_adj is not None else None,
        mape=mape,
        model=model,
        x_const=x_const,
        y_price=y_price,
        joint_f_tests={},
        cv_mape=cv_mape,
        cv_folds=cv_folds,
    )


def _rolling_time_cv_mape(
    df: pd.DataFrame,
    spec: RegressionVariableSpec,
    *,
    unified: bool,
    response_scale: ResponseScale,
    region_col: str | None,
) -> tuple[float | None, int]:
    """과거 연도로 학습하고 다음 연도를 평가하는 rolling CV-MAPE."""
    import statsmodels.api as sm

    if "contract_year" not in df.columns:
        return None, 0
    years = sorted(pd.to_numeric(df["contract_year"], errors="coerce").dropna().unique())
    if len(years) < 2:
        return None, 0
    try:
        y, X, _ = _build_design_matrix(
            df,
            spec,
            unified=unified,
            response_scale=response_scale,
            region_col=region_col,
        )
    except (KeyError, ValueError, TypeError):
        return None, 0
    if y.empty:
        return None, 0
    x_const = sm.add_constant(X.astype(float), has_constant="add")
    price = pd.to_numeric(df["price"], errors="coerce").reindex(y.index)
    year_values = pd.to_numeric(df["contract_year"], errors="coerce").reindex(y.index)
    fold_errors: list[float] = []
    valid_folds = 0
    for test_year in years[1:]:
        train_mask = year_values < test_year
        test_mask = year_values == test_year
        if int(train_mask.sum()) < max(5, x_const.shape[1] + 1) or not bool(test_mask.any()):
            continue
        y_train = y.loc[train_mask]
        y_test = y.loc[test_mask]
        if _uses_log_y(response_scale) and (price.loc[y_train.index] <= 0).any():
            continue
        try:
            model = sm.OLS(y_train, x_const.loc[y_train.index]).fit()
            pred = np.asarray(model.predict(x_const.loc[y_test.index]), dtype=float)
            if _uses_log_y(response_scale):
                pred = np.exp(pred) * _duan_smearing(model.resid.to_numpy())
            # log-scale 예측을 지수화하면 test fold의 범주 조합이 train에 드물게
            # 나타났을 때 극단적으로 큰 예측값(예: price 대비 10^150배)이 나올 수
            # 있다. 이런 수치적 발산은 "예측이 나쁘다"가 아니라 외삽 실패이므로,
            # train 표본의 관측 가격 범위를 벗어난 예측은 그 범위로 clip한다.
            train_actual = price.loc[y_train.index].to_numpy(dtype=float)
            train_actual = train_actual[np.isfinite(train_actual) & (train_actual > 0)]
            if train_actual.size:
                pred = np.clip(pred, train_actual.min() * 0.1, train_actual.max() * 10)
            actual = price.loc[y_test.index].to_numpy(dtype=float)
            valid = np.isfinite(actual) & np.isfinite(pred) & (actual != 0)
            if valid.any():
                fold_errors.extend(
                    (np.abs(actual[valid] - pred[valid]) / np.abs(actual[valid])).tolist()
                )
                valid_folds += 1
        except (ValueError, np.linalg.LinAlgError):
            continue
    if not fold_errors:
        return None, 0
    return round(float(np.mean(fold_errors)) * 100, 2), valid_folds


def attach_joint_f_tests(
    df: pd.DataFrame,
    fit: BlockFitResult,
    *,
    unified: bool,
    region_col: str | None,
    admin_level: str,
) -> BlockFitResult:
    """각 포함 블록을 제거한 nested model과 Joint F-test를 계산한다."""
    results: dict[str, JointFTest] = {}
    for block in fit.blocks:
        reduced_blocks = [candidate for candidate in fit.blocks if candidate != block]
        reduced = fit_block_subset(
            df,
            reduced_blocks,
            unified=unified,
            response_scale=fit.response_scale,
            region_col=region_col,
            admin_level=admin_level,
        )
        if reduced is None:
            results[block] = JointFTest(tested=False)
            continue
        try:
            f_value, p_value, df_diff = fit.model.compare_f_test(reduced.model)
            f_value = float(f_value)
            p_value = float(p_value)
            if not (np.isfinite(f_value) and np.isfinite(p_value)):
                # 표본이 작아 완전적합(ssr≈0)이면 F값이 무한/NaN이 될 수 있다.
                # JSON은 Infinity/NaN을 지원하지 않으므로 미검정으로 표시한다.
                results[block] = JointFTest(tested=False)
                continue
            results[block] = JointFTest(
                f_statistic=round(f_value, 6),
                p_value=round(p_value, 8),
                df_restriction=int(df_diff),
                df_resid=int(fit.model.df_resid),
                tested=True,
            )
        except (AttributeError, TypeError, ValueError):
            results[block] = JointFTest(tested=False)
    fit.joint_f_tests = results
    return fit


def fit_best_scale(
    df: pd.DataFrame,
    blocks: list[BlockId] | list[str],
    *,
    unified: bool,
    region_col: str | None,
    admin_level: str,
) -> tuple[BlockFitResult | None, object | None]:
    """linear·log 중 AIC 최소 scale 선택 + ModelComparison."""
    from app.built.regression.selection.metrics import build_model_comparison

    fits: dict[str, BlockFitResult] = {}
    for scale in ("linear", "log"):
        r = fit_block_subset(
            df,
            blocks,
            unified=unified,
            response_scale=scale,  # type: ignore[arg-type]
            region_col=region_col,
            admin_level=admin_level,
        )
        if r is not None:
            fits[scale] = r
    if not fits:
        return None, None
    best = min(fits.values(), key=lambda r: r.aic)
    best = attach_joint_f_tests(
        df,
        best,
        unified=unified,
        region_col=region_col,
        admin_level=admin_level,
    )
    cmp = None
    if best.x_const is not None and len(best.x_const):
        y_s = pd.Series(best.y_price)
        cmp = build_model_comparison(y_s, best.x_const)
    return best, cmp
