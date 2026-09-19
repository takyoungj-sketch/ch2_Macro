"""잔차 진단 (P5) — 적합된 모형이 «어디서» 틀리는지 계산한다.

이 제품은 AVM이 아니고 추천식을 정답으로 내세우지 않는다. 사용자가 자기 회귀식을 먼저
만드는 구조라면 그 식이 어디서 틀렸는지 보여 주는 화면이 있어야 한다. Adj R²와 MAPE 숫자
하나씩만으로는 특정 용도지역에서 계속 과소평가하는지, 큰 거래에서만 무너지는지 알 수 없다.

## 잔차 정의 — 화면 MAPE와 같은 것을 쓴다

표시용 잔차는 **원척도 백분율 오차**다.

    오차% = (실제금액 − 예측금액) / 실제금액 × 100

log 종속 모형의 예측금액은 `exp(적합값) × Duan` — `_insample_mape_pct`와 **같은 식**이다.
그래서 집단별 평균 절대오차를 모으면 그 집단의 MAPE가 되고, 화면 상단 MAPE와 단위가 같다.
부호는 **양수 = 모형이 과소평가**(실제가 예측보다 높다).

단 **이분산 검정만은 모형 잔차(log 공간)로 한다.** 등분산을 가정하는 것은 OLS가 실제로
추정한 공간이지 원척도가 아니다. 두 공간을 섞으면 log 모형에서 늘 이분산 판정이 난다.

## 편향은 «중위수»로, 유의성은 «나머지와 비교»로

운영 표본에서 처음 재 보니 전체 평균 편향이 강남 −12.6%, 수성 −19.0%이고 거의 모든 집단이
음수로 «유의»하게 나왔다. 모형이 전부 과대평가한다는 뜻이 아니다. **백분율 오차의 성질**이다:

- log 종속 + Duan은 예측을 **금액 평균**에 맞춘다. 금액 기준으로는 치우침이 없다.
- 그런데 오차를 실제금액으로 나누면 **작은 거래가 분모를 통해 과대 대표된다.** 8천만원
  거래를 3.6억으로 예측하면 −355%지만, 반대 방향 오차는 최대 +100%를 넘지 못한다.
  평균을 내면 구조적으로 음수가 된다.

그래서 두 가지를 바꿨다.

1. **편향은 중위 오차%로 잰다.** 위 꼬리에 끌려다니지 않는다. 평균 절대오차(=MAPE)는
   화면 상단 MAPE와 맞추기 위해 그대로 평균으로 둔다 — 둘은 다른 통계다.
2. **유의성은 「그 집단 vs 나머지 표본」 Mann–Whitney로 판정한다.** 전체가 공통으로
   가진 치우침은 양쪽에 똑같이 들어 있으므로 자동으로 상쇄되고, **그 집단만 다르게
   틀리는지**만 남는다. 평균을 0과 비교하는 방식으로는 전 집단이 유의하게 찍혔다.

`excess_bias_pct`(그 집단 중위 − 나머지 중위)가 화면에서 읽어야 할 숫자다. 절대 편향은
참고값이다. n이 `MIN_GROUP_N` 미달인 집단은 애초에 표에 넣지 않는다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.built.schemas import (
    CoefficientShift,
    CorrelationPoint,
    InfluentialTransaction,
    ResidualDiagnostics,
    ResidualGroup,
    ResidualGroupSet,
    ResidualScaleBin,
)

# 집단별 편향을 보고할 최소 건수. 이보다 얇은 집단은 평균이 거래 한두 건에 끌려다닌다.
MIN_GROUP_N = 10
# 한 축에 보여 줄 집단 수 상한. 읍면동이 수십 개면 화면이 표로 덮인다.
MAX_GROUPS_PER_SET = 12
# 영향이 큰 거래 보고 건수.
TOP_INFLUENTIAL = 5
# 산점도 점 수 상한 — 산점도 번들(`_subsample_points`)과 같은 기준.
MAX_SCATTER_POINTS = 500
# 영향도(hat 대각)는 n × p² 연산이다. 초점 표본은 보통 수천 건이지만 상위 행정층을
# 초점으로 잡으면 커질 수 있어 상한을 둔다.
MAX_INFLUENCE_N = 50_000


def _pct_errors(y_price: np.ndarray, pred: np.ndarray) -> np.ndarray:
    """오차%. 실제금액이 0이거나 비유한이면 NaN."""
    y = np.asarray(y_price, dtype=float)
    p = np.asarray(pred, dtype=float)
    out = np.full(y.shape, np.nan)
    ok = np.isfinite(y) & np.isfinite(p) & (y != 0)
    out[ok] = (y[ok] - p[ok]) / np.abs(y[ok]) * 100.0
    return out


def _group_vs_rest(inside: np.ndarray, outside: np.ndarray) -> float | None:
    """그 집단 오차 분포가 나머지와 다른지 — Mann–Whitney U (양측).

    평균을 0과 비교하지 않는 이유는 모듈 설명에 있다. 전체 표본이 공통으로 가진 치우침은
    양쪽에 똑같이 들어 있어 상쇄되고, 그 집단만의 차이가 남는다.
    """
    if inside.size < 3 or outside.size < 3:
        return None
    try:
        from scipy.stats import mannwhitneyu

        return float(mannwhitneyu(inside, outside, alternative="two-sided").pvalue)
    except Exception:  # noqa: BLE001 — 검정 실패가 진단 전체를 막지 않는다
        return None


def _group_set(
    key: str,
    label: str,
    keys: pd.Series,
    err: np.ndarray,
    *,
    order: list[str] | None = None,
) -> ResidualGroupSet | None:
    """한 축(용도지역·연식 구간 등)의 집단별 편향.

    `order`가 있으면 그 순서대로(연식 구간처럼 자연 순서가 있는 축), 없으면 |전체 대비
    초과 편향| 큰 순서대로 — 진단 목적에서는 남들과 다르게 틀리는 집단이 먼저 보여야 한다.
    """
    s = keys.astype("string").str.strip().replace("", pd.NA)
    finite = np.isfinite(err)
    groups: list[ResidualGroup] = []
    omitted = 0
    labelled = s.dropna()
    for name, idx in labelled.groupby(labelled).groups.items():
        pos = s.index.get_indexer(pd.Index(idx))
        sel = np.zeros(err.shape, dtype=bool)
        sel[pos] = True
        sel &= finite
        n = int(sel.sum())
        if n == 0:
            continue
        if n < MIN_GROUP_N:
            omitted += n
            continue
        inside = err[sel]
        outside = err[finite & ~sel]
        p = _group_vs_rest(inside, outside)
        rest_median = float(np.median(outside)) if outside.size else 0.0
        median = float(np.median(inside))
        groups.append(
            ResidualGroup(
                label=str(name),
                n=n,
                bias_pct=round(median, 1),
                excess_bias_pct=round(median - rest_median, 1),
                mape_pct=round(float(np.mean(np.abs(inside))), 1),
                p_value=round(p, 4) if p is not None else None,
                significant=bool(p is not None and p < 0.05),
            )
        )
    omitted += int((finite & s.isna().to_numpy()).sum())
    if len(groups) < 2:
        # 집단이 하나면 「나머지와 비교」가 성립하지 않는다.
        return None
    if order:
        rank = {v: i for i, v in enumerate(order)}
        groups.sort(key=lambda g: rank.get(g.label, len(rank)))
    else:
        groups.sort(key=lambda g: (-abs(g.excess_bias_pct), -g.n))
    trimmed = len(groups) > MAX_GROUPS_PER_SET
    if trimmed:
        omitted += sum(g.n for g in groups[MAX_GROUPS_PER_SET:])
        groups = groups[:MAX_GROUPS_PER_SET]
    return ResidualGroupSet(
        key=key,
        label=label,
        groups=groups,
        omitted_n=omitted,
        trimmed=trimmed,
    )


_AGE_BINS = [
    (0, 5, "신축 0–4년"),
    (5, 10, "준신축 5–9년"),
    (10, 20, "10–19년"),
    (20, 30, "20–29년"),
    (30, np.inf, "30년+"),
]
_AGE_ORDER = [lbl for _, _, lbl in _AGE_BINS]


def _age_bin_keys(age: pd.Series) -> pd.Series:
    a = pd.to_numeric(age, errors="coerce")
    out = pd.Series(pd.NA, index=age.index, dtype="string")
    for lo, hi, lbl in _AGE_BINS:
        out[(a >= lo) & (a < hi)] = lbl
    return out


def _quintile_keys(values: pd.Series, unit: str) -> pd.Series:
    """규모 5분위. 경계값을 라벨에 넣어 「어느 구간인지」가 화면에서 바로 읽히게 한다."""
    v = pd.to_numeric(values, errors="coerce")
    ok = v.dropna()
    out = pd.Series(pd.NA, index=values.index, dtype="string")
    if ok.nunique() < 5:
        return out
    try:
        edges = np.unique(np.quantile(ok.to_numpy(), [0, 0.2, 0.4, 0.6, 0.8, 1.0]))
    except (ValueError, IndexError):
        return out
    if edges.size < 3:
        return out
    for i in range(edges.size - 1):
        lo, hi = edges[i], edges[i + 1]
        last = i == edges.size - 2
        sel = (v >= lo) & ((v <= hi) if last else (v < hi))
        out[sel] = f"{i + 1}분위 {lo:,.0f}–{hi:,.0f}{unit}"
    return out


def _scale_bins(fitted_price: np.ndarray, err: np.ndarray) -> list[ResidualScaleBin]:
    """적합값 5분위별 오차 산포 — 이분산을 눈이 아니라 숫자로 확인하는 쪽."""
    ok = np.isfinite(fitted_price) & np.isfinite(err)
    if ok.sum() < 25:
        return []
    f, e = fitted_price[ok], err[ok]
    try:
        edges = np.unique(np.quantile(f, [0, 0.2, 0.4, 0.6, 0.8, 1.0]))
    except (ValueError, IndexError):
        return []
    if edges.size < 3:
        return []
    bins: list[ResidualScaleBin] = []
    for i in range(edges.size - 1):
        lo, hi = edges[i], edges[i + 1]
        last = i == edges.size - 2
        sel = (f >= lo) & ((f <= hi) if last else (f < hi))
        if sel.sum() < 3:
            continue
        bins.append(
            ResidualScaleBin(
                label=f"{i + 1}분위",
                n=int(sel.sum()),
                fitted_median=round(float(np.median(f[sel])), 1),
                abs_pct_median=round(float(np.median(np.abs(e[sel]))), 1),
                spread_pct=round(float(np.std(e[sel], ddof=1)), 1),
            )
        )
    return bins


def _het_p_value(model) -> float | None:
    """Breusch–Pagan p값. 모형 잔차(= OLS가 실제로 등분산을 가정한 공간)로 검정한다.

    더미가 많으면 보조회귀가 특이해져 실패할 수 있다. 실패는 None으로 넘기고 분위별
    산포로 판단하게 한다 — 진단이 아예 없는 것보다 낫다.
    """
    try:
        from statsmodels.stats.diagnostic import het_breuschpagan

        exog = np.asarray(model.model.exog, dtype=float)
        resid = np.asarray(model.resid, dtype=float)
        if exog.shape[0] - exog.shape[1] < 5:
            return None
        _, p_value, _, _ = het_breuschpagan(resid, exog)
        return float(p_value) if np.isfinite(p_value) else None
    except Exception:  # noqa: BLE001 — 진단 실패가 회귀 응답을 막으면 안 된다
        return None


def _het_note(p_value: float | None, bins: list[ResidualScaleBin]) -> str | None:
    """이분산 설명 — **분위별 산포를 먼저** 말하고 검정은 보조로 붙인다.

    운영 표본에서 둘이 양방향으로 엇갈렸다. 강남은 BP p=0.000인데 분위별 산포가
    42~46%로 평평했고, 수성은 p=0.109인데 산포가 83%→43%로 급감했다. BP는 «금액대»가
    아니라 설계행렬 전체에 반응하고 n이 크면 사소한 위반에도 기각한다. 사용자가 실제로
    쓸 수 있는 정보는 「어느 금액대에서 더 많이 틀리나」이므로 그쪽을 기준으로 삼는다.
    """
    formal = None
    if p_value is not None:
        verdict = "기각" if p_value < 0.05 else "유지"
        formal = f"형식 검정(Breusch–Pagan) p={p_value:.3f} — 등분산 {verdict}"

    spreads = [b.spread_pct for b in bins if b.spread_pct > 0]
    if len(spreads) < 3:
        return formal or "이분산을 판단할 자료가 부족합니다."

    ratio = max(spreads) / min(spreads)
    lo, hi = bins[0].spread_pct, bins[-1].spread_pct
    if ratio < 1.4:
        core = f"금액대별 오차 폭이 고릅니다 (분위별 산포 {min(spreads):.0f}~{max(spreads):.0f}%)."
    elif lo > hi:
        core = (
            f"금액이 작은 쪽에서 더 많이 틀립니다 (1분위 산포 {lo:.0f}% → 5분위 {hi:.0f}%). "
            "작은 거래의 예상값은 넓게 보세요."
        )
    elif hi > lo:
        core = (
            f"금액이 큰 쪽에서 더 많이 틀립니다 (1분위 산포 {lo:.0f}% → 5분위 {hi:.0f}%). "
            "고가 물건의 예상값은 넓게 보세요."
        )
    else:
        core = f"분위별 산포가 최대 {ratio:.1f}배 차이 납니다."

    if formal and ratio < 1.4 and p_value is not None and p_value < 0.05:
        # 이 조합이 강남에서 나왔다. 검정만 보고 「금액대에 따라 다르다」로 읽으면 틀린다.
        return (
            f"{core} {formal}이지만, 이는 금액대가 아닌 다른 변수 방향의 위반일 수 있습니다."
        )
    return f"{core} {formal}" if formal else core


def _cooks_distance(model) -> np.ndarray | None:
    """Cook 거리. hat 대각을 직접 계산한다 (statsmodels influence보다 가볍다)."""
    try:
        X = np.asarray(model.model.exog, dtype=float)
        n, p = X.shape
        if n <= p + 1 or n > MAX_INFLUENCE_N:
            return None
        mse = float(model.mse_resid)
        if not np.isfinite(mse) or mse <= 0:
            return None
        xtx_inv = np.linalg.pinv(X.T @ X)
        h = np.einsum("ij,jk,ik->i", X, xtx_inv, X)
        h = np.clip(h, 0.0, 1.0 - 1e-9)
        e = np.asarray(model.resid, dtype=float)
        return (e**2 / (p * mse)) * (h / (1.0 - h) ** 2)
    except Exception:  # noqa: BLE001
        return None


def _leverage(model) -> np.ndarray | None:
    try:
        X = np.asarray(model.model.exog, dtype=float)
        xtx_inv = np.linalg.pinv(X.T @ X)
        return np.einsum("ij,jk,ik->i", X, xtx_inv, X)
    except Exception:  # noqa: BLE001
        return None


def _tx_label(row: pd.Series, leaf_col: str) -> str:
    bits = [row.get(leaf_col), row.get("addr5")]
    out = " ".join(str(b).strip() for b in bits if b is not None and str(b).strip())
    return out or "주소 미상"


def _refit_without(
    model,
    drop_positions: np.ndarray,
) -> tuple[list[CoefficientShift], str | None]:
    """영향 상위 거래를 뺀 재적합 — 「이 몇 건이 끌고 있다」의 정량 근거.

    변화 크기는 **표준오차 배수**로 잰다. 계수 스케일이 서로 다르고(면적 탄력성 vs 연식
    계수) 0 근처 계수는 백분율이 폭발하기 때문이다. 1 SE 넘게 움직이면 그 몇 건이 계수를
    실질적으로 끌고 있다는 뜻이다.
    """
    try:
        import statsmodels.api as sm

        X = np.asarray(model.model.exog, dtype=float)
        y = np.asarray(model.model.endog, dtype=float)
        keep = np.ones(X.shape[0], dtype=bool)
        keep[drop_positions] = False
        if keep.sum() <= X.shape[1] + 1:
            return [], "제외 후 표본이 부족해 재적합을 생략했습니다."
        refit = sm.OLS(y[keep], X[keep]).fit()
        names = list(model.params.index)
        before = np.asarray(model.params, dtype=float)
        after = np.asarray(refit.params, dtype=float)
        se = np.asarray(model.bse, dtype=float)
        shifts: list[CoefficientShift] = []
        for i, name in enumerate(names):
            b, a, s = before[i], after[i], se[i]
            if not (np.isfinite(b) and np.isfinite(a)):
                continue
            shift_se = float(abs(a - b) / s) if np.isfinite(s) and s > 0 else None
            shift_pct = (
                round(float((a - b) / abs(b) * 100), 1) if abs(b) > 1e-9 else None
            )
            shifts.append(
                CoefficientShift(
                    name=str(name),
                    before=round(float(b), 6),
                    after=round(float(a), 6),
                    shift_se=round(shift_se, 2) if shift_se is not None else None,
                    shift_pct=shift_pct,
                )
            )
        shifts.sort(key=lambda c: -(c.shift_se or 0.0))
        top = shifts[:4]
        worst = top[0].shift_se if top else None
        if worst is None:
            note = None
        elif worst >= 1.0:
            note = (
                f"이 {len(drop_positions)}건을 빼면 계수가 최대 {worst:.1f} 표준오차 "
                "움직입니다 — 소수 거래가 결과를 끌고 있습니다."
            )
        else:
            note = (
                f"이 {len(drop_positions)}건을 빼도 계수 변화는 최대 {worst:.1f} 표준오차로 "
                "작습니다 — 모형이 특정 거래에 매달려 있지는 않습니다."
            )
        return top, note
    except Exception:  # noqa: BLE001
        return [], None


def build_residual_diagnostics(
    df: pd.DataFrame,
    model,
    *,
    y_price: np.ndarray,
    pred_price: np.ndarray,
    fitted_index: pd.Index,
    leaf_col: str,
    unified: bool = False,
) -> ResidualDiagnostics | None:
    """적합 결과에서 잔차 진단을 만든다.

    `y_price`·`pred_price`는 `_insample_mape_pct`와 동일하게 구한 원척도 금액이어야 한다.
    이 두 개가 어긋나면 화면 MAPE와 집단별 MAPE가 다른 값을 가리킨다.
    """
    err = _pct_errors(y_price, pred_price)
    finite = np.isfinite(err)
    if finite.sum() < MIN_GROUP_N:
        return None

    fit_df = df.loc[fitted_index]
    e = err[finite]
    bias_pct = round(float(np.median(e)), 1)
    mean_bias_pct = round(float(np.mean(e)), 1)

    step = max(1, int(finite.sum()) // MAX_SCATTER_POINTS)
    pos = np.flatnonzero(finite)[::step]
    points = [
        CorrelationPoint(x=round(float(pred_price[i]), 1), y=round(float(err[i]), 2))
        for i in pos
    ]

    scale_bins = _scale_bins(np.asarray(pred_price, dtype=float), err)
    het_p = _het_p_value(model)
    het_note = _het_note(het_p, scale_bins)

    sets: list[ResidualGroupSet] = []
    if leaf_col in fit_df.columns:
        gs = _group_set("region", "지역", fit_df[leaf_col], err)
        if gs:
            sets.append(gs)
    for col, key, label in (
        ("zone_type", "zone_type", "용도지역"),
        ("building_use", "building_use", "건축물용도"),
    ):
        if col in fit_df.columns:
            gs = _group_set(key, label, fit_df[col], err)
            if gs:
                sets.append(gs)
    if unified and "asset_type" in fit_df.columns:
        gs = _group_set("asset_type", "자산유형", fit_df["asset_type"], err)
        if gs:
            sets.append(gs)
    if "building_age" in fit_df.columns:
        gs = _group_set(
            "building_age", "연식 구간", _age_bin_keys(fit_df["building_age"]), err,
            order=_AGE_ORDER,
        )
        if gs:
            sets.append(gs)
    if "gross_area" in fit_df.columns:
        gs = _group_set(
            "gross_area", "연면적 분위", _quintile_keys(fit_df["gross_area"], "㎡"), err
        )
        if gs:
            sets.append(gs)
    if "contract_year" in fit_df.columns:
        gs = _group_set(
            "contract_year", "계약연도", fit_df["contract_year"].astype("string"), err
        )
        if gs:
            gs.groups.sort(key=lambda g: g.label)
            sets.append(gs)

    influential: list[InfluentialTransaction] = []
    shifts: list[CoefficientShift] = []
    refit_note = None
    cooks = _cooks_distance(model)
    lev = _leverage(model)
    if cooks is not None and cooks.size == len(fit_df):
        ranked = np.argsort(-np.nan_to_num(cooks, nan=-1.0))[:TOP_INFLUENTIAL]
        ranked = [int(i) for i in ranked if np.isfinite(cooks[i])]
        for rank, i in enumerate(ranked, start=1):
            row = fit_df.iloc[i]
            influential.append(
                InfluentialTransaction(
                    rank=rank,
                    label=_tx_label(row, leaf_col),
                    contract_year=(
                        int(row["contract_year"])
                        if "contract_year" in row and pd.notna(row["contract_year"])
                        else None
                    ),
                    zone_type=(
                        str(row["zone_type"])
                        if "zone_type" in row and pd.notna(row["zone_type"])
                        else None
                    ),
                    price=round(float(y_price[i]), 1),
                    predicted=round(float(pred_price[i]), 1),
                    error_pct=round(float(err[i]), 1) if np.isfinite(err[i]) else None,
                    gross_area=_opt_float(row, "gross_area"),
                    land_area=_opt_float(row, "land_area"),
                    building_age=_opt_float(row, "building_age"),
                    cooks_d=round(float(cooks[i]), 4),
                    leverage=(
                        round(float(lev[i]), 4)
                        if lev is not None and i < lev.size and np.isfinite(lev[i])
                        else None
                    ),
                )
            )
        if ranked:
            shifts, refit_note = _refit_without(model, np.asarray(ranked, dtype=int))

    warning = None
    if cooks is None:
        warning = "표본이 커서 영향도 계산을 생략했습니다." if len(fit_df) > MAX_INFLUENCE_N else None

    return ResidualDiagnostics(
        n=int(finite.sum()),
        residual_definition=(
            "오차% = (실제 − 예측) ÷ 실제 × 100. 양수는 모형이 과소평가한 쪽입니다. "
            "예측은 화면 상단 MAPE와 같은 방식으로 계산했습니다."
        ),
        bias_pct=bias_pct,
        mean_bias_pct=mean_bias_pct,
        bias_note=_bias_note(bias_pct, mean_bias_pct),
        points=points,
        scale_bins=scale_bins,
        het_p_value=het_p,
        het_note=het_note,
        groups=sets,
        influential=influential,
        refit_shifts=shifts,
        refit_note=refit_note,
        warning=warning,
    )


def _bias_note(median_bias: float, mean_bias: float) -> str:
    """중위 편향과 평균 편향이 왜 다른지 — 이걸 안 적으면 사용자가 과대평가로 오독한다."""
    gap = abs(mean_bias - median_bias)
    if gap >= 5:
        return (
            f"평균 편향({mean_bias:+.1f}%)은 중위({median_bias:+.1f}%)보다 음수 쪽입니다. "
            "금액이 작은 거래에서 백분율 오차가 한쪽으로만 크게 벌어지기 때문이며(−300%는 "
            "가능하지만 +300%는 불가), 모형이 전반적으로 과대평가한다는 뜻이 아닙니다. "
            "치우침은 중위로 읽으세요."
        )
    if abs(median_bias) < 3:
        return "전반적으로 한쪽으로 치우쳐 있지 않습니다."
    direction = "과소평가" if median_bias > 0 else "과대평가"
    return f"전반적으로 {direction} 쪽으로 {abs(median_bias):.1f}% 치우쳐 있습니다."


def _opt_float(row: pd.Series, col: str) -> float | None:
    if col not in row or pd.isna(row[col]):
        return None
    try:
        return round(float(row[col]), 1)
    except (TypeError, ValueError):
        return None
