"""R2 — stage2 optimize mode (pool 재탐색, 식 고정 아님)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.built.regression.selection.blocks import BlockId
from app.built.regression.selection.context import SelectionContext, with_complete_case
from app.built.regression.selection.fit import fit_best_scale
from app.built.regression.selection.pooling import evaluate_pooling_candidates, filter_twins_by_hard_gates
from app.built.schemas import RegressionSelectionRequest


def _timed_rows(
    n: int,
    *,
    region_code: str,
    start_year: int,
    years: int,
    seed: int,
    noise_std: float,
) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        gross = 50 + (i % 20) * 2
        land = 30 + (i % 20)
        age = 5 + (i % 6)
        zone = ["Z1", "Z2", "Z3"][i % 3]
        base_price = 3000 + gross * 12 + land * 2 - age * 20 + (500 if zone == "Z2" else 0)
        rows.append(
            {
                "price": base_price + rng.normal(0, noise_std),
                "gross_area": gross,
                "land_area": land,
                "building_age": age,
                "road_width_label": "8m" if i % 2 == 0 else "12m",
                "zone_type": zone,
                "building_use": "근린",
                "asset_type": "commercial",
                "contract_year": start_year + (i % years),
                "eupmyeondong_code": region_code,
            }
        )
    return rows


class _FakePoolResult:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakePoolConn:
    def __init__(self, rows: list[dict], price_levels: dict[str, float] | None = None):
        self._rows = rows
        self._price_levels = price_levels or {}

    def execute(self, stmt, _params=None):
        if "median_psqm" in str(stmt):
            price_rows = [
                {"code": code, "median_psqm": value, "n": 999}
                for code, value in self._price_levels.items()
            ]
            return _FakePoolResult(price_rows)
        return _FakePoolResult(self._rows)


_POOL: list[BlockId] = ["gross_area", "land_area", "building_age", "zone_type"]


def test_filter_twins_by_hard_gates_returns_passed_codes():
    anchor = "11110250"
    twin = "11110251"
    local_rows = _timed_rows(10, region_code=anchor, start_year=2018, years=3, seed=1, noise_std=100)
    price_levels = {anchor: 100.0, twin: 120.0}
    gates, passed = filter_twins_by_hard_gates(
        _FakePoolConn(local_rows, price_levels=price_levels),
        req=RegressionSelectionRequest(
            profile_twin_neighbors=[{"region_code": twin, "similarity_score": 0.9}]
        ),
        anchor_region_codes=(anchor,),
        twin_region_codes=(twin,),
        admin_level="eupmyeondong",
    )
    assert len(gates) == 1
    assert passed == [twin]


def test_evaluate_pooling_optimize_returns_researched_blocks():
    anchor = "11110250"
    twin = "11110251"
    # local: land_area만 유효해 보이지만 잡음 큼
    local_rows = _timed_rows(12, region_code=anchor, start_year=2018, years=3, seed=1, noise_std=900)
    twin_rows = _timed_rows(60, region_code=twin, start_year=2018, years=3, seed=2, noise_std=40)
    all_rows = local_rows + twin_rows

    local_ctx = SelectionContext(
        df=pd.DataFrame(local_rows),
        scope_label="local",
        admin_level="eupmyeondong",
        addr4_city=False,
        mode="single",
        unified=False,
    )
    local_ctx = with_complete_case(local_ctx, _POOL, region_col=None)
    local_fit, _ = fit_best_scale(
        local_ctx.df, ["land_area"], unified=False, region_col=None, admin_level="eupmyeondong"
    )
    assert local_fit is not None

    price_levels = {
        anchor: sum(r["price"] / r["gross_area"] for r in local_rows) / len(local_rows),
        twin: sum(r["price"] / r["gross_area"] for r in twin_rows) / len(twin_rows),
    }

    result = evaluate_pooling_candidates(
        _FakePoolConn(all_rows, price_levels=price_levels),
        local_ctx=local_ctx,
        req=RegressionSelectionRequest(
            profile_twin_neighbors=[{"region_code": twin, "similarity_score": 0.9}]
        ),
        blocks=_POOL,
        local_fit=local_fit,
        anchor_region_codes=(anchor,),
        twin_region_codes=(twin,),
        admin_level="eupmyeondong",
        region_col=None,
        mode="optimize",
    )
    pool_metrics = next(c for c in result.candidates if c.candidate_id != "local")
    assert pool_metrics.blocks, "optimize mode must return researched blocks"
    assert pool_metrics.response_scale in {"linear", "log"}
