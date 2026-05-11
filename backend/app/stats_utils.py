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
        ci_lower, ci_upper = float(ci[0]), float(ci[1])

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


def _empty(n: int) -> dict:
    return {
        "count": n, "mean": None, "std": None, "ci_lower": None, "ci_upper": None,
        "min": None, "p25": None, "median": None, "p75": None, "max": None,
        "is_reliable": False,
    }
