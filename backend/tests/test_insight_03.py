from app.ai.bundles.extractors import build_bundle
from app.ai.bundles.registry import resolve_bundle_id, suggested_questions
from app.ai.schemas import AiContext, AiScope


def test_insight_03_suggested_questions():
    qs = suggested_questions("Insight03", purpose="statistics", app="insight")
    assert any("1층=100" in q for q in qs)
    assert any("13%" in q or "13.5" in q for q in qs)


def test_insight_03_bundle_not_01():
    ctx = AiContext(
        app="insight",
        panel="Insight03",
        purpose="statistics",
        scope=AiScope(region_label="전국"),
        facts={"as_of": "2026-08", "n_eligible": 1086, "pct_theta_top": 0.135},
    )
    pack = build_bundle(ctx)
    assert pack.bundle_id == "insight_macro_03"
    assert resolve_bundle_id("Insight03") == "insight_macro_03"
    assert any("13.5" in x or "인과" in x for x in pack.limitations)
