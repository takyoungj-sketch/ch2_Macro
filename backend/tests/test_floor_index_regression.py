"""효용지수 — 상가 층 구간·공장 면적대."""

import pandas as pd

from app.collective.floor_index_regression import compute_residential_floor_index_regression


def _base_rows(n: int, **cols) -> pd.DataFrame:
    data = {
        "unit_price": [100.0] * n,
        "exclusive_area": [50.0] * n,
        "building_age": [10.0] * n,
        "contract_year": [2024] * n,
        "contract_month": [3] * n,
        "floor": [1] * n,
    }
    data.update(cols)
    return pd.DataFrame(data)


def test_shop_basement_is_not_mid_floor():
    n = 18
    df = pd.concat(
        [
            _base_rows(n, unit_price=[90.0] * n, floor=[-1] * n),
            _base_rows(n, unit_price=[120.0] * n, floor=[1] * n),
            _base_rows(n, unit_price=[110.0] * n, floor=[2] * n),
        ],
        ignore_index=True,
    )
    raw = compute_residential_floor_index_regression(
        df, asset_type="collective_shop", dimension="floor"
    )
    labels = {c["label"] for c in raw["cells"] if c["count"] > 0}
    assert "지하1층" in labels
    assert "1층" in labels
    assert "2층" in labels
    assert "중층부" not in labels
    assert raw.get("floor_mode") == "shop"
    ref = next(c for c in raw["cells"] if c.get("is_reference"))
    assert ref["label"] == "1층"
    assert ref["index"] == 100.0


def test_factory_area_uses_100_300_1000_buckets():
    n = 16
    df = pd.concat(
        [
            _base_rows(n, exclusive_area=[50.0] * n, unit_price=[80.0] * n, floor=[1] * n),
            _base_rows(n, exclusive_area=[150.0] * n, unit_price=[100.0] * n, floor=[1] * n),
            _base_rows(n, exclusive_area=[400.0] * n, unit_price=[90.0] * n, floor=[1] * n),
            _base_rows(n, exclusive_area=[1200.0] * n, unit_price=[70.0] * n, floor=[1] * n),
        ],
        ignore_index=True,
    )
    raw = compute_residential_floor_index_regression(
        df, asset_type="collective_factory", dimension="area"
    )
    labels = {c["label"] for c in raw["cells"] if c["count"] > 0}
    assert "100㎡ 미만" in labels
    assert "100~300㎡" in labels
    assert "300~1000㎡" in labels
    assert "1000㎡ 이상" in labels
    assert "150㎡" not in labels
    assert "50㎡" not in labels


def test_residential_relative_floor_keeps_1_low_mid_high_top():
    n = 16
    df = pd.concat(
        [
            _base_rows(n, floor=[1] * n, unit_price=[100.0] * n),
            _base_rows(n, floor=[3] * n, unit_price=[105.0] * n),
            _base_rows(n, floor=[8] * n, unit_price=[110.0] * n),
            _base_rows(n, floor=[12] * n, unit_price=[115.0] * n),
            _base_rows(n, floor=[15] * n, unit_price=[120.0] * n),
        ],
        ignore_index=True,
    )
    raw = compute_residential_floor_index_regression(
        df, asset_type="apartment", dimension="floor", floor_mode="relative"
    )
    labels = {c["label"] for c in raw["cells"] if c["count"] > 0}
    assert "1층" in labels
    assert "최상층" in labels
    assert "지하1층" not in labels
    assert raw.get("floor_mode") == "relative"


def test_rowhouse_default_is_one_mid_top_not_apartment_bands():
    n = 16
    df = pd.concat(
        [
            _base_rows(n, floor=[1] * n, unit_price=[100.0] * n),
            _base_rows(n, floor=[3] * n, unit_price=[110.0] * n),
            _base_rows(n, floor=[5] * n, unit_price=[120.0] * n),
        ],
        ignore_index=True,
    )
    raw = compute_residential_floor_index_regression(
        df, asset_type="rowhouse", dimension="floor", floor_mode="relative"
    )
    labels = {c["label"] for c in raw["cells"] if c["count"] > 0}
    assert raw.get("floor_mode") == "rowhouse"
    assert labels == {"1층", "중간층", "최상층"}
    assert "저층부" not in labels
    assert "고층부" not in labels


def test_factory_floor_is_not_shop_ultra_high():
    n = 16
    df = pd.concat(
        [
            _base_rows(n, floor=[1] * n, unit_price=[100.0] * n),
            _base_rows(n, floor=[2] * n, unit_price=[90.0] * n),
            _base_rows(n, floor=[5] * n, unit_price=[80.0] * n),
        ],
        ignore_index=True,
    )
    raw = compute_residential_floor_index_regression(
        df, asset_type="collective_factory", dimension="floor"
    )
    labels = {c["label"] for c in raw["cells"] if c["count"] > 0}
    assert raw.get("floor_mode") == "factory"
    assert "1층" in labels
    assert "2층" in labels
    assert "3층 이상" in labels
    assert "초고층" not in labels
    assert "중층부" not in labels


def test_shop_area_uses_ledger_buckets_not_30m2():
    n = 12
    df = pd.concat(
        [
            _base_rows(n, exclusive_area=[20.0] * n, unit_price=[80.0] * n),
            _base_rows(n, exclusive_area=[40.0] * n, unit_price=[100.0] * n),
            _base_rows(n, exclusive_area=[80.0] * n, unit_price=[110.0] * n),
            _base_rows(n, exclusive_area=[200.0] * n, unit_price=[90.0] * n),
            _base_rows(n, exclusive_area=[400.0] * n, unit_price=[70.0] * n),
        ],
        ignore_index=True,
    )
    raw = compute_residential_floor_index_regression(
        df, asset_type="collective_shop", dimension="area"
    )
    labels = {c["label"] for c in raw["cells"] if c["count"] > 0}
    assert "35㎡ 미만" in labels
    assert "35~50㎡" in labels
    assert "50~100㎡" in labels
    assert "100~300㎡" in labels
    assert "300㎡ 이상" in labels
    assert "30㎡" not in labels
    assert "60㎡" not in labels


def test_relative_floor_uses_each_buildings_max():
    from app.collective.regression.engine import relative_floor_group, row_max_floors

    work = pd.DataFrame(
        {
            "building_key": ["A", "A", "B", "B", "B"],
            "floor": [1, 5, 1, 5, 25],
        }
    )
    maxes = row_max_floors(work)
    codes = [relative_floor_group(f, m) for f, m in zip(work["floor"], maxes)]
    assert codes[1] == "floor_rel_top"
    assert codes[3] == "floor_rel_low"
    assert float(maxes.iloc[1]) == 5
    assert float(maxes.iloc[3]) == 25
