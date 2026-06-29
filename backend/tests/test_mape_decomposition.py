"""verify_mape_decomposition.decompose_mape 단위 테스트."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import statsmodels.api as sm

_PIPELINE = Path(__file__).resolve().parents[2] / "pipeline" / "built"
sys.path.insert(0, str(_PIPELINE))

from verify_mape_decomposition import decompose_mape  # noqa: E402


def test_decompose_mape_low_price_tail():
    y = np.array([50000.0] * 90 + [2000.0, 3000.0, 1500.0, 2500.0, 1800.0])
    pred = y * 1.05
    pred[90:] = 50000.0  # low prices badly predicted
    x = sm.add_constant(np.arange(len(y), dtype=float))
    model = sm.OLS(y, x).fit()
    d = decompose_mape(y, pred, label="test", response_scale="linear", model=model)
    assert d.mape_overall_pct is not None
    assert d.mape_overall_pct > 50
    assert len(d.top_worst) >= 1
    assert d.top_worst[0]["pct_error"] > 100
