"""기존 설명·해석 어시스턴트의 검증 누락과 분석 이력 충돌 회귀 테스트."""
from unittest.mock import patch

from app.ai.knowledge.history import maybe_record, format_history_compare
from app.ai.knowledge.product import product_knowledge_excerpt, SANGKWON_REB
from app.ai.llm import numbers_preserved
from app.ai.orchestrator import handle_chat, handle_explain
from app.ai.schemas import AiChatRequest, AiContext, AiScope, AiExplainRequest
from app.ai.sessions import AiSession, get_or_create
from app.ai.validator import numbers_grounded


def context(coef=1, period="2025"):
    return AiContext(app="built", panel="RegressionCard",
        scope=AiScope(region_label="시험 지역", asset_type="상가", filters={"period": period}),
        facts={"n": 73, "adj_r_squared": 0.55, "mape": 0,
               "coefficients": [{"name": "면적", "coef": coef, "p": 0}]})


def test_polish_rejects_added_values_and_sign_changes():
    assert not numbers_preserved("표본 73건", "표본 73건, 수익률 999%")
    assert not numbers_preserved("계수 -0.5", "계수 0.5")
    assert not numbers_preserved("분석 없음", "표본 73건")
    assert numbers_preserved("표본 1,000건, 계수 -0.50", "계수 -0.5, 표본 1000건")


def test_numeric_guard_allows_labels_not_fabrication():
    assert numbers_grounded("1. CH2의 Adj R²는 0.55, 표본 73건입니다.", '{"n":73,"adj":0.55}')
    assert not numbers_grounded("표본 999건입니다.", '{"n":73}')
    assert not numbers_grounded("표본999건입니다.", '{"n":73}')
    assert not numbers_grounded("계수는-0.55입니다.", '{"coef":0.55}')
    assert numbers_grounded("설명력은 55%입니다.", '{"adj":0.55}')
    assert not numbers_grounded("설명력은 99%입니다.", '{"adj":0.55}')
    assert not numbers_grounded("설명력 55%, 표본 55건입니다.", '{"adj":0.55}')


def test_commercial_regression_does_not_route_to_reb():
    knowledge = product_knowledge_excerpt(app="built", panel="RegressionCard", message="상업용 부동산 회귀 결과는 어떻게 해석하나요?")
    assert "complete-case" in knowledge
    assert SANGKWON_REB.strip() not in knowledge
    assert "한국부동산원" in product_knowledge_excerpt(app="rent", panel="SangkwonCard", message="공실률 설명")


def test_history_keeps_conditions_coefficients_and_zero_metrics():
    session = AiSession("test-history", 0, 0)
    def record(ctx):
        return maybe_record(session, ctx, bundle_id="regression_diagnostic", diagnostics={"n": 73, "adj_r_squared": 0.55, "mape": 0})
    assert record(context())
    assert record(context()) is None
    assert record(context(coef=2))
    assert record(context(period="2026"))
    assert len(session.analysis_history) == 3
    assert session.analysis_history[0]["metrics"]["mape"] == 0
    assert session.analysis_history[-1]["scope"]["filters"] == {"period": "2026"}


def test_open_mode_validates_before_answer_enters_followup_memory(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "ai_open_mode", True)
    with patch("app.ai.orchestrator.open_mode_chat_completion", return_value="표본은 999건이며 반드시 오를 것입니다."):
        response = handle_chat(AiChatRequest(message="이 결과를 설명해주세요", context=context()))
    assert "999" not in response.answer
    assert "반드시 오를" not in response.answer
    assert not response.llm_used
    assert response.answer_context["scope"]["filters"]["period"] == "2025"
    assert get_or_create(response.session_id).turns[-1].message == response.answer[:500]


def test_different_model_scales_are_not_compared_as_coefficient_changes():
    session = AiSession("model-compare", 0, 0)
    for model in ("linear", "log-log"):
        ctx = context()
        ctx.facts["model_type"] = model
        maybe_record(session, ctx, bundle_id="regression_diagnostic", diagnostics={"n": 73})
    answer = format_history_compare(session.analysis_history)
    assert "조건이 다릅니다" in answer
    assert "방향은 동일" not in answer


def test_open_mode_keeps_grounded_answer_and_sanitizes_valuation(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "ai_open_mode", True)
    with patch("app.ai.orchestrator.open_mode_chat_completion", return_value="표본 73건입니다. 반드시 오를 것입니다."):
        response = handle_chat(AiChatRequest(message="이 결과를 설명해주세요", context=context()))
    assert "표본 73건" in response.answer
    assert "반드시 오를" not in response.answer
    assert response.llm_used


def test_explain_endpoint_rejects_unsupported_synthesized_numbers():
    with patch("app.ai.orchestrator.try_grounded_synthesis", return_value=("표본 999건입니다.", [], None, True)):
        response = handle_explain(AiExplainRequest(context=context()))
    assert "999" not in response.answer
    assert not response.llm_used
    assert response.answer_context["app"] == "built"
