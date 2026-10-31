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
    assert "관측 최상층" in labels
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
    assert labels == {"1층", "중간층", "관측 최상층"}
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


def _cell(raw: dict, label: str) -> dict:
    return next(c for c in raw["cells"] if c["label"] == label)


def test_sparse_floor_is_excluded_and_does_not_move_the_index():
    plain = pd.concat(
        [
            _base_rows(40, floor=[1] * 40, unit_price=[100.0] * 40),
            _base_rows(80, floor=[2] * 80, unit_price=[120.0] * 80),
        ],
        ignore_index=True,
    )
    contaminated = pd.concat(
        [plain, _base_rows(4, floor=[9] * 4, unit_price=[500.0] * 4)],
        ignore_index=True,
    )
    before = compute_residential_floor_index_regression(
        plain, asset_type="apartment", dimension="floor", floor_mode="dummy"
    )
    after = compute_residential_floor_index_regression(
        contaminated, asset_type="apartment", dimension="floor", floor_mode="dummy"
    )
    assert _cell(before, "2층")["index"] == 120.0
    assert _cell(after, "2층")["index"] == 120.0
    ninth = _cell(after, "9층")
    assert ninth["index"] is None
    assert ninth["count"] == 0
    assert ninth["count_raw"] == 4


def test_missing_age_on_modal_floor_does_not_publish_an_index():
    missing = pd.concat(
        [
            _base_rows(40, floor=[1] * 40, unit_price=[100.0] * 40, building_age=[5.0] * 20 + [15.0] * 20),
            _base_rows(80, floor=[2] * 80, unit_price=[120.0] * 80, building_age=[None] * 80),
        ],
        ignore_index=True,
    )
    raw = compute_residential_floor_index_regression(
        missing, asset_type="apartment", dimension="floor", floor_mode="dummy"
    )
    second = _cell(raw, "2층")
    assert raw["method"] == "reference_only"
    assert raw["n_regression"] == 0
    assert second["count"] == 0
    assert second["count_raw"] == 80
    assert second["index"] is None
    assert _cell(raw, "1층")["index"] is None


def test_confidence_interval_is_against_the_display_floor():
    import numpy as np

    rng = np.random.default_rng(1)
    first = _base_rows(40, floor=[1] * 40, unit_price=rng.lognormal(np.log(100), 0.12, 40).tolist())
    second = _base_rows(80, floor=[2] * 80, unit_price=rng.lognormal(np.log(130), 0.12, 80).tolist())
    third = _base_rows(40, floor=[3] * 40, unit_price=rng.lognormal(np.log(110), 0.12, 40).tolist())
    raw = compute_residential_floor_index_regression(
        pd.concat([first, second, third], ignore_index=True),
        asset_type="apartment",
        dimension="floor",
        floor_mode="dummy",
    )
    ground = _cell(raw, "1층")
    modal = _cell(raw, "2층")
    upper = _cell(raw, "3층")
    assert ground["is_reference"] is True
    assert ground["index"] == 100.0
    assert ground["p_value"] is None
    assert modal["is_reference"] is False
    assert modal["p_value"] is not None
    assert modal["index_lo"] < modal["index"] < modal["index_hi"]
    assert abs(upper["index"] - round(float(np.exp(upper["gamma"]) * 100), 1)) < 0.05


def test_sparse_half_year_does_not_join_the_reference_period():
    main = pd.concat(
        [
            _base_rows(40, floor=[1] * 40, unit_price=[100.0] * 40),
            _base_rows(80, floor=[2] * 80, unit_price=[120.0] * 80),
        ],
        ignore_index=True,
    )
    thin = _base_rows(
        4,
        floor=[1] * 4,
        unit_price=[1000.0] * 4,
        contract_year=[2020] * 4,
        contract_month=[3] * 4,
    )
    raw = compute_residential_floor_index_regression(
        pd.concat([main, thin], ignore_index=True),
        asset_type="apartment",
        dimension="floor",
        floor_mode="dummy",
    )
    assert _cell(raw, "2층")["index"] == 120.0
    assert _cell(raw, "1층")["count_raw"] == 44
    assert _cell(raw, "1층")["count"] == 40


def test_age_collinear_with_half_years_is_dropped():
    frames = []
    for year, month in ((2023, 3), (2023, 9), (2024, 3), (2024, 9)):
        for floor, price in ((1, 100.0), (2, 120.0)):
            frames.append(
                _base_rows(
                    8,
                    floor=[floor] * 8,
                    unit_price=[price] * 8,
                    contract_year=[year] * 8,
                    contract_month=[month] * 8,
                    building_age=[float(year - 2000)] * 8,
                    building_year=[2000] * 8,
                )
            )
    raw = compute_residential_floor_index_regression(
        pd.concat(frames, ignore_index=True),
        asset_type="apartment",
        dimension="floor",
        floor_mode="dummy",
    )
    assert raw["method"] == "regression_semilog"
    assert "building_age" not in raw["controls"]
    assert _cell(raw, "2층")["index"] == 120.0


def test_sparse_building_does_not_join_the_reference_building():
    large = pd.concat(
        [
            _base_rows(40, floor=[1] * 40, unit_price=[100.0] * 40, building_key=["A"] * 40),
            _base_rows(40, floor=[2] * 40, unit_price=[120.0] * 40, building_key=["A"] * 40),
        ],
        ignore_index=True,
    )
    small = _base_rows(4, floor=[1] * 4, unit_price=[1000.0] * 4, building_key=["B"] * 4)
    raw = compute_residential_floor_index_regression(
        pd.concat([large, small], ignore_index=True),
        asset_type="apartment",
        dimension="floor",
        floor_mode="dummy",
    )
    assert _cell(raw, "2층")["index"] == 120.0
    assert _cell(raw, "1층")["count_raw"] == 44
    assert _cell(raw, "1층")["count"] == 40
