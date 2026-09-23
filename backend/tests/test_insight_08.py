from app.ai.bundles.extractors import build_bundle
from app.ai.bundles.registry import resolve_bundle_id, suggested_questions
from app.ai.knowledge.screen_guides import format_screen_guide
from app.ai.schemas import AiContext, AiScope


def test_insight_08_suggested_questions():
    qs = suggested_questions("Insight08", purpose="statistics", app="insight")
    assert any("1층=100" in q for q in qs)
    assert any("가운데값" in q for q in qs)
    assert any("오피스텔" in q for q in qs)


def test_insight_08_bundle_not_01():
    ctx = AiContext(
        app="insight",
        panel="Insight08",
        purpose="statistics",
        scope=AiScope(region_label="전국"),
        facts={"as_of": "2026-08", "n_eligible": 6958},
    )
    pack = build_bundle(ctx)
    assert pack.bundle_id == "insight_macro_08"
    assert resolve_bundle_id("Insight08") == "insight_macro_08"
    assert any("오피스텔" in x or "연속" in x for x in pack.limitations)
    guide = format_screen_guide(ctx)
    assert "8번" in guide
    assert "108" in guide
    assert "저층=100" in guide
