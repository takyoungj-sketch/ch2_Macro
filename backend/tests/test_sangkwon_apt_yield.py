from shapely.geometry import box

from app.sangkwon_apt_yield.build import intersecting_codes, mean_present, monthly_rent_manwon


def test_mean_skips_blank_years():
    avg, n = mean_present({2021: 4.0, 2022: None, 2023: 6.0, 2024: None, 2025: None})
    assert n == 2
    assert avg == 5.0


def test_rent_needs_four_quarters():
    assert monthly_rent_manwon({1: 10.0, 2: 10.0, 3: 10.0, 4: 10.0}) == 1.0
    assert monthly_rent_manwon({1: 10.0, 2: 10.0, 3: 10.0}) is None


def test_overlap_keeps_area_and_drops_touch():
    polys = [{"sec_nm": "가", "geom": box(0, 0, 2, 2)}]
    emds = [
        ("11111111", box(1, 1, 3, 3)),
        ("22222222", box(2, 0, 4, 2)),
    ]
    assert intersecting_codes(polys, emds)["가"] == ["11111111"]
