"""백엔드에서 사용하는 통계 계산 유틸리티 (pipeline/stats.py 와 동일 로직)."""

from __future__ import annotations

from typing import Sequence

import numpy as np
import scipy.stats as st

ALPHA = 0.05
MIN_RELIABLE_COUNT = 15
OUTLIER_IQR_MULTIPLIER = 3.0


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
        "mean": round(mean, 0),
        "std": round(std, 0) if std is not None else None,
        "ci_lower": round(ci_lower, 0) if ci_lower is not None else None,
        "ci_upper": round(ci_upper, 0) if ci_upper is not None else None,
        "min": round(float(np.min(arr)), 0),
        "p25": round(float(np.percentile(arr, 25)), 0),
        "median": round(float(np.median(arr)), 0),
        "p75": round(float(np.percentile(arr, 75)), 0),
        "max": round(float(np.max(arr)), 0),
        "is_reliable": n >= MIN_RELIABLE_COUNT,
    }


def remove_outliers(prices: Sequence[float]) -> list[float]:
    arr = np.asarray(prices, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 4:
        return arr.tolist()
    q1, q3 = np.percentile(arr, [25, 75])
    iqr = q3 - q1
    lo, hi = q1 - OUTLIER_IQR_MULTIPLIER * iqr, q3 + OUTLIER_IQR_MULTIPLIER * iqr
    return arr[(arr >= lo) & (arr <= hi)].tolist()


def outlier_keep_mask(prices: Sequence[float]) -> list[bool]:
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
    lo, hi = q1 - OUTLIER_IQR_MULTIPLIER * iqr, q3 + OUTLIER_IQR_MULTIPLIER * iqr
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
    std_out = round(std_raw, 0) if std_raw is not None else None
    if n >= 2 and mean_f is not None and std_raw is not None:
        sem = float(std_raw) / (n ** 0.5)
        ci = st.t.interval(1 - ALPHA, df=n - 1, loc=float(mean_f), scale=sem)
        ci_lower = _finite_or_none(ci[0])
        ci_upper = _finite_or_none(ci[1])

    mean_out = round(mean_f, 0) if mean_f is not None else None

    return {
        "count": int(n),
        "mean": mean_out,
        "std": std_out,
        "ci_lower": round(ci_lower, 0) if ci_lower is not None else None,
        "ci_upper": round(ci_upper, 0) if ci_upper is not None else None,
        "min": round(vmin, 0) if vmin is not None else None,
        "p25": round(q1, 0) if q1 is not None else None,
        "median": round(med, 0) if med is not None else None,
        "p75": round(q3, 0) if q3 is not None else None,
        "max": round(vmax, 0) if vmax is not None else None,
        "is_reliable": int(n) >= MIN_RELIABLE_COUNT,
    }
