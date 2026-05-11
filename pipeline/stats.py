"""
통계 계산 함수
STAT_COLUMNS 순서에 맞춰 결과를 반환합니다.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import scipy.stats as st

from constants import ALPHA, MIN_RELIABLE_COUNT, OUTLIER_IQR_MULTIPLIER


def compute_stats(prices: Sequence[float]) -> dict:
    """
    단가 목록(원/㎡)을 받아 통계 딕셔너리를 반환한다.
    거래건수가 2건 미만이면 신뢰구간을 None으로 처리한다.
    """
    arr = np.asarray(prices, dtype=float)
    arr = arr[~np.isnan(arr)]
    n = len(arr)

    if n == 0:
        return _empty_stats()

    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if n >= 2 else None
    mn = float(np.min(arr))
    p25 = float(np.percentile(arr, 25))
    median = float(np.median(arr))
    p75 = float(np.percentile(arr, 75))
    mx = float(np.max(arr))

    ci_lower, ci_upper = None, None
    if n >= 2:
        se = st.sem(arr)
        ci = st.t.interval(1 - ALPHA, df=n - 1, loc=mean, scale=se)
        ci_lower = float(ci[0])
        ci_upper = float(ci[1])

    return {
        "count": n,
        "mean": round(mean, 0),
        "std": round(std, 0) if std is not None else None,
        "ci_lower": round(ci_lower, 0) if ci_lower is not None else None,
        "ci_upper": round(ci_upper, 0) if ci_upper is not None else None,
        "min": round(mn, 0),
        "p25": round(p25, 0),
        "median": round(median, 0),
        "p75": round(p75, 0),
        "max": round(mx, 0),
    }


def remove_outliers_iqr(prices: Sequence[float]) -> list[float]:
    """IQR 기반 이상치 제거 (유료 기능용)."""
    arr = np.asarray(prices, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 4:
        return arr.tolist()
    q1 = np.percentile(arr, 25)
    q3 = np.percentile(arr, 75)
    iqr = q3 - q1
    lower = q1 - OUTLIER_IQR_MULTIPLIER * iqr
    upper = q3 + OUTLIER_IQR_MULTIPLIER * iqr
    return arr[(arr >= lower) & (arr <= upper)].tolist()


def is_reliable(count: int) -> bool:
    """거래건수가 신뢰도 기준(15건)을 충족하는지 여부."""
    return count >= MIN_RELIABLE_COUNT


def _empty_stats() -> dict:
    return {
        "count": 0,
        "mean": None,
        "std": None,
        "ci_lower": None,
        "ci_upper": None,
        "min": None,
        "p25": None,
        "median": None,
        "p75": None,
        "max": None,
    }
