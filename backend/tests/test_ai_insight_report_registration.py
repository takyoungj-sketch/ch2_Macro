"""Published Insight pages retain their report-specific AI context, without API calls."""

import pytest

from app.ai.bundles.extractors import build_bundle
from app.ai.bundles.registry import resolve_bundle_id, suggested_questions
from app.ai.knowledge.screen_guides import format_screen_guide, screen_guide_followups
from app.ai.panel_capabilities import get_panel_capability
from app.ai.schemas import AiContext


@pytest.mark.parametrize("number,figure", [(13, "35.2%"), (14, "62.0%")])
def test_published_report_uses_its_own_bundle_and_guide(number, figure):
    panel = f"Insight{number}"
    bundle_id = f"insight_macro_{number}"
    context = AiContext(app="insight", panel=panel, facts={"as_of": "test-snapshot"})
    assert resolve_bundle_id(panel) == bundle_id
    assert get_panel_capability(panel).bundle_id == bundle_id
    bundle = build_bundle(context)
    assert bundle.bundle_id == bundle_id
    assert bundle.diagnostics["as_of"] == "test-snapshot"
    assert figure in " ".join(bundle.summary_lines)
    assert bundle.limitations
    assert figure in format_screen_guide(context)
    assert screen_guide_followups(context)
    assert suggested_questions(panel, app="insight")
