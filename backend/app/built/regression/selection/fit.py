"""블록 subset OLS 적합."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.built.regression.engine import (
    _build_design_matrix,
    _duan_smearing,
    _insample_mape_pct,
    _insample_pred_price,
    _uses_log_y,
)
from app.built.regression.price_index import TimeAdjuster, deflate_prices
from app.built.regression.selection.blocks import BlockId, spec_from_blocks
from app.built.schemas import JointFTest, RegressionVariableSpec, ResponseScale


@dataclass(frozen=True)
class CvPhase:
    """한 평가 구간(탐색 또는 확인)의 CV 결과와 안정성 진단.

    `mape`는 clip하지 않은 raw 예측으로 계산한 공식 성능 지표다 (D-074). clip 경계는
    계속 계산하되 판정에만 써서 `extreme_rate`로 남긴다. 크게 실패한 예측을 잘라내면
    실패를 덜 실패한 것처럼 만들기 때문에, 안정성은 성능과 분리해 따로 본다.
    """

    mape: float | None = None
    folds: int = 0
    # 학습 관측 가격의 ×0.1~×10 밖으로 나간 예측 비율. 높으면 예측이 불안정한 후보다.
    extreme_rate: float | None = None
    max_ape: float | None = None
    # 폭발한 몇 건에 면역인 보조 지표. 평균 순위와 크게 엇갈리면 D-074를 재검토한다.
    median_ape: float | None = None


_EMPTY_CV = CvPhase()


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
    confirm_cv_mape: float | None = None
    confirm_cv_folds: int = 0
    # 탐색·확인 구간의 안정성 진단. 순위에는 쓰지 않는다.
    cv_search: CvPhase = _EMPTY_CV
    cv_confirm: CvPhase = _EMPTY_CV


def fit_block_subset(
    df: pd.DataFrame,
    blocks: list[BlockId] | list[str],
    *,
    unified: bool,
    response_scale: ResponseScale,
    region_col: str | None,
    admin_level: str,
    with_cv: bool = True,
    time_adjuster: TimeAdjuster | None = None,
) -> BlockFitResult | None:
    import statsmodels.api as sm

    spec = spec_from_blocks(blocks)
    # 최종 적합은 창 전체 지수로 기준시점(창의 마지막 연도)까지 환산한 가격에 맞춘다.
    # 그래야 계수가 시간 추세를 흡수하지 않고 구조만 설명한다 (D-075).
    df_nominal = df
    if time_adjuster is not None:
        df = deflate_prices(df, time_adjuster.full())
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

    mape = _insample_mape_pct(
        y_price, _insample_pred_price(model, response_scale=response_scale)
    )
    search = _EMPTY_CV
    confirm = _EMPTY_CV
    if with_cv:
        # 마지막 연도는 Final Holdout으로 선택에서 떼어 둔다 (D-074). 랭킹은 탐색 CV,
        # 확인은 그 마지막 연도로만. 이전에는 마지막 연도가 랭킹 CV에 포함된 채
        # 같은 연도로 「확인」해서 확인이 확인이 아니었다.
        # CV에는 환산 전 원본을 넘긴다 — fold마다 학습 연도만으로 지수를 다시 추정해야
        # holdout 연도가 전처리로 새지 않는다 (D-075).
        search, confirm = _rolling_time_cv_mape(
            df_nominal,
            spec,
            unified=unified,
            response_scale=response_scale,
            region_col=region_col_use,
            holdout_last_year=True,
            time_adjuster=time_adjuster,
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
        cv_mape=search.mape,
        cv_folds=search.folds,
        confirm_cv_mape=confirm.mape,
        confirm_cv_folds=confirm.folds,
        cv_search=search,
        cv_confirm=confirm,
    )


def rolling_time_cv_split(
    df: pd.DataFrame,
    spec: RegressionVariableSpec,
    *,
    unified: bool,
    response_scale: ResponseScale,
    region_col: str | None,
    time_adjuster: TimeAdjuster | None = None,
) -> tuple[float | None, int, float | None, int, str | None]:
    """탐색 CV(마지막 연도 제외)와 확인 CV(마지막 연도).

    고유 연도가 3 미만이면 확인을 생략하고 탐색은 기존 롤링과 같다.
    """
    search, confirm = _rolling_time_cv_mape(
        df,
        spec,
        unified=unified,
        response_scale=response_scale,
        region_col=region_col,
        holdout_last_year=True,
        time_adjuster=time_adjuster,
    )
    skip = None
    if confirm.mape is None:
        skip = "확인 CV 생략 — 고유 계약연도가 3년 미만이거나 마지막 연도 fold를 적합할 수 없음"
    return search.mape, search.folds, confirm.mape, confirm.folds, skip


def _estimable_columns(x_train: pd.DataFrame) -> list[str]:
    """학습 fold에서 계수를 추정할 수 있는 열만 고른다.

    설계행렬을 전체 표본에서 만들기 때문에, 학습 fold에 한 번도 나오지 않는
    범주의 더미는 전부 0인 열이 된다. 그대로 두면 statsmodels가 pinv로 축퇴된
    해를 조용히 내놓으므로 그런 열을 먼저 뺀다. 뺀 뒤에도 공선이 남으면 (예:
    더미가 fold를 완전 분할해 상수와 겹칠 때) 빈 목록을 돌려 fold를 건너뛴다.
    """
    varying = [
        column
        for column in x_train.columns
        if column == "const" or x_train[column].nunique(dropna=False) > 1
    ]
    if not varying:
        return []
    matrix = x_train.loc[:, varying].to_numpy(dtype=float)
    # 면적(수십~수백)과 더미(0/1)가 섞여 있으면 특이값 범위가 커져 rank 판정
    # 허용오차가 느슨해진다. 열 노름으로 정규화해 척도 영향을 뺀다.
    norms = np.linalg.norm(matrix, axis=0)
    norms[norms == 0.0] = 1.0
    if np.linalg.matrix_rank(matrix / norms) < len(varying):
        return []
    return varying


def _rolling_time_cv_mape(
    df: pd.DataFrame,
    spec: RegressionVariableSpec,
    *,
    unified: bool,
    response_scale: ResponseScale,
    region_col: str | None,
    holdout_last_year: bool = False,
    time_adjuster: TimeAdjuster | None = None,
) -> tuple[CvPhase, CvPhase]:
    """과거 연도로 학습하고 다음 연도를 평가하는 rolling CV-MAPE.

    MAPE는 fold 평균이 아니라 **거래 가중 평균**이다. fold마다의 개별 오차를 모두
    모아 한 번에 평균하므로 거래가 많은 연도가 지표를 더 끌어당긴다.

    예측은 **clip하지 않는다** (D-074). 학습 관측 범위를 크게 벗어난 예측은 실제로
    실패한 예측이므로 지표에 그대로 반영하고, 대신 그 비율을 `extreme_rate`로 남겨
    안정성 진단에 쓴다. 역변환 보정 계수는 그 fold의 **train 잔차만** 쓴다.

    `time_adjuster`를 주면 fold마다 **그 fold의 학습 연도만으로** 지수를 추정해 학습
    가격을 마지막 학습 연도 수준으로 환산한다 (D-075). 평가 연도의 실제 가격은 **손대지
    않는다** — 그 해의 지수는 예측 시점에 알 수 없기 때문이다. 따라서 CV-MAPE는 계속
    「실제 거래가 대비 몇 % 틀렸나」로 읽히고, 보정의 이득은 학습 수준이 평가 연도에 더
    가까워지는 데서 나온다(창 5년 평균 수준 → 직전 연도 수준).

    설계행렬은 전체 표본에서 한 번 만들고 연도로만 나눈다. 따라서 학습 fold에
    없는 범주의 더미 열이 생길 수 있어, fold마다 추정 불가 열을 빼고 적합한다.
    """
    import statsmodels.api as sm

    if "contract_year" not in df.columns:
        return _EMPTY_CV, _EMPTY_CV
    years = sorted(pd.to_numeric(df["contract_year"], errors="coerce").dropna().unique())
    if len(years) < 2:
        return _EMPTY_CV, _EMPTY_CV
    try:
        y, X, _ = _build_design_matrix(
            df,
            spec,
            unified=unified,
            response_scale=response_scale,
            region_col=region_col,
        )
    except (KeyError, ValueError, TypeError):
        return _EMPTY_CV, _EMPTY_CV
    if y.empty:
        return _EMPTY_CV, _EMPTY_CV
    x_const = sm.add_constant(X.astype(float), has_constant="add")
    price = pd.to_numeric(df["price"], errors="coerce").reindex(y.index)
    year_values = pd.to_numeric(df["contract_year"], errors="coerce").reindex(y.index)

    confirm_year = years[-1] if holdout_last_year and len(years) >= 3 else None
    search_years = [yr for yr in years[1:] if confirm_year is None or yr != confirm_year]

    def _eval(test_years: list) -> CvPhase:
        fold_errors: list[float] = []
        extreme_hits = 0
        scored = 0
        valid_folds = 0
        for test_year in test_years:
            train_mask = year_values < test_year
            test_mask = year_values == test_year
            if int(train_mask.sum()) < max(5, x_const.shape[1] + 1) or not bool(test_mask.any()):
                continue
            y_train = y.loc[train_mask]
            y_test = y.loc[test_mask]
            if _uses_log_y(response_scale) and (price.loc[y_train.index] <= 0).any():
                continue
            columns = _estimable_columns(x_const.loc[y_train.index])
            if not columns:
                continue
            if time_adjuster is not None:
                train_years = sorted(
                    int(v) for v in year_values.loc[y_train.index].dropna().unique()
                )
                fold_index = time_adjuster.for_train_years(train_years)
                if fold_index.available:
                    # y는 이미 척도 변환된 값이므로 X를 다시 만들지 않고 y만 옮긴다.
                    factors = year_values.loc[y_train.index].map(fold_index.factor).fillna(1.0)
                    if _uses_log_y(response_scale):
                        y_train = y_train + np.log(factors.to_numpy(dtype=float))
                    else:
                        y_train = y_train * factors.to_numpy(dtype=float)
            try:
                model = sm.OLS(y_train, x_const.loc[y_train.index, columns]).fit()
                pred = np.asarray(
                    model.predict(x_const.loc[y_test.index, columns]), dtype=float
                )
                if _uses_log_y(response_scale):
                    # 보정 계수는 학습 fold의 잔차만으로 — validation 잔차를 쓰면 누수다.
                    pred = np.exp(pred) * _duan_smearing(model.resid.to_numpy())
                actual = price.loc[y_test.index].to_numpy(dtype=float)
                valid = np.isfinite(actual) & np.isfinite(pred) & (actual != 0)
                if valid.any():
                    fold_errors.extend(
                        (np.abs(actual[valid] - pred[valid]) / np.abs(actual[valid])).tolist()
                    )
                    valid_folds += 1
                    # 성능에는 개입하지 않고, 학습 범위를 한 자릿수 이상 벗어난 예측만 센다.
                    train_actual = price.loc[y_train.index].to_numpy(dtype=float)
                    train_actual = train_actual[np.isfinite(train_actual) & (train_actual > 0)]
                    scored += int(valid.sum())
                    if train_actual.size:
                        lo = train_actual.min() * 0.1
                        hi = train_actual.max() * 10
                        pred_valid = pred[valid]
                        extreme_hits += int(((pred_valid < lo) | (pred_valid > hi)).sum())
            except (ValueError, np.linalg.LinAlgError):
                continue
        if not fold_errors:
            return _EMPTY_CV
        errors = np.asarray(fold_errors, dtype=float)
        return CvPhase(
            mape=round(float(np.mean(errors)) * 100, 2),
            folds=valid_folds,
            extreme_rate=round(extreme_hits / scored, 4) if scored else None,
            max_ape=round(float(np.max(errors)) * 100, 2),
            median_ape=round(float(np.median(errors)) * 100, 2),
        )

    search = _eval(search_years)
    confirm = _eval([confirm_year]) if confirm_year is not None else _EMPTY_CV
    return search, confirm


def attach_joint_f_tests(
    df: pd.DataFrame,
    fit: BlockFitResult,
    *,
    unified: bool,
    region_col: str | None,
    admin_level: str,
    time_adjuster: TimeAdjuster | None = None,
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
            with_cv=False,  # compare_f_test는 model만 쓴다
            time_adjuster=time_adjuster,
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


LOGLOG_X_BLOCKS = frozenset({"gross_area", "land_area"})
LOG_FAMILY_SCALES = frozenset({"log", "loglog"})


def subset_allows_loglog(blocks: list[BlockId] | list[str]) -> bool:
    return any(b in LOGLOG_X_BLOCKS for b in blocks)


def common_scale_frame(df: pd.DataFrame, blocks: list[BlockId] | list[str]) -> pd.DataFrame:
    """linear / log / log-log가 같은 행에서 붙도록 양수 가격·면적을 고정한다."""
    if df.empty:
        return df
    out = df
    if "price" in out.columns:
        price = pd.to_numeric(out["price"], errors="coerce")
        out = out.loc[price.notna() & (price > 0)]
    for col in LOGLOG_X_BLOCKS:
        if col in blocks and col in out.columns:
            area = pd.to_numeric(out[col], errors="coerce")
            out = out.loc[area.notna() & (area > 0)]
    return out


def orig_cv_sort_key(fit: BlockFitResult) -> tuple[int, float, float]:
    """원척도 CV-MAPE 우선, 없으면 in-sample MAPE, 마지막에 AIC."""
    if fit.cv_mape is not None:
        mape = float(fit.mape) if fit.mape is not None else 1e9
        return (0, float(fit.cv_mape), mape)
    if fit.mape is not None:
        return (1, float(fit.mape), 0.0)
    return (2, float(fit.aic), 0.0)


def pick_predictive_scale(fits: dict[str, BlockFitResult]) -> BlockFitResult:
    return min(fits.values(), key=orig_cv_sort_key)


def pick_explanatory_scale(fits: dict[str, BlockFitResult]) -> BlockFitResult | None:
    """설명형은 같은 y(log 금액)끼리 AIC. 선형 AIC는 섞지 않는다."""
    family = [fit for scale, fit in fits.items() if scale in LOG_FAMILY_SCALES]
    if not family:
        return None
    return min(family, key=lambda r: r.aic)


def fit_scale_candidates(
    df: pd.DataFrame,
    blocks: list[BlockId] | list[str],
    *,
    unified: bool,
    region_col: str | None,
    admin_level: str,
    time_adjuster: TimeAdjuster | None = None,
) -> dict[str, BlockFitResult]:
    df_cmp = common_scale_frame(df, blocks)
    scales: list[ResponseScale] = ["linear", "log"]
    if subset_allows_loglog(blocks):
        scales.append("loglog")
    fits: dict[str, BlockFitResult] = {}
    for scale in scales:
        result = fit_block_subset(
            df_cmp,
            blocks,
            unified=unified,
            response_scale=scale,
            region_col=region_col,
            admin_level=admin_level,
            time_adjuster=time_adjuster,
        )
        if result is not None:
            fits[scale] = result
    return fits


def fit_best_scale(
    df: pd.DataFrame,
    blocks: list[BlockId] | list[str],
    *,
    unified: bool,
    region_col: str | None,
    admin_level: str,
    time_adjuster: TimeAdjuster | None = None,
) -> tuple[BlockFitResult | None, object | None]:
    """linear·log·log-log 중 원척도 CV-MAPE 최소 scale + ModelComparison."""
    from app.built.regression.selection.metrics import build_model_comparison_from_fits

    fits = fit_scale_candidates(
        df,
        blocks,
        unified=unified,
        region_col=region_col,
        admin_level=admin_level,
        time_adjuster=time_adjuster,
    )
    if not fits:
        return None, None
    best = pick_predictive_scale(fits)
    df_cmp = common_scale_frame(df, blocks)
    best = attach_joint_f_tests(
        df_cmp,
        best,
        unified=unified,
        region_col=region_col,
        admin_level=admin_level,
        time_adjuster=time_adjuster,
    )
    cmp = build_model_comparison_from_fits(fits, recommended=best.response_scale)
    return best, cmp
