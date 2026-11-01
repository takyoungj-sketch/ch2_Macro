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


def test_catalog_searches_flat_sido_and_keeps_dong_filter(monkeypatch):
    from app.collective import building_stats_query as query

    captured = []

    class Connection:
        def execute(self, statement, params):
            captured.append((str(statement), params))
            return self

        def mappings(self):
            return self

        def all(self):
            return [dict(building_key=key, display_name=key, addr3=dong, addr4=None,
                         year_from=2015, year_to=2016, total_count=10)
                    for key, dong in [("same", "고운동"), ("other", "아름동")]]

    monkeypatch.setattr(query, "building_addr_meta", lambda *_: dict(
        addr1="세종특별자치시", addr2="", addr3="고운동", addr4=None))
    monkeypatch.setattr(query, "_table_exists", lambda *_: True)
    monkeypatch.setattr(query, "_presale_road_lot", lambda *_: {})
    _, items = query.list_sigungu_presale_catalog(Connection(), "subject")
    assert [item["building_key"] for item in items] == ["same"]
    sql, params = captured[0]
    assert "addr2 IS NULL" in sql
    assert "btrim(addr2::text) = ''" in sql
    assert params["addr1"] == "세종특별자치시"


def test_catalog_keeps_regular_sigungu_scope(monkeypatch):
    from app.collective import building_stats_query as query

    class Connection:
        def execute(self, statement, params):
            assert "addr2 = :addr2" in str(statement)
            assert params["addr1"] == "부산광역시"
            assert params["addr2"] == "금정구"
            return self

        def mappings(self):
            return self

        def all(self):
            return []

    monkeypatch.setattr(query, "building_addr_meta", lambda *_: dict(
        addr1="부산광역시", addr2="금정구", addr3="구서동", addr4=None))
    monkeypatch.setattr(query, "_table_exists", lambda *_: True)
    monkeypatch.setattr(query, "_presale_road_lot", lambda *_: {})
    assert query.list_sigungu_presale_catalog(Connection(), "subject")[1] == []
