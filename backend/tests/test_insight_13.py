from app.ai.bundles.extractors import build_bundle
from app.ai.bundles.registry import resolve_bundle_id, suggested_questions
from app.ai.knowledge.screen_guides import format_screen_guide
from app.ai.schemas import AiContext, AiScope


def test_insight_13_suggested_questions():
    qs = suggested_questions("Insight13", purpose="statistics", app="insight")
    assert any("건부감가" in q for q in qs)
    assert any("나지" in q for q in qs)


def test_insight_13_bundle_not_12():
    ctx = AiContext(
        app="insight",
        panel="Insight13",
        purpose="statistics",
        scope=AiScope(region_label="전국"),
        facts={"as_of": "2026-10-01"},
    )
    pack = build_bundle(ctx)
    assert pack.bundle_id == "insight_macro_13"
    assert resolve_bundle_id("Insight13") == "insight_macro_13"
    assert any("나지" in x for x in pack.limitations)
    guide = format_screen_guide(ctx)
    assert "35.2%" in guide
    assert "−12.8" in guide
