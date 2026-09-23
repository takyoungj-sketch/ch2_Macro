from app.ai.bundles.extractors import build_bundle
from app.ai.bundles.registry import resolve_bundle_id, suggested_questions
from app.ai.knowledge.screen_guides import format_screen_guide
from app.ai.schemas import AiContext, AiScope


def test_insight_10_suggested_questions():
    qs = suggested_questions("Insight10", purpose="statistics", app="insight")
    assert any("시세" in q for q in qs)
    assert any("55" in q and "68" in q for q in qs)
    assert any("아파트" in q for q in qs)


def test_insight_10_bundle_not_08():
    ctx = AiContext(
        app="insight",
        panel="Insight10",
        purpose="statistics",
        scope=AiScope(region_label="전국"),
        facts={"as_of": "2026-08", "n_roads_area": 89},
    )
    pack = build_bundle(ctx)
    assert pack.bundle_id == "insight_macro_10"
    assert resolve_bundle_id("Insight10") == "insight_macro_10"
    assert any("원인" in x for x in pack.limitations)
    guide = format_screen_guide(ctx)
    assert "10번" in guide
    assert "55" in guide and "68" in guide
    assert "108" in guide
