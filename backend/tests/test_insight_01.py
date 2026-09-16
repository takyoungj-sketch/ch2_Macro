from app.insight.public import public_insight_01


def test_public_insight_01_strips_lab_and_keeps_month():
    raw = {
        "lab": "macro_ts",
        "grain": "calendar_month",
        "default_rate": "cd_91",
        "periods": ["2011-01", "2026-08"],
        "lags": [0, 1, 3, 6],
        "types": ["토지", "합계"],
        "rates": {
            "cd_91": {
                "id": "cd_91",
                "label": "CD(91일)",
                "role": "short_market",
                "unit": "%",
                "values": [{"month": "2011-01", "v": 3.0}],
                "d_pp": [{"month": "2012-01", "v": -0.2}],
            }
        },
        "m2": {
            "label": "M2",
            "unit": "십억원",
            "values": [{"month": "2011-01", "v": 1.0}],
            "yoy_pct": [{"month": "2012-01", "v": 4.0}],
        },
        "series": {
            "합계": {
                "count": [{"month": "2011-01", "v": 10}],
                "amount": [{"month": "2011-01", "v": 100}],
                "yoy_count": [{"month": "2012-01", "v": -5}],
                "yoy_amount": [{"month": "2012-01", "v": -8}],
            }
        },
        "pairs": [{"type": "합계", "cd_91_count_lag0": {"n": 188, "r": -0.35, "lag": 0}}],
        "coverage_notes": ["note"],
        "missing": [],
    }
    out = public_insight_01(raw)
    assert "lab" not in out
    assert out["id"] == "01"
    assert out["status"] == "open"
    assert out["grain"] == "calendar_month"
    assert out["as_of"] == "2026-08"
    assert out["period_start"] == "2011-01"
    assert out["default_rate"] == "cd_91"
    assert out["rates"]["cd_91"]["d_pp"][0]["v"] == -0.2
    assert out["pairs"][0]["cd_91_count_lag0"]["r"] == -0.35
    assert "결론이 아니다" in out["note"]


def test_insight_suggested_questions():
    from app.ai.bundles.registry import suggested_questions

    qs = suggested_questions("Insight01", purpose="statistics", app="insight")
    assert any("상관계수" in q for q in qs)
    assert any("금리가 거래를 줄인" in q for q in qs)


def test_insight_bundle_not_regression():
    from app.ai.bundles.extractors import build_bundle
    from app.ai.schemas import AiContext, AiScope

    ctx = AiContext(
        app="insight",
        panel="Insight01",
        purpose="statistics",
        scope=AiScope(region_label="전국"),
        facts={"as_of": "2026-08", "pairs": [], "types": ["합계"]},
    )
    pack = build_bundle(ctx)
    assert pack.bundle_id == "insight_macro_01"
    assert any("인과" in x or "결론" in x for x in pack.limitations)
