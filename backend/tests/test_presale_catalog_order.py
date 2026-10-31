from app.collective.building_stats_query import order_presale_catalog, same_dong_presale_items


def test_catalog_orders_by_name():
    items = [
        {"display_name": "나단지"},
        {"display_name": "가단지"},
        {"display_name": "다단지"},
    ]
    ordered = [row["display_name"] for row in order_presale_catalog(items)]
    assert ordered == ["가단지", "나단지", "다단지"]


def test_catalog_keeps_only_the_open_dong():
    items = [
        {"display_name": "개포", "dong": "개포동"},
        {"display_name": "대치", "dong": "대치동"},
    ]
    kept = [row["display_name"] for row in same_dong_presale_items(items, "개포동")]
    assert kept == ["개포"]
    assert same_dong_presale_items(items, "") == []
