import inspect

from app.collective.building_geocode import address_is_masked, build_building_query, geocode_collective_building
from app.rent.sql_fragments import building_key_sql
from app.rent.tx_query import _identity_clauses, _key_match_sql, list_building_transactions


def test_tx_lookup_hash_fallback_still_matches_mart_key():
    sql = _key_match_sql("t")
    assert "sha256" in sql
    assert "= :bk" in sql
    assert building_key_sql("t") in sql


def test_tx_list_prefers_stored_key_then_mart_identity():
    src = inspect.getsource(list_building_transactions)
    assert "_mart_identity" in src
    assert "t.building_key = :bk" in src
    assert "_key_match_sql" in src
    clauses, params = _identity_clauses(
        {
            "asset_type": "detached",
            "addr1": "충청북도",
            "addr2": "옥천군",
            "addr3": "군북면",
            "lot_number": "1**",
            "road_name": "",
        }
    )
    joined = " ".join(clauses)
    assert "sha256" not in joined
    assert "t.addr1 = :addr1" in joined
    assert "t.building_key = :bk" not in joined
    assert params["at"] == "detached"
    assert params["lot"] == "1**"


def test_masked_lot_is_not_geocoded():
    assert address_is_masked("군북면 1**")
    assert address_is_masked("충청북도 옥천군 군북면 1**")
    assert not address_is_masked("가경동 123")
    query = build_building_query(
        addr1="충청북도",
        addr2="옥천군",
        jibun_address="군북면 1**",
    )
    result = geocode_collective_building(
        api_key="unused",
        addr1="충청북도",
        addr2="옥천군",
        jibun_address="군북면 1**",
    )
    assert "*" in query
    assert result["ok"] is False
    assert result["error"] == "masked_address"
