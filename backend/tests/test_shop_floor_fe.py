"""집합상가 2층 회귀. 55·68을 대체하지 않는다."""
from __future__ import annotations

import pandas as pd

from app.shop_floor_lab.fe import fill_age, fit_both, group_use


def _trade(key, floor, price, *, age=10, year=None, contract_year=2024, use="근린생활시설", area=50):
    return {
        "cluster_key": key,
        "floor": floor,
        "unit_price": price,
        "gross_area": area,
        "building_age": age,
        "building_year": year,
        "contract_year": contract_year,
        "building_use": use,
    }


def test_age_fills_from_year_and_drops_the_rest():
    frame = pd.DataFrame(
        [
            _trade("a", 1, 100, age=None, year=2000, contract_year=2020),
            _trade("a", 2, 50, age=None, year=None),
        ]
    )
    filled = fill_age(frame)
    assert filled.iloc[0] == 20
    assert pd.isna(filled.iloc[1])


def test_rare_use_joins_other_and_modal_is_reference():
    uses = ["상점"] * 40 + ["학원"] * 10 + [None] * 5
    grouped, reference, other_n = group_use(pd.Series(uses))
    assert reference == "상점"
    assert other_n == 15
    assert set(grouped) == {"상점", "기타"}


def test_within_road_half_price_is_index_50():
    rows = []
    for i in range(6):
        for _ in range(4):
            rows.append(_trade(f"c{i}", 1, 100))
            rows.append(_trade(f"c{i}", 2, 50))
    payload = fit_both(pd.DataFrame(rows))
    assert payload["base_equal"] == 55.2
    assert payload["base_weighted"] == 68.1
    for fit in payload["fits"]:
        assert fit["ok"] is True
        assert fit["index"] == 50.0
        assert fit["includes_100"] is False
        assert fit["pct_vs_1f"] == -50.0


def test_cluster_weight_and_trade_weight_can_differ():
    rows = []
    for i in range(4):
        for _ in range(20):
            rows.append(_trade(f"big{i}", 1, 100))
            rows.append(_trade(f"big{i}", 2, 80))
        for _ in range(2):
            rows.append(_trade(f"small{i}", 1, 100))
            rows.append(_trade(f"small{i}", 2, 40))
    payload = fit_both(pd.DataFrame(rows))
    by = {fit["weight"]: fit["index"] for fit in payload["fits"]}
    assert by["trade"] > by["cluster"]
    assert by["trade"] < 100
    assert by["cluster"] < 100
    assert payload["index_gap_trade_minus_cluster"] == round(by["trade"] - by["cluster"], 1)
