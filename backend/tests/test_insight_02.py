from app.insight.public_02 import public_insight_02


def test_public_insight_02_strips_lab_and_share():
    raw = {
        "lab": "market_size",
        "window_years": 3,
        "region_level": "sigungu",
        "as_of_month": "2026-06-01",
        "n": 270,
        "universe_n": 258,
        "types": ["토지", "상가", "아파트"],
        "price_types": ["상가", "아파트"],
        "price_missing_types": ["토지"],
        "presence": [{"type": "아파트", "n_pos": 266, "pct": 0.9852}],
        "pairs": [
            {
                "a": "상가",
                "b": "아파트",
                "amount": {"n": 266, "r": 0.9212, "n_pop": 266, "r_pop": 0.5379},
                "count": {"n": 266, "r": 0.8564, "n_pop": 266, "r_pop": 0.2273},
                "share_amount": {"n": 266, "r": -0.4},
                "within_amount": {"n": 0, "r": None},
            }
        ],
        "price_pairs": [
            {
                "a": "상가",
                "b": "아파트",
                "price": {"n": 254, "r": 0.9066},
                "within_price": {"n": 0, "r": None},
            }
        ],
    }
    out = public_insight_02(raw)
    assert "lab" not in out
    assert out["id"] == "02"
    assert out["status"] == "open"
    assert out["grain"] == "sigungu"
    assert out["as_of"] == "2026-06-01"
    assert out["window_years"] == 3
    assert out["n"] == 270
    pair = out["pairs"][0]
    assert pair["amount"]["r"] == 0.9212
    assert pair["amount"]["r_pop"] == 0.5379
    assert "share_amount" not in pair
    assert "within_amount" not in pair
    assert out["price_pairs"][0]["r"] == 0.9066
    assert "within_price" not in out["price_pairs"][0]
    assert "구성비가 아니다" in out["note"]


def test_insight_02_suggested_questions():
    from app.ai.bundles.registry import suggested_questions

    qs = suggested_questions("Insight02", purpose="statistics", app="insight")
    assert any("인구" in q for q in qs)
    assert any("가격" in q or "단가" in q for q in qs)
    assert not any("금리" in q for q in qs)


def test_insight_02_bundle_not_time_series():
    from app.ai.bundles.extractors import build_bundle
    from app.ai.schemas import AiContext, AiScope

    ctx = AiContext(
        app="insight",
        panel="Insight02",
        purpose="statistics",
        scope=AiScope(region_label="전국"),
        facts={"as_of": "2026-06-01", "n": 270, "types": ["아파트", "상가"]},
    )
    pack = build_bundle(ctx)
    assert pack.bundle_id == "insight_macro_02"
    assert any("시군구" in x or "단면" in x for x in pack.summary_lines)
    assert any("인과" in x or "결론" in x for x in pack.limitations)
    joined = " ".join(pack.limitations)
    assert "시군구 r가 없습니다" not in joined
