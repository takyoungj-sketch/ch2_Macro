from app.ai.bundles.extractors import build_bundle
from app.ai.bundles.registry import resolve_bundle_id, suggested_questions
from app.ai.schemas import AiContext, AiScope


def test_insight_04_suggested_questions():
    qs = suggested_questions("Insight04", purpose="statistics", app="insight")
    assert any("할인율" in q for q in qs)
    assert any("1,000" in q or "1000" in q for q in qs)


def test_insight_04_bundle_not_01():
    ctx = AiContext(
        app="insight",
        panel="Insight04",
        purpose="statistics",
        scope=AiScope(region_label="전국"),
        facts={"as_of": "2026-08", "n_comparable": 358, "n_lower": 175},
    )
    pack = build_bundle(ctx)
    assert pack.bundle_id == "insight_macro_04"
    assert resolve_bundle_id("Insight04") == "insight_macro_04"
    assert any("할인율" in x or "인과" in x for x in pack.limitations)
