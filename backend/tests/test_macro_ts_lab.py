from app.regional_profile.macro_ts_lab import _lag_pearson, _merge_mix


def test_merge_shop_adds_built_and_collective():
    land = {2010: {"count": 1.0, "amount": 10.0}}
    built = {"commercial": {2010: {"count": 2.0, "amount": 20.0}}, "factory": {}}
    cc = {"collective_shop": {2010: {"count": 3.0, "amount": 30.0}}}
    mixed = _merge_mix(land, built, cc, {})
    assert mixed["상가"][2010]["count"] == 5.0
    assert mixed["상가"][2010]["amount"] == 50.0
    assert mixed["토지"][2010]["count"] == 1.0
    assert mixed["합계"][2010]["count"] == 6.0


def test_lag_pearson_shifts_right():
    left = {2010: 1.0, 2011: 2.0, 2012: 3.0, 2013: 4.0}
    right = {2010: 0.0, 2011: 1.0, 2012: 2.0, 2013: 3.0}
    # lag 1: (1,1), (2,2), (3,3) — right[t+1]
    out = _lag_pearson(left, right, 1)
    assert out["n"] == 3
    assert out["r"] is not None and out["r"] > 0.99
