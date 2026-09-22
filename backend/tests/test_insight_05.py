from app.ai.bundles.extractors import build_bundle
from app.ai.bundles.registry import resolve_bundle_id, suggested_questions
from app.ai.schemas import AiContext, AiScope


def test_insight_05_suggested_questions():
    qs = suggested_questions("Insight05", purpose="statistics", app="insight")
    assert any("GDP" in q for q in qs)
    assert any("1번" in q for q in qs)


def test_insight_05_bundle_not_01():
    ctx = AiContext(
        app="insight",
        panel="Insight05",
        purpose="statistics",
        scope=AiScope(region_label="전국"),
        facts={"as_of": "2026-09-22", "year_start": 2010, "year_end": 2024, "n_years": 15},
    )
    pack = build_bundle(ctx)
    assert pack.bundle_id == "insight_macro_05"
    assert resolve_bundle_id("Insight05") == "insight_macro_05"
    assert any("기여" in x or "이동" in x or "인과" in x for x in pack.limitations)
