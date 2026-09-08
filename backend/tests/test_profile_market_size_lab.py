from app.regional_profile.market_size_lab import (
    MIX_TYPES,
    pearson,
    residualize,
    _missing_price_types,
    _parent_sigungu,
    _within_pair_stats,
    _price_pair_stats,
    _within_price_pair_stats,
)


def test_pearson_perfect():
    r = pearson([1.0, 2.0, 3.0, 4.0], [2.0, 4.0, 6.0, 8.0])
    assert r is not None and abs(r - 1.0) < 1e-9


def test_pearson_too_short():
    assert pearson([1.0, 2.0], [1.0, 2.0]) is None


def test_residualize_removes_linear_pop():
    # y = 2x + 3, x = log pop stand-in
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [2 * x + 3 for x in xs]
    resid = residualize(ys, xs)
    assert resid is not None
    assert all(abs(v) < 1e-9 for v in resid)
    assert pearson(resid, xs) is None or abs(pearson(resid, xs) or 0) < 1e-9


def test_mix_types_eight():
    assert len(MIX_TYPES) == 8
    assert "아파트" in MIX_TYPES and "상가" in MIX_TYPES


def test_parent_sigungu():
    assert _parent_sigungu("eupmyeondong", "43113250") == "43113"
    assert _parent_sigungu("beopjungri", "4311325021") == "43113"
    assert _parent_sigungu("sigungu", "43113") == ""


def test_within_pair_keeps_within_group_relation():
    # 두 시군구. 그룹 안에서는 같이 움직이고, 그룹 평균은 다름.
    left = [10.0, 20.0, 40.0, 100.0, 200.0, 400.0]
    right = [10.0, 20.0, 40.0, 100.0, 200.0, 400.0]
    parents = ["A", "A", "A", "B", "B", "B"]
    pops = [None] * 6
    out = _within_pair_stats(left, right, parents, pops, use_log=True)
    assert out["n_parents"] == 2
    assert out["n"] == 6
    assert out["r"] is not None and out["r"] > 0.99


def test_within_pair_drops_between_group_only():
    # 그룹 안은 평평, 그룹 간에만 같이 큼 → within r 없음
    left = [10.0, 10.0, 10.0, 100.0, 100.0, 100.0]
    right = [10.0, 10.0, 10.0, 100.0, 100.0, 100.0]
    parents = ["A", "A", "A", "B", "B", "B"]
    out = _within_pair_stats(left, right, parents, [None] * 6, use_log=True)
    assert out["n"] == 6
    assert out["r"] is None  # 그룹 안 분산 0


def test_price_pair_no_pop_field():
    out = _price_pair_stats([1.0, 2.0, 4.0, 8.0], [1.0, 2.0, 4.0, 8.0])
    assert out["n"] == 4
    assert out["r"] is not None and out["r"] > 0.99
    assert "r_pop" not in out


def test_within_price_pair():
    left = [1.0, 2.0, 4.0, 10.0, 20.0, 40.0]
    right = [1.0, 2.0, 4.0, 10.0, 20.0, 40.0]
    out = _within_price_pair_stats(left, right, ["A", "A", "A", "B", "B", "B"])
    assert out["n_parents"] == 2
    assert out["r"] is not None and out["r"] > 0.99
    assert "r_pop" not in out


def test_missing_price_types_skips_empty_vectors():
    prices = {
        "상가": [None, None],
        "공장": [None, None],
        "단독다가구": [None, None],
        "아파트": [1.0, 2.0],
        "오피스텔": [3.0, None],
        "연립다세대": [None, 4.0],
        "분양권": [5.0, 6.0],
    }
    assert _missing_price_types(prices) == ["상가", "공장", "단독다가구"]
