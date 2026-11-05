from app.ai.bundles.extractors import build_bundle
from app.ai.bundles.registry import resolve_bundle_id, suggested_questions
from app.ai.knowledge.screen_guides import format_screen_guide
from app.ai.schemas import AiContext, AiScope


def test_insight_14_suggested_questions():
    qs = suggested_questions("Insight14", purpose="statistics", app="insight")
    assert any("62.0%" in q for q in qs)
    assert any("같은 건물" in q for q in qs)


def test_insight_14_bundle_and_guide():
    ctx = AiContext(
        app="insight",
        panel="Insight14",
        purpose="statistics",
        scope=AiScope(region_label="전국"),
        facts={"as_of": "2026-10-01", "period_start": "2021-11-01", "period_end": "2026-10-31"},
    )
    pack = build_bundle(ctx)
    assert resolve_bundle_id("Insight14") == "insight_macro_14"
    assert pack.bundle_id == "insight_macro_14"
    guide = format_screen_guide(ctx)
    assert "62.0%" in guide
    assert "업무용" in guide
    assert "물리적 한 동" in guide
