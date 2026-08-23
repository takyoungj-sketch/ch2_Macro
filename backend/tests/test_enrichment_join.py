from app.built.enrichment_join import canonical_zone_label, wrap_tx_enrichment


def test_canonical_zone_drops_urban_and_matches_ledger():
    assert canonical_zone_label(["도시지역", "제2종일반주거지역"]) == "제2종일반주거"
    assert canonical_zone_label(["제2종일반주거지역", "도시지역"]) == "제2종일반주거"
    assert canonical_zone_label(["제3종일반주거지역, 도시지역"]) == "제3종일반주거"
    assert canonical_zone_label(["도시지역"]) is None
    assert canonical_zone_label(["계획관리지역", "농림지역"]) == "계획관리"
    assert canonical_zone_label(["일반상업지역"]) == "일반상업"
    assert canonical_zone_label(["개발제한구역"]) == "개발제한구역"
    assert canonical_zone_label(["nan"]) is None
    assert canonical_zone_label([]) is None


def test_wrap_sql_strips_coarse_and_지역_suffix():
    sql = wrap_tx_enrichment("SELECT transaction_hash, zone_type FROM built_transactions")
    assert "도시지역" in sql
    assert "regexp_replace(lab, '지역$', '')" in sql
    assert "s.zone_type IN" not in sql
    assert "z IN (" in sql
    assert "zone_type_filled" in sql
    assert "zone_type_first" in sql
    assert sql.count("zone_type_filled") == 1
