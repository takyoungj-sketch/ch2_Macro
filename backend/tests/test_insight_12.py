from app.ai.bundles.extractors import build_bundle
from app.ai.bundles.registry import resolve_bundle_id, suggested_questions
from app.ai.knowledge.screen_guides import format_screen_guide
from app.ai.schemas import AiContext, AiScope


def test_insight_12_suggested_questions():
    qs = suggested_questions("Insight12", purpose="statistics", app="insight")
    assert any("임대료" in q for q in qs)
    assert any("더 나은 투자" in q for q in qs)


def test_insight_12_bundle_not_11():
    ctx = AiContext(
        app="insight",
        panel="Insight12",
        purpose="statistics",
        scope=AiScope(region_label="전국"),
        facts={"as_of": "2025"},
    )
    pack = build_bundle(ctx)
    assert pack.bundle_id == "insight_macro_12"
    assert resolve_bundle_id("Insight12") == "insight_macro_12"
    assert any("읍면동" in x for x in pack.limitations)
    guide = format_screen_guide(ctx)
    assert "12번" in guide
    assert "매매가격지수" in guide
