"""조회용 시군구 토큰은 외부 지도 주소에 전달하지 않는다."""
from app.collective import building_geocode
from app.collective_commercial import road_geocode
from app.flat_sido_region import FLAT_SIDO_ADDR2_TOKEN


def test_sejong_building_geocode_sends_real_address(monkeypatch):
    queries = []

    def lookup(key, query, categories):
        queries.append((query, categories))
        return (127.24, 36.50, "고운동 1706", "parcel")

    monkeypatch.setattr(building_geocode, "geocode_vworld_cached", lookup)
    result = building_geocode.geocode_collective_building(
        api_key="test", addr1="세종특별자치시", addr2=FLAT_SIDO_ADDR2_TOKEN,
        jibun_address="고운동 1706",
    )
    assert result["ok"]
    assert queries == [("세종특별자치시 고운동 1706", ("parcel", "road"))]


def test_sejong_commercial_geocode_sends_real_address(monkeypatch):
    queries = []

    def lookup(key, query):
        queries.append(query)
        return (127.24, 36.50, "마음로 92", "road")

    monkeypatch.setattr(road_geocode, "geocode_road_cached", lookup)
    result = road_geocode.geocode_commercial_road(
        api_key="test", addr1="세종특별자치시", addr2=FLAT_SIDO_ADDR2_TOKEN,
        addr3="고운동", road_name="마음로",
    )
    assert result["ok"]
    assert queries == ["세종특별자치시 고운동 마음로"]


def test_regular_sigungu_remains_in_address():
    assert building_geocode.build_building_query(
        addr1="부산광역시", addr2="금정구", jibun_address="구서동 100",
    ) == "부산광역시 금정구 구서동 100"
    assert road_geocode.build_road_query(
        addr1="부산광역시", addr2="금정구", road_name="중앙대로",
    ) == "부산광역시 금정구 중앙대로"
