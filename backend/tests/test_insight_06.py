from app.ai.bundles.extractors import build_bundle
from app.ai.bundles.registry import resolve_bundle_id, suggested_questions
from app.ai.knowledge.screen_guides import format_screen_guide
from app.ai.schemas import AiContext, AiScope


def test_insight_06_suggested_questions():
    qs = suggested_questions("Insight06", purpose="statistics", app="insight")
    assert any("3분의 1" in q for q in qs)
    assert any("도시" in q for q in qs)


def test_insight_06_bundle_not_01():
    ctx = AiContext(
        app="insight",
        panel="Insight06",
        purpose="statistics",
        scope=AiScope(region_label="전국"),
        facts={"as_of": "2026-08", "ju_p50": 0.6521, "nok_p50": 0.4704},
    )
    pack = build_bundle(ctx)
    assert pack.bundle_id == "insight_macro_06"
    assert resolve_bundle_id("Insight06") == "insight_macro_06"
    assert any("3분의 1" in x or "도시" in x for x in pack.limitations)
    guide = format_screen_guide(ctx)
    assert "6번" in guide
    assert "도시 전체를 하나의 퍼센트" in guide
