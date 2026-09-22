from app.ai.bundles.extractors import build_bundle
from app.ai.bundles.registry import resolve_bundle_id, suggested_questions
from app.ai.knowledge.screen_guides import format_screen_guide
from app.ai.schemas import AiContext, AiScope


def test_insight_07_suggested_questions():
    qs = suggested_questions("Insight07", purpose="statistics", app="insight")
    assert any("91.4%" in q for q in qs)
    assert any("전국" in q for q in qs)
    assert any("n=3" in q for q in qs)


def test_insight_07_bundle_not_01():
    ctx = AiContext(
        app="insight",
        panel="Insight07",
        purpose="statistics",
        scope=AiScope(region_label="전국"),
        facts={"algorithm": 21, "window_years": 3},
    )
    pack = build_bundle(ctx)
    assert pack.bundle_id == "insight_macro_07"
    assert resolve_bundle_id("Insight07") == "insight_macro_07"
    assert any("같은 시장" in x for x in pack.limitations)
    guide = format_screen_guide(ctx)
    assert "7번" in guide
    assert "권역" in guide
    assert "CV-MAPE" in guide
    assert "모든 지역에서 줄었다고 말하지 않습니다" in guide
    assert "19%" not in guide
