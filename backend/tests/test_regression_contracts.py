import numpy as np
import pandas as pd

from app.regression_contracts import build_analysis_context, observation_signature, signature
from app.regression_contracts import grouped_sample_details


def test_group_details_count_actual_fit_and_never_fill_missing_or_time_varying_attributes():
    source = pd.DataFrame(dict(building_key=["a", "a", "b", "b", "c"],
        households=[100, 100, 200, 200, 300], parking=[1., 1., 2., np.nan, 3.],
        assessed=[1000, 1200, 2000, 2000, 3000]))
    groups = grouped_sample_details(source, source.iloc[:4], key="building_key",
        labels={"a": "가단지", "b": "나단지"}, reference="a", effects=["b"],
        attributes=["households", "parking", "assessed"])
    assert sum(g["source_n"] for g in groups) == 5
    assert sum(g["fit_n"] for g in groups) == 4
    assert [g["fe_state"] for g in groups] == ["reference", "estimated", "no_fit"]
    assert groups[0]["confirmed_attributes"] == {"households": 100, "parking": 1.}
    assert groups[1]["confirmed_attributes"] == {"households": 200, "assessed": 2000}
    assert groups[2]["confirmed_attributes"] == {}


def context(rows, **kwargs):
    return build_analysis_context(request={"variables": {"region_leaf_dummy": True, "gross_area": True}},
        rows=rows, coefficients=[{"name": "const"}, {"name": "gross_area"}],
        observation_unit="transaction", target="price", target_unit="만원", response_scale="log",
        fit_n=len(rows), **kwargs)


def test_identity_requires_observation_id_and_preserves_duplicates():
    assert observation_signature(pd.DataFrame({"price": [1, 2]})) is None
    a = pd.DataFrame({"transaction_id": [1, 2, 2]})
    assert observation_signature(a) == observation_signature(a.iloc[::-1])
    assert observation_signature(a) != observation_signature(a.drop_duplicates())
    assert observation_signature(pd.DataFrame({"transaction_id": [1, 3, 3]})) != observation_signature(a)


def test_same_n_different_rows_changes_signature_and_unknown_variable_is_not_in_model():
    rows = pd.DataFrame({"price": [1., 2.]})
    a, b = context(rows), context(pd.DataFrame({"price": [1., 3.]}))
    assert a.data_signature != b.data_signature
    assert a.fit_sample_signature is None
    assert a.data_signature == context(rows.iloc[::-1]).data_signature
    assert [(v.name, v.state) for v in a.variables] == [("region_leaf_dummy", "not_in_model"), ("gross_area", "included")]


def test_unavailable_metric_is_distinct_from_zero_and_rank_is_actual():
    c = context(pd.DataFrame({"id": [1, 2]}), exog=np.ones((2, 2)), metrics=[
        dict(key="mape", role="training", scale="price", value=0.),
        dict(key="mape", role="selection_validation", scale="price", value=None),
    ])
    assert c.design_rank == 1
    assert c.metrics[0].status == "available"
    assert c.metrics[1].status == "unavailable"
    assert c.metrics[1].reason
    assert signature({"a": np.nan}) == signature({"a": None})


def test_model_identity_does_not_change_with_input_or_display_only_fields():
    rows = pd.DataFrame({"id": [1, 2], "price": [10., 20.]})
    base = dict(rows=rows, observation_unit="transaction", target="price", target_unit="만원",
        response_scale="log", fit_n=2)
    fit = build_analysis_context(**base, request={"variables": {"gross_area": True}},
        coefficients=[dict(name="gross_area", estimate=1.)])
    pred = build_analysis_context(**base, request={"inputs": {"area": 80}, "expected_model_signature": "abc"},
        coefficients=[dict(name="gross_area", coef=1., label="설명 변경")])
    assert fit.model_signature == pred.model_signature
    assert "inputs" not in pred.conditions
