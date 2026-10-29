from app.collective.region_name_search import map_sigungu_to_addr2
from app.flat_sido_region import FLAT_SIDO_ADDR2_TOKEN


def test_plain_gu_is_the_addr2():
    addr2, gu = map_sigungu_to_addr2("종로구", "서울특별시", ["종로구", "중구"])
    assert addr2 == "종로구"
    assert gu == ""


def test_city_gu_splits_into_addr2_and_gu():
    addr2, gu = map_sigungu_to_addr2("수원시 장안구", "경기도", ["수원시", "성남시"])
    assert addr2 == "수원시"
    assert gu == "장안구"


def test_flat_sido_when_sigungu_is_empty():
    addr2, gu = map_sigungu_to_addr2("", "세종특별자치시", [FLAT_SIDO_ADDR2_TOKEN])
    assert addr2 == FLAT_SIDO_ADDR2_TOKEN
    assert gu == ""
