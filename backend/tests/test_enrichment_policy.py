from app.built.enrichment_join import wrap_tx_enrichment
from app.built.enrichment_policy import NOTICE, split_zone_filter
from app.built.router import _apply_tx_enrichment_fields


def test_notice_has_four_sentences():
    assert len(NOTICE) == 4
    assert "75.0%" in NOTICE[0]
    assert "서울" in NOTICE[3] and "충북" in NOTICE[3]


def test_split_zone_moves_to_outer_when_enrich():
    inner, outer = split_zone_filter(enrich=True, zone_types=["준주거"])
    assert inner is None
    assert outer == ["준주거"]
    inner2, outer2 = split_zone_filter(enrich=False, zone_types=["준주거"])
    assert inner2 == ["준주거"]
    assert outer2 is None


def test_wrap_skips_join_when_off():
    sql = wrap_tx_enrichment("SELECT transaction_hash, zone_type FROM t")
    assert "built_transaction_enrichment" not in sql


def test_wrap_filters_display_zone():
    sql = wrap_tx_enrichment(
        "SELECT transaction_hash, zone_type FROM t",
        enrich=True,
        zone_types=["준주거"],
    )
    assert "c.canon = ANY(:zone_types)" in sql
    assert "built_transaction_enrichment" in sql
    assert "e.match_rule" in sql
    assert "AS recovered_lot" in sql


def test_apply_fields_does_not_overwrite_zone_when_off():
    out = _apply_tx_enrichment_fields(
        {
            "zone_type": "준주거",
            "zone_type_filled": "제2종일반주거",
            "match_tier": "A1",
        },
        enrich=False,
    )
    assert out["zone_type"] == "준주거"
    assert out.get("match_tier") is None
    assert out["zone_source"] == "ledger"


def test_apply_fields_uses_filled_zone_when_on():
    out = _apply_tx_enrichment_fields(
        {
            "zone_type": "도시지역",
            "zone_type_filled": "제2종일반주거",
            "match_tier": "A1",
        },
        enrich=True,
    )
    assert out["zone_type"] == "제2종일반주거"
    assert out["zone_type_ledger"] == "도시지역"
    assert out["match_tier"] == "A1"
    assert out["zone_source"] == "title"
    assert out.get("recovered_lot") is None


def test_apply_fields_zone_source_ledger_when_suffix_only():
    out = _apply_tx_enrichment_fields(
        {
            "zone_type": "제2종일반주거지역",
            "zone_type_filled": "제2종일반주거",
            "match_tier": "A1",
            "match_rule": "gross_exact",
            "recovered_lot": "123-4",
        },
        enrich=True,
    )
    assert out["zone_type"] == "제2종일반주거"
    assert out["zone_source"] == "ledger"
    assert out["match_rule"] == "gross_exact"
    assert out["recovered_lot"] == "123-4"


def test_csv_omits_recovered_lot():
    from app.built.transaction_export import built_transactions_csv_bytes

    raw = built_transactions_csv_bytes(
        [
            {
                "asset_type": "commercial",
                "display_address": "청주",
                "zone_type": "준주거",
                "match_tier": "A1",
                "recovered_lot": "secret-lot",
                "price": 1,
            }
        ],
        asset_type="commercial",
    )
    text = raw.decode("utf-8-sig")
    assert "복원지번" not in text
    assert "secret-lot" not in text
    assert "대장확인" in text
    assert ",Y" in text or "Y\n" in text


def test_apply_fields_splits_recovered_lot_key():
    out = _apply_tx_enrichment_fields(
        {
            "zone_type": "준주거",
            "recovered_lot": "1111010100|146-6",
            "match_tier": "A1",
        },
        enrich=True,
    )
    assert out["recovered_lot"] == "146-6"


def test_apply_fields_hides_recovered_lot_when_off():
    out = _apply_tx_enrichment_fields(
        {"zone_type": "준주거", "recovered_lot": "146-6"},
        enrich=False,
    )
    assert "recovered_lot" not in out
