from app.regional_profile.macro_ts_lab import _lag_pearson, _merge_mix, _rollup_calendar_year


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
    out = _lag_pearson(left, right, 1, grain="year")
    assert out["n"] == 3
    assert out["r"] is not None and out["r"] > 0.99


def test_rollup_calendar_year_sums_and_drops_partial():
    month = {
        "아파트": {
            201001: {"count": 1.0, "amount": 10.0},
            201002: {"count": 2.0, "amount": 20.0},
            **{201000 + m: {"count": 1.0, "amount": 1.0} for m in range(3, 13)},
            201101: {"count": 9.0, "amount": 90.0},
        }
    }
    notes: list[str] = []
    out = _rollup_calendar_year(month, notes)
    assert out["아파트"][2010]["count"] == 13.0
    assert 2011 not in out["아파트"]
    assert any("2011" in n for n in notes)


def test_lag_pearson_month_lag3():
    left = {201001: 1.0, 201004: 2.0, 201007: 3.0}
    right = {201004: 1.0, 201007: 2.0, 201010: 3.0}
    out = _lag_pearson(left, right, 3, grain="month")
    assert out["n"] == 3
    assert out["r"] is not None and out["r"] > 0.99
