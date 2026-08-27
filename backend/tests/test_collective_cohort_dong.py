"""코호트 회귀: 같은 동 번호라도 단지가 다르면 별개 더미."""

from __future__ import annotations

import pandas as pd

from app.collective.regression.engine import (
    _build_design_matrix,
    _inputs_to_x_row,
    _nested_dong_col,
)
from app.collective.schemas import (
    CollectiveRegressionPredictInputs,
    CollectiveRegressionRequest,
    CollectiveRegressionSpec,
)


def _req() -> CollectiveRegressionRequest:
    return CollectiveRegressionRequest(
        asset_type="apartment",
        variables=CollectiveRegressionSpec(
            exclusive_area=False,
            building_age=False,
            floor=False,
            dong=True,
        ),
    )


def test_cohort_dong_dummies_are_nested_in_building():
    rows = []
    for dong, n in (("101동", 3), ("102동", 2)):
        for _ in range(n):
            rows.append(
                {
                    "building_key": "aaa",
                    "display_name": "A단지",
                    "dong": dong,
                    "price": 10000.0,
                    "floor": 5,
                }
            )
    for dong, n in (("101동", 3), ("102동", 2)):
        for _ in range(n):
            rows.append(
                {
                    "building_key": "bbb",
                    "display_name": "B단지",
                    "dong": dong,
                    "price": 11000.0,
                    "floor": 5,
                }
            )
    work = pd.DataFrame(rows)
    y, X, labels, meta, warnings = _build_design_matrix(
        work,
        _req(),
        cohort_mode=True,
        building_display_names={"aaa": "A단지", "bbb": "B단지"},
    )
    assert len(y) == 10
    col_a = _nested_dong_col("aaa", "102동")
    col_b = _nested_dong_col("bbb", "102동")
    assert col_a in X.columns
    assert col_b in X.columns
    assert col_a != col_b
    assert "dong_102동" not in X.columns
    assert labels[col_a] == "동 A단지 102동"
    assert labels[col_b] == "동 B단지 102동"
    assert meta.dong_reference_by_building["aaa"] == "101동"
    assert meta.dong_reference_by_building["bbb"] == "101동"
    assert any("단지별로 구분" in w for w in warnings)

    a102 = int(X[col_a].sum())
    b102 = int(X[col_b].sum())
    assert a102 == 2
    assert b102 == 2
    assert int((X[col_a] * X[col_b]).sum()) == 0


def test_cohort_predict_dong_uses_selected_building():
    rows = []
    for bk, name, price in (("aaa", "A단지", 10000.0), ("bbb", "B단지", 11000.0)):
        for dong, n in (("101동", 3), ("102동", 2)):
            for _ in range(n):
                rows.append(
                    {
                        "building_key": bk,
                        "display_name": name,
                        "dong": dong,
                        "price": price,
                        "floor": 5,
                    }
                )
    work = pd.DataFrame(rows)
    _, X, _, meta, _ = _build_design_matrix(
        work,
        _req(),
        cohort_mode=True,
        building_display_names={"aaa": "A단지", "bbb": "B단지"},
    )
    col_a = _nested_dong_col("aaa", "102동")
    col_b = _nested_dong_col("bbb", "102동")
    req = _req()

    row_a = _inputs_to_x_row(
        X,
        meta,
        req,
        CollectiveRegressionPredictInputs(dong="102동", building_key="aaa"),
    )
    assert row_a[col_a] == 1.0
    assert row_a[col_b] == 0.0

    row_b = _inputs_to_x_row(
        X,
        meta,
        req,
        CollectiveRegressionPredictInputs(dong="102동", building_key="bbb"),
    )
    assert row_b[col_a] == 0.0
    assert row_b[col_b] == 1.0

    row_ref = _inputs_to_x_row(
        X,
        meta,
        req,
        CollectiveRegressionPredictInputs(dong="101동", building_key="aaa"),
    )
    assert row_ref[col_a] == 0.0
    assert row_ref[col_b] == 0.0


def test_single_building_dong_dummy_unchanged():
    work = pd.DataFrame(
        [
            {"building_key": "aaa", "dong": "101동", "price": 10000.0, "floor": 5},
            {"building_key": "aaa", "dong": "101동", "price": 10100.0, "floor": 6},
            {"building_key": "aaa", "dong": "102동", "price": 9900.0, "floor": 4},
            {"building_key": "aaa", "dong": "102동", "price": 9800.0, "floor": 3},
        ]
    )
    _, X, labels, meta, _ = _build_design_matrix(work, _req(), cohort_mode=False)
    assert any(c.startswith("dong_") for c in X.columns)
    assert meta.dong_fe_map == {}
    assert "102동" in labels.get("dong_102동", "") or any("102" in v for v in labels.values())
