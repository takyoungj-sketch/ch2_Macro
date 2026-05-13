"""백엔드에서 사용하는 통계 계산 유틸리티 (pipeline/stats.py 와 동일 로직)."""

from __future__ import annotations

from typing import Sequence

import numpy as np
import scipy.stats as st

ALPHA = 0.05
MIN_RELIABLE_COUNT = 15
OUTLIER_IQR_MULTIPLIER = 3.0

# 만원/㎡ 단가 통계 반올림 자리수 (매트릭스·표는 소수 첫째 자리까지 표시)
PRICE_STAT_DECIMALS = 1


def _rnd_price(x: float | None) -> float | None:
    if x is None:
        return None
    return round(float(x), PRICE_STAT_DECIMALS)


def compute_stats(prices: Sequence[float]) -> dict:
    arr = np.asarray(prices, dtype=float)
    arr = arr[~np.isnan(arr)]
    n = int(len(arr))

    if n == 0:
        return _empty(0)

    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if n >= 2 else None
    ci_lower, ci_upper = None, None
    if n >= 2:
        se = st.sem(arr)
        ci = st.t.interval(1 - ALPHA, df=n - 1, loc=mean, scale=se)
        ci_lower, ci_upper = _finite_or_none(ci[0]), _finite_or_none(ci[1])

    return {
        "count": n,
        "mean": _rnd_price(mean),
        "std": _rnd_price(std) if std is not None else None,
        "ci_lower": _rnd_price(ci_lower) if ci_lower is not None else None,
        "ci_upper": _rnd_price(ci_upper) if ci_upper is not None else None,
        "min": _rnd_price(float(np.min(arr))),
        "p25": _rnd_price(float(np.percentile(arr, 25))),
        "median": _rnd_price(float(np.median(arr))),
        "p75": _rnd_price(float(np.percentile(arr, 75))),
        "max": _rnd_price(float(np.max(arr))),
        "is_reliable": n >= MIN_RELIABLE_COUNT,
    }


def remove_outliers(
    prices: Sequence[float], *, iqr_multiplier: float = OUTLIER_IQR_MULTIPLIER
) -> list[float]:
    arr = np.asarray(prices, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 4:
        return arr.tolist()
    q1, q3 = np.percentile(arr, [25, 75])
    iqr = q3 - q1
    lo, hi = q1 - iqr_multiplier * iqr, q3 + iqr_multiplier * iqr
    return arr[(arr >= lo) & (arr <= hi)].tolist()


def outlier_keep_mask(
    prices: Sequence[float], *, iqr_multiplier: float = OUTLIER_IQR_MULTIPLIER
) -> list[bool]:
    """행 단위 계산 후 연도·그룹으로 나눌 때 같은 인덱스에 대해 재사용."""
    raw_list = list(prices)
    n = len(raw_list)
    if n == 0:
        return []
    finite_idx: list[int] = []
    vals: list[float] = []
    out = [False] * n
    for i, x in enumerate(raw_list):
        try:
            fx = float(x)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(fx):
            continue
        finite_idx.append(i)
        vals.append(fx)

    if not vals:
        return out

    arr = np.asarray(vals, dtype=float)
    if len(arr) < 4:
        for i in finite_idx:
            out[i] = True
        return out

    q1, q3 = np.percentile(arr, [25, 75])
    iqr = q3 - q1
    lo, hi = q1 - iqr_multiplier * iqr, q3 + iqr_multiplier * iqr
    keep_val = ((arr >= lo) & (arr <= hi)).tolist()

    for j, ki in enumerate(finite_idx):
        if keep_val[j]:
            out[ki] = True
    return out


def _empty(n: int) -> dict:
    return {
        "count": n, "mean": None, "std": None, "ci_lower": None, "ci_upper": None,
        "min": None, "p25": None, "median": None, "p75": None, "max": None,
        "is_reliable": False,
    }


def _finite_or_none(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def stats_dict_from_sql_aggregates(
    n: int,
    mean_raw: float | None,
    std_samp_raw: float | None,
    min_raw: float | None,
    p25_raw: float | None,
    median_raw: float | None,
    p75_raw: float | None,
    max_raw: float | None,
) -> dict:
    """
    compute_stats 출력과 같은 키를 갖도록, PG 집계만으로 통계 행 하나를 만든다.
    (이상치 제거 전 순수 AVG / STDDEV_SAMP / percentile_cont 기준)
    """

    if n <= 0:
        return _empty(0)

    mean_f = _finite_or_none(mean_raw)
    std_raw = _finite_or_none(std_samp_raw)
    vmin = _finite_or_none(min_raw)
    q1 = _finite_or_none(p25_raw)
    med = _finite_or_none(median_raw)
    q3 = _finite_or_none(p75_raw)
    vmax = _finite_or_none(max_raw)

    ci_lower, ci_upper = None, None
    std_out = _rnd_price(std_raw) if std_raw is not None else None
    if n >= 2 and mean_f is not None and std_raw is not None:
        sem = float(std_raw) / (n ** 0.5)
        ci = st.t.interval(1 - ALPHA, df=n - 1, loc=float(mean_f), scale=sem)
        ci_lower = _finite_or_none(ci[0])
        ci_upper = _finite_or_none(ci[1])

    mean_out = _rnd_price(mean_f) if mean_f is not None else None

    return {
        "count": int(n),
        "mean": mean_out,
        "std": std_out,
        "ci_lower": _rnd_price(ci_lower) if ci_lower is not None else None,
        "ci_upper": _rnd_price(ci_upper) if ci_upper is not None else None,
        "min": _rnd_price(vmin) if vmin is not None else None,
        "p25": _rnd_price(q1) if q1 is not None else None,
        "median": _rnd_price(med) if med is not None else None,
        "p75": _rnd_price(q3) if q3 is not None else None,
        "max": _rnd_price(vmax) if vmax is not None else None,
        "is_reliable": int(n) >= MIN_RELIABLE_COUNT,
    }
