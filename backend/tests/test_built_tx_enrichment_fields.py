from app.built.router import _apply_tx_enrichment_fields


def test_match_tier_preserved_when_present():
    out = _apply_tx_enrichment_fields(
        {
            "id": 1,
            "match_tier": "A1",
            "zone_type": "준주거",
            "transaction_hash": "deadbeef",
        },
        enrich=True,
    )
    assert out["match_tier"] == "A1"
    assert "transaction_hash" not in out


def test_match_tier_absent_stays_none():
    out = _apply_tx_enrichment_fields({"id": 1, "zone_type": "준주거"}, enrich=True)
    assert out.get("match_tier") is None


def test_match_tier_blank_becomes_none():
    out = _apply_tx_enrichment_fields({"id": 1, "match_tier": "  "}, enrich=True)
    assert out["match_tier"] is None
