from app.rent.query import row_from_mart

_MART_METRICS = {
    "jeonse_n": 67,
    "jeonse_mean": 131,
    "jeonse_median": 126,
    "jeonse_ci_lower": 123,
    "jeonse_ci_upper": 139,
    "mixed_n": 18,
    "mixed_deposit_mean": 82,
    "mixed_deposit_median": 80,
    "mixed_deposit_ci_lower": 70,
    "mixed_deposit_ci_upper": 90,
    "mixed_monthly_mean": 1.2,
    "mixed_monthly_median": 1.1,
    "mixed_monthly_ci_lower": 1.0,
    "mixed_monthly_ci_upper": 1.4,
    "monthly_n": 0,
    "monthly_mean": None,
    "monthly_median": None,
    "monthly_ci_lower": None,
    "monthly_ci_upper": None,
}


def test_row_from_mart_parallel_types():
    row = row_from_mart(
        {
            "building_key": "abc",
            "asset_type": "apartment",
            "display_name": "한국그린",
            "addr3": "동송읍",
            "lot_number": "123",
            "road_name": "금학로 1",
            "building_year": 1995,
            **_MART_METRICS,
        }
    )
    assert row.jeonse.median == 126
    assert row.mixed.n == 18
    assert row.mixed.deposit.median == 80
    assert row.mixed.monthly.median == 1.1
    assert row.monthly.n == 0
    assert row.jibun_address.startswith("동송읍")


def test_row_from_mart_jibun_includes_ri_in_addr5():
    """구 없는 시: D-015로 리가 addr5로 승격된 뒤에도 매매와 같이 리를 붙인다."""
    row = row_from_mart(
        {
            "building_key": "songsan",
            "asset_type": "apartment",
            "display_name": "당진해링턴플레이스에듀타운",
            "addr3": "송산면",
            "addr4": "",
            "addr5": "유곡리",
            "lot_number": "1312",
            "road_name": "",
            "building_year": 2022,
            **_MART_METRICS,
        }
    )
    assert row.jibun_address == "송산면 유곡리 1312"


def test_row_from_mart_jibun_matches_sale_when_gu():
    row = row_from_mart(
        {
            "building_key": "cheongju",
            "asset_type": "apartment",
            "display_name": "가경단지",
            "addr3": "흥덕구",
            "addr4": "가경동",
            "addr5": None,
            "lot_number": "1",
            "road_name": "흥덕로 1",
            "building_year": 2010,
            **_MART_METRICS,
        }
    )
    assert row.jibun_address == "가경동 1"
