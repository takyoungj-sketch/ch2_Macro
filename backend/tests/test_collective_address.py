from app.collective.address import format_jibun_address, format_road_address, split_building_addresses


def test_jibun_with_gu():
    assert (
        format_jibun_address(addr3="흥덕구", addr4="가경동", addr5="화산리", lot_number="123-4")
        == "가경동 화산리 123-4"
    )


def test_jibun_without_gu_ri_in_addr5():
    assert format_jibun_address(addr3="화산면", addr4=None, addr5="화산리", lot_number="12") == "화산면 화산리 12"


def test_jibun_without_gu_ri_in_addr4():
    assert format_jibun_address(addr3="화산면", addr4="화산리", addr5=None, lot_number="12") == "화산면 화산리 12"


def test_road_only():
    assert format_road_address(road_name="충청북도 청주시 흥덕로 123") == "충청북도 청주시 흥덕로 123"
    assert format_road_address(road_name=None) == "—"


def test_split():
    jibun, road, legacy = split_building_addresses(
        addr3="흥덕구",
        addr4="가경동",
        addr5=None,
        lot_number="1",
        road_name="청주시 흥덕로 1",
    )
    assert jibun == "가경동 1"
    assert road == "청주시 흥덕로 1"
    assert legacy == "가경동 1 (청주시 흥덕로 1)"
