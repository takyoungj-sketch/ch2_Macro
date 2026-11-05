import json

import pytest

from app.ai.orchestrator import handle_chat
from app.ai.schemas import AiChatRequest, AiContext, AiScope


def regression(region="지역 A", coef=-0.24, **extra):
    return AiContext(
        app="land", panel="LandRegressionTab", scope=AiScope(region_label=region),
        facts={
            "n": 120,
            "adj_r_squared": 0.528,
            "model_type": "log",
            "coefficients": [{"name": "log_area", "label": "log(면적)", "coef": coef}],
            "correlations": [{"label": "면적", "pearson_r": -0.17, "points": [{"x": 7019, "y": 7}]}],
            **extra,
        },
    )


def ask(message, context, session_id=None):
    return handle_chat(AiChatRequest(message=message, context=context, session_id=session_id))


def fake_model(monkeypatch, choose):
    def draft(*, user, system, json_response, timeout=45):
        assert json_response
        kind, answer = choose(json.loads(user))
        return json.dumps({"kind": kind, "answer": answer}, ensure_ascii=False)

    monkeypatch.setattr("app.ai.dialogue.llm._openai_chat", draft)


def reference(payload, label, source="current"):
    return next(key for key, fact in payload["sources"][source]["facts"].items() if fact.startswith(label))


def test_screen_reply_uses_labeled_coefficient_and_omits_raw_transactions(monkeypatch):
    def choose(payload):
        assert "7019" not in str(payload)
        assert payload["sources"]["current"]["context"]["종속변수"] == "log(토지 단가)"
        fact = reference(payload, "log(면적) 계수")
        return "screen", "다른 조건이 같을 때, {{" + fact + "}}는 면적과 단가의 음의 관계를 뜻합니다."

    fake_model(monkeypatch, choose)
    result = ask("면적 계수는 무슨 뜻이야?", regression())
    assert result.llm_used
    assert "log(면적) 계수 -0.24" in result.answer
    assert "120" not in result.answer
    assert result.evidence[0].ref == "current.f2"
    assert not result.suggested_followups


@pytest.mark.parametrize("answer", [
    "표본은 0.528건이고 조정 R²는 120입니다.",
    "{{previous.f0}}입니다.",
    "{{current.f0}}%입니다.",
    "단가는 올랐습니다.",
])
def test_invalid_screen_claim_does_not_reach_answer(monkeypatch, answer):
    fake_model(monkeypatch, lambda _: ("screen", answer))
    result = ask("이 결과가 뭐야?", regression())
    assert result.evidence
    assert answer not in result.answer


def test_unusable_model_reply_does_not_dump_metrics(monkeypatch):
    fake_model(monkeypatch, lambda _: ("screen", "{{current.f2}}퍼센트입니다."))
    result = ask("면적 계수는 무슨 뜻이야?", regression())
    assert result.evidence
    assert "log(면적) 계수" not in result.answer
    assert "120" not in result.answer
    assert not result.llm_used


def test_negated_statistical_misconception_is_not_blocked_by_keywords(monkeypatch):
    fake_model(monkeypatch, lambda _: ("screen", "{{current.f3}}가 크다고 우연일 가능성이 크다는 뜻은 아닙니다."))
    context = regression(coefficients=[{"name": "log_area", "coef": -0.24, "p": 0.68}])
    result = ask("이 결과의 p값은 무슨 뜻이야?", context)
    assert result.llm_used and "뜻은 아닙니다" in result.answer


def test_analysis_suggestion_is_not_blocked_by_question_keywords(monkeypatch):
    fake_model(monkeypatch, lambda _: ("screen", "{{current.f2}}입니다. 다른 종속변수의 실제 결과를 비교하려면 별도 모형을 적합해야 합니다."))
    result = ask("총가격을 종속변수로 적합한 결과와 비교하려면?", regression())
    assert result.llm_used and "별도 모형" in result.answer


def test_followups_and_screen_changes_select_distinct_sources(monkeypatch):
    def choose(payload):
        question = payload["question"]
        sources = payload["sources"]
        if "비교" in question:
            assert set(sources) == {"current", "previous"}
            return "screen", "{{previous.f2}}와 {{current.f2}}입니다."
        if question.startswith(("그럼", "그런데")) or "아까" in question:
            assert set(sources) == {"current", "previous"}
            assert "-0.24" not in str(payload["conversation"])
            return "screen", "{{previous.f2}}입니다. 단가의 조건부 관계만으로 규모의 경제를 판단할 수는 없습니다."
        assert "current" in sources
        return "screen", "{{current.f2}}입니다."

    fake_model(monkeypatch, choose)
    first = ask("면적 계수는 무슨 뜻이야?", regression())
    for question in (
        "그럼 큰 토지는 더 싸다는 거야?",
        "그런데 실제 거래에서는 큰 토지가 더 비싸지 않아?",
        "그럼 규모의 경제가 있는 거네?",
    ):
        response = ask(question, regression("지역 B", 0.35), first.session_id)
        assert "지역 A" in response.answer and "0.35" not in response.answer
    compare = ask("아까 모형과 비교해줘", regression("지역 B", 0.35), first.session_id)
    assert "지역 A" in compare.answer and "지역 B" in compare.answer
    current = ask("이 표의 면적 계수는?", regression("지역 B", 0.35), first.session_id)
    assert "0.35" in current.answer and "-0.24" not in current.answer


def test_stale_result_cannot_be_used_for_current_conditions(monkeypatch):
    def choose(payload):
        assert payload["sources"]["current"]["facts"] == {}
        return "screen", "{{current.f0}}입니다."

    fake_model(monkeypatch, choose)
    result = ask("지금 계수가 어떻게 돼?", regression(controls_changed=True))
    assert not result.llm_used
    assert "다시 실행" in result.answer


def test_trend_uses_displayed_metric_and_its_own_scope(monkeypatch):
    def choose(payload):
        facts = payload["sources"]["current"]["facts"]
        assert list(facts.values()) == ["지역 B 2024년 단가 중앙값 51만원/㎡", "지역 B 2024년 거래 수 32건"]
        return "screen", "{{current.f0}}입니다."

    fake_model(monkeypatch, choose)
    response = ask("이 추세에서 보이는 값은?", AiContext(
        app="land", panel="TrendCard", scope=AiScope(region_label="지역 B"),
        facts={"trend_metric": "median", "series": [{"region_name": "지역 B", "points": [
            {"year": 2024, "median": 51, "mean": 73, "count": 32},
        ]}]},
    ))
    assert "51만원/㎡" in response.answer and "73" not in response.answer
    assert response.evidence[0].type == "ch2_trend"


def test_floor_index_screen_passes_the_visible_table(monkeypatch):
    def choose(payload):
        facts = payload["sources"]["current"]["facts"]
        assert facts["current.f0"].startswith("조회 거래")
        assert any(fact.startswith("저층부 p값") for fact in facts.values())
        assert "기준 구간은 중층부" in " ".join(payload["sources"]["current"]["notes"])
        return "screen", "{{current.f0}}입니다."

    fake_model(monkeypatch, choose)
    result = ask("저층부 p값은?", AiContext(
        app="collective", panel="FloorIndexPanel", scope=AiScope(region_label="힐스테이트태전"),
        facts={
            "n_total": 121, "n_regression": 114, "reference_floor": "중층부",
            "regression_reference_floor": "중층",
            "warnings": ["1층이 최종 회귀 표본에 없습니다."],
            "cells": [
                {"label": "저층부", "count_raw": 32, "count": 30, "p_value": 0.806, "index": 98.2},
                {"label": "중층부", "count_raw": 61, "count": 57, "is_reference": True, "index": 100},
            ],
        },
    ))
    assert result.llm_used and "조회 거래 121건" in result.answer


def test_building_screen_is_described_as_trade_regression_not_regional():
    from app.ai.dialogue import _screen

    evidence = _screen(AiContext(
        app="collective", panel="BuildingRegressionPanel",
        facts={"cohort": False, "n": 121, "r_squared": 0.932},
    ))
    text = " ".join(evidence.notes)
    assert "거래 회귀" in text and "지역회귀" in text and "중앙단가" in text
    assert evidence.facts == []


def test_unrelated_meal_is_refused_without_the_model(monkeypatch):
    def boom(**kwargs):
        raise AssertionError("model called")

    monkeypatch.setattr("app.ai.dialogue.llm._openai_chat", boom)
    result = ask("오늘 저녁 메뉴 추천해줘", regression())
    assert result.route == "refusal" and not result.llm_used
    assert "통계 밖" in result.answer


def test_p_value_is_withheld_until_the_user_asks(monkeypatch):
    def choose(payload):
        facts = " ".join(payload["sources"]["current"]["facts"].values())
        assert "p값" not in facts
        return "knowledge", "이 표본에서는 면적이 크면 단가가 낮게 연관됩니다."

    fake_model(monkeypatch, choose)
    result = ask(
        "면적 계수가 음수면 단가가 낮다는 거지?",
        regression(coefficients=[{"name": "log_area", "label": "log(면적)", "coef": -0.24, "p": 0.001}]),
    )
    assert result.llm_used and "p값" not in result.answer


def test_repeated_metric_name_is_inserted_once(monkeypatch):
    def choose(payload):
        key = next(k for k, fact in payload["sources"]["current"]["facts"].items() if fact.startswith("조정 R²"))
        return "screen", "조정 R² = {{" + key + "}}입니다."

    fake_model(monkeypatch, choose)
    result = ask("조정 R²가 0.528이면 잘 맞춘 거야?", regression())
    assert result.answer.count("조정 R²") == 1


def test_unasked_cause_list_is_removed(monkeypatch):
    def once(*, user, system, json_response, timeout=45):
        assert json_response
        return json.dumps({
            "kind": "knowledge",
            "answer": "맞습니다. 단가가 낮아집니다.\n\n원인에 대한 가설:\n- 외곽일 수 있습니다.\n\n인과는 아닙니다.",
        }, ensure_ascii=False)

    monkeypatch.setattr("app.ai.dialogue.llm._openai_chat", once)
    result = ask("면적 계수가 음수면 단가가 낮다는 거지?", regression())
    assert "가설" not in result.answer and "외곽" not in result.answer
    assert "인과는 아닙니다" in result.answer


def test_wrong_scale_agreement_is_not_sent(monkeypatch):
    calls = {"n": 0}

    def draft(*, user, system, json_response, timeout=45):
        calls["n"] += 1
        assert json_response
        text = "맞습니다. 규모의 경제가 관찰됩니다." if calls["n"] == 1 else "아니요. 단가 연관과 규모의 경제는 다릅니다."
        return json.dumps({"kind": "knowledge", "answer": text}, ensure_ascii=False)

    monkeypatch.setattr("app.ai.dialogue.llm._openai_chat", draft)
    result = ask("그럼 규모의 경제가 있는 거네?", regression())
    assert result.answer.startswith("아니요")
    assert calls["n"] == 2


def test_rules_reject_only_unrelated_questions_and_apply_to_every_app(monkeypatch):
    seen = {}

    def draft(*, user, system, json_response, timeout=45):
        seen["system"] = system
        assert json_response
        return json.dumps({"kind": "knowledge", "answer": "이 질문에는 화면 숫자 없이 답할 수 있어요."}, ensure_ascii=False)

    monkeypatch.setattr("app.ai.dialogue.llm._openai_chat", draft)
    result = ask("이 계수 해석이 맞아?", AiContext(app="built", panel="RegressionCard", scope=AiScope(region_label="서동")))
    assert result.llm_used and result.route == "ch2"
    assert "무관한 질문뿐" in seen["system"]
    assert "두세 문장" not in seen["system"]
    assert "질문마다 다른 답안" in seen["system"]


def test_cross_app_and_general_statistics_use_dialogue(monkeypatch):
    def choose(payload):
        if "임대" in payload["question"]:
            assert "전환율" in payload["product_knowledge"][0]
            return "knowledge", "임대 화면에서 전환율 분석을 열 수 있어요."
        return "knowledge", "교란변수는 설명변수와 결과 모두에 관련돼 둘의 관계를 다르게 보이게 할 수 있어요."

    fake_model(monkeypatch, choose)
    result = ask("임대의 전환율은 어디서 봐?", regression())
    assert result.llm_used and result.answer.startswith("임대")
    result = ask("교란변수가 뭐야?", regression(), result.session_id)
    assert result.llm_used and result.answer.startswith("교란변수")


@pytest.mark.parametrize(("question", "kind", "answer"), [
    ("이 땅의 적정가격을 알려줘", "refusal", "개별 적정가격은 판단하지 않아요. 통계 해석은 도와드릴 수 있어요."),
    ("너는 누구지?", "knowledge", "CH2 분석을 함께 살펴보는 AI 어시스턴트예요."),
    ("금리와 부동산 시장은 어떤 관계야?", "knowledge", "금리는 차입 비용과 수요를 통해 부동산 시장에 영향을 줄 수 있어요."),
    ("유의수준 0.05는 무슨 의미야?", "knowledge", "유의수준 0.05는 귀무가설이 참일 때 이를 잘못 기각할 확률의 기준이에요."),
])
def test_scope_and_style_are_model_decisions(monkeypatch, question, kind, answer):
    fake_model(monkeypatch, lambda _: (kind, answer))
    result = ask(question, regression())
    assert result.llm_used
    assert result.answer == answer
    assert result.route == ("refusal" if kind == "refusal" else "ch2")


def test_previous_evidence_available_without_followup_keywords(monkeypatch):
    fake_model(monkeypatch, lambda _: ("screen", "{{current.f2}}입니다."))
    first = ask("면적은?", regression())
    def choose(payload):
        assert set(payload["sources"]) == {"current", "previous"}
        return "screen", "{{previous.f2}}입니다."
    fake_model(monkeypatch, choose)
    result = ask("그 음의 관계를 다시 설명해줄래?", regression("지역 B", 0.35), first.session_id)
    assert "지역 A" in result.answer and "0.35" not in result.answer


@pytest.mark.parametrize(("panel", "facts", "expected"), [
    ("PaidMatrixCell", {"tx_count": 326}, "전체 거래 326건"),
    ("LandHistogram", {"median_unit_price_per_sqm": 51}, "단가 중앙값 51만원/㎡"),
    ("LandTransactions", {"total": 43, "items": [{"address": "원시 거래"}]}, "조건에 맞는 거래 43건"),
    ("LandPredict", {"y_hat": 65}, "모형 추정 단가 65만원/㎡"),
])
def test_any_land_panel_uses_same_dialogue_and_repair(monkeypatch, panel, facts, expected):
    def choose(payload):
        assert "원시 거래" not in str(payload)
        assert payload["sources"]["current"]["context"]["panel"] == panel
        if "rejected_draft" not in payload:
            return "screen", "결과는 999입니다."
        return "screen", "화면에서 확인한 값은 {{current.f0}}입니다."

    fake_model(monkeypatch, choose)
    result = ask("여기서 눈여겨볼 값이 있어?", AiContext(app="land", panel=panel, facts=facts))
    assert result.llm_used
    assert expected in result.answer and "999" not in result.answer


def test_failed_reply_is_not_spliced_into_a_different_conclusion(monkeypatch):
    fake_model(monkeypatch, lambda _: ("screen", "{{current.f0}}입니다. 검증 MAPE는 77%입니다."))
    result = ask("이 결과를 어떻게 봐?", regression())
    assert "적합 표본 120건" not in result.answer
    assert "77%" not in result.answer
    assert not result.llm_used




def test_symbolic_identity_does_not_block_grounded_explanation(monkeypatch):
    fake_model(monkeypatch, lambda _: ("screen", "{{current.f2}}입니다. 총액의 탄력성은 1+β이지만 규모의 경제를 증명하지는 않습니다."))
    result = ask("이 관계를 어떻게 해석해?", regression())
    assert result.llm_used
    assert "규모의 경제를 증명하지는 않습니다" in result.answer


def test_mixed_knowledge_and_screen_refs_are_validated(monkeypatch):
    fake_model(monkeypatch, lambda _: ("knowledge", "{{current.f2}}만으로 인과관계를 판단할 수는 없어요."))
    result = ask("인과관계야?", regression())
    assert result.llm_used and result.evidence[0].ref == "current.f2"


@pytest.mark.parametrize("text", ["총액은 1+120입니다", "y+120", "현재 값은 1입니다", "표본은 0.528건입니다"])
def test_symbolic_allowance_does_not_admit_observed_numbers(monkeypatch, text):
    fake_model(monkeypatch, lambda _: ("screen", "{{current.f2}}. " + text))
    result = ask("설명해줘", regression())
    assert not result.llm_used


def test_repair_preserves_conclusion_without_partial_recovery(monkeypatch):
    def choose(payload):
        if "rejected_draft" not in payload:
            return "screen", "규모의 경제로 단정할 수 없습니다. {{current.f2}}이며 검증값은 999입니다."
        assert payload["validation_feedback"]
        return "screen", "규모의 경제로 단정할 수 없습니다. {{current.f2}}는 조건부 연관입니다."
    fake_model(monkeypatch, choose)
    result = ask("규모의 경제야?", regression())
    assert result.llm_used and result.answer.startswith("규모의 경제로 단정할 수 없습니다")


def test_referenced_elasticity_can_explain_unit_change(monkeypatch):
    fake_model(monkeypatch, lambda _: ("screen", "{{current.f2}}는 면적이 1% 커질 때 단가가 약 0.24% 낮아지는 조건부 연관입니다. 규모의 경제를 증명하지는 않습니다."))
    result = ask("면적 관계를 설명해줘", regression())
    assert result.llm_used and "증명하지는 않습니다" in result.answer


def test_numbers_cannot_borrow_other_sentences_evidence(monkeypatch):
    fake_model(monkeypatch, lambda _: ("screen", "{{current.f2}}입니다. 추정 단가는 0.24만원입니다."))
    result = ask("설명해줘", regression())
    assert not result.llm_used


@pytest.mark.parametrize(("claim", "accepted"), [("0.416", True), ("0.4159", True), ("0.417", False), ("0.4", False), ("1", False)])
def test_display_rounding_is_checked_against_cited_metric(monkeypatch, claim, accepted):
    fake_model(monkeypatch, lambda _: ("screen", "{{current.f1}}, 약 " + claim + "입니다."))
    result = ask("모형 적합도는?", regression(adj_r_squared=0.41594143))
    assert result.llm_used is accepted


def test_validation_feedback_identifies_missing_reference():
    from app.ai.dialogue import _repair_feedback, _screen
    feedback = _repair_feedback({"kind":"screen", "answer":"표본은 999건입니다."}, {"current":_screen(regression())})
    assert "number_without_local_reference" in feedback


@pytest.mark.parametrize(("category", "accepted"), [("12미만", True), ("25이상", True), ("8미만", True), ("99미만", False)])
def test_category_identifiers_are_not_measurements(monkeypatch, category, accepted):
    context = regression(coefficients=[{"label":"도로:12미만", "coef":0.78}, {"label":"도로:25이상", "coef":0.75}], reference_categories={"도로조건":"8미만"})
    fake_model(monkeypatch, lambda _: ("screen", category + " 범주는 {{current.f2}}와 함께 검토하세요."))
    result = ask("이 모형의 적정성은?", context)
    assert result.llm_used is accepted


def test_diagnostic_availability_is_transmitted(monkeypatch):
    def choose(payload):
        source = payload["sources"]["current"]
        assert any("잔차 자유도 94" in v for v in source["facts"].values())
        assert any("독립 검증 MAPE은 제공되지" in v for v in source["notes"])
        return "knowledge", "독립 검증 결과는 제공되지 않아 예측 정확도를 단정하기 어렵습니다."
    fake_model(monkeypatch, choose)
    result = ask("예측 정확도는?", regression(analysis={"coefficient_n":6,"provision":{"residual_df":94},"metrics":[{"key":"MAPE","role":"independent_confirmation","status":"unavailable"}]}))
    assert result.llm_used


def test_markdown_list_and_duplicate_unit_preserve_evidence(monkeypatch):
    fake_model(monkeypatch, lambda _: ("screen", "- {{current.f0}}건입니다.\n- {{current.f1}}입니다."))
    result = ask("적정성을 검토해줘", regression())
    assert result.llm_used and "120건건" not in result.answer


def test_inline_negative_sign_still_rejected(monkeypatch):
    fake_model(monkeypatch, lambda _: ("screen", "결과는 -{{current.f0}}입니다."))
    assert not ask("표본은?", regression()).llm_used


def test_unknown_category_hyphen_is_not_a_numeric_sign(monkeypatch):
    fake_model(monkeypatch, lambda _: ("screen", "도로:- {{current.f2}}는 미상 도로조건의 계수입니다."))
    result = ask("회귀식의 적정성을 검토해줘", regression(coefficients=[{"label":"도로:-", "coef":-0.3299}]))
    assert result.llm_used and "-0.3299" in result.answer


def test_current_question_is_last_conversation_turn(monkeypatch):
    def choose(payload):
        assert payload["conversation"][-1] == {"role":"user", "message":payload["question"]}
        return "knowledge", "현재 질문에 대한 설명입니다."
    fake_model(monkeypatch, choose)
    first = ask("회귀식의 적정성은?", regression())
    second = ask("미상 범주와 결측 제외의 차이는?", regression(), first.session_id)
    assert second.llm_used
