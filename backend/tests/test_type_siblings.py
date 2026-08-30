"""같은 지번 아파트·오피스텔 sibling 페어링 (DB 없음)."""

from app.collective.type_siblings import lot_key, siblings_on_lot


def test_lot_key_strips():
    assert lot_key(" 4311311700 ", " 459 ") == ("4311311700", "459")
    assert lot_key("", "459") is None
    assert lot_key("4311311700", None) is None


def test_siblings_on_lot_pairs_apt_and_officetel():
    apt = "a" * 64
    ot = "b" * 64
    rows = [
        {
            "building_key": apt,
            "asset_type": "apartment",
            "display_name": "신해블루지움",
            "count": 157,
            "median": 280.0,
            "mean": 290.0,
        },
        {
            "building_key": ot,
            "asset_type": "officetel",
            "display_name": "신해블루지움",
            "count": 215,
            "median": 310.0,
            "mean": 305.0,
        },
    ]
    sibs = siblings_on_lot(asset_type="apartment", building_key=apt, lot_rows=rows)
    assert len(sibs) == 1
    assert sibs[0].asset_type == "officetel"
    assert sibs[0].count == 215
    assert sibs[0].median == 310.0

    back = siblings_on_lot(asset_type="officetel", building_key=ot, lot_rows=rows)
    assert len(back) == 1
    assert back[0].asset_type == "apartment"
    assert back[0].count == 157


def test_siblings_ignore_same_type_and_presale():
    apt = "a" * 64
    rows = [
        {"building_key": apt, "asset_type": "apartment", "display_name": "A", "count": 10},
        {"building_key": "c" * 64, "asset_type": "apartment", "display_name": "A2", "count": 8},
        {"building_key": "d" * 64, "asset_type": "presale", "display_name": "P", "count": 20},
    ]
    assert siblings_on_lot(asset_type="apartment", building_key=apt, lot_rows=rows) == []
