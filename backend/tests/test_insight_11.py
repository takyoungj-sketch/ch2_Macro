from app.ai.bundles.extractors import build_bundle
from app.ai.bundles.registry import resolve_bundle_id, suggested_questions
from app.ai.knowledge.screen_guides import format_screen_guide
from app.ai.schemas import AiContext, AiScope


def test_insight_11_suggested_questions():
    qs = suggested_questions("Insight11", purpose="statistics", app="insight")
    assert any("소득+자본" in q for q in qs)
    assert any("국고채" in q for q in qs)
    assert any("KODEX" in q for q in qs)


def test_insight_11_bundle_not_01():
    ctx = AiContext(
        app="insight",
        panel="Insight11",
        purpose="statistics",
        scope=AiScope(region_label="전국"),
        facts={"as_of": "2025", "office_income_2025": 3.5, "apt_sum_2025": 4.42},
    )
    pack = build_bundle(ctx)
    assert pack.bundle_id == "insight_macro_11"
    assert resolve_bundle_id("Insight11") == "insight_macro_11"
    assert any("총수익" in x for x in pack.limitations)
    guide = format_screen_guide(ctx)
    assert "11번" in guide
    assert "오피스텔" in guide
    assert "KODEX" in guide
