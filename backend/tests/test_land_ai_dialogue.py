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
        payload = json.loads(user)
        if "passages" in payload:
            return json.dumps({"general_indices": [i for i, text in enumerate(payload["passages"]) if "유의수준" in text]})
        kind, answer = choose(payload)
        return json.dumps({"kind": kind, "answer": answer}, ensure_ascii=False)

    monkeypatch.setattr("app.ai.dialogue.llm._openai_chat", draft)


def reference(payload, label, source="current"):
    return next(key for key, fact in payload["sources"][source]["facts"].items() if fact.startswith(label))


def test_screen_reply_uses_labeled_coefficient_and_omits_raw_transactions(monkeypatch):
    def choose(payload):
        assert "7019" not in str(payload)
        assert payload["sources"]["current"]["context"]["종속변수"] == "log(토지 단가)"
        fact = reference(payload, "log(면적) 계수")
        return "screen", "다른 조건이 같을 때, {{" + fact + "|label}}는 면적과 단가의 음의 관계를 뜻합니다."

    fake_model(monkeypatch, choose)
    result = ask("면적 계수는 무슨 뜻이야?", regression())
    assert result.llm_used
    assert "log(면적) 계수 -0.24" in result.answer
    assert "120" not in result.answer
    assert result.evidence[0].ref == "current.f2"
    assert not result.suggested_followups


@pytest.mark.parametrize("answer", [
    "표본은 0.528건이고 조정 R²는 120입니다.",
    "{{previous.f0|label}}입니다.",
    "{{current.f0|label}}%입니다.",
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
        return "screen", "{{current.f0|label}}입니다."

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


def test_built_screen_passes_the_visible_equation(monkeypatch):
    def choose(payload):
        facts = " ".join(payload["sources"]["current"]["facts"].values())
        notes = " ".join(payload["sources"]["current"]["notes"])
        assert "연면적 계수 12.5" in facts
        assert "연식 계수" not in facts
        assert "R²" in facts and "MAPE" in facts  # available regardless of question wording
        assert "회귀식이 있다" in notes and "금액(만원)" in notes
        assert "용도지역 기준 범주 일반상업" in notes
        return "screen", "화면에 회귀식이 있습니다. 연면적 계수는 {{" + reference(payload, "연면적 계수") + "|label}}입니다."

    fake_model(monkeypatch, choose)
    result = ask("지금 화면의 회귀식이 보이나?", AiContext(
        app="built", panel="RegressionScatterCard", scope=AiScope(region_label="마산합포구"),
        facts={
            "response_scale": "linear", "scatter_tab": "raw",
            "primary": {
                "scope_label": "마산합포구", "n": 218, "r_squared": 0.41, "adj_r_squared": 0.38,
                "mape": 31.2, "coefficients": [
                    {"name": "const", "estimate": 1000, "p_value": 0.001},
                    {"name": "gross_area", "estimate": 12.5, "p_value": 0.01},
                    {"name": "building_age", "estimate": -3, "p_value": 0.4},
                ],
                "predict_options": {"zone_reference": "일반상업"},
            },
            "correlations": [{"label": "연면적", "pearson_r": 0.22, "points": [{"x": 80, "y": 9000}]}],
            "comparisons": [{"scope_label": "창원시"}],
        },
    ))
    assert result.llm_used and "연면적 계수 12.5" in result.answer
    assert "80" not in result.answer and "9000" not in result.answer


def test_recommendation_screen_passes_only_the_open_tab():
    from app.ai.dialogue import _screen

    stage1 = {
        "selection_n": 200, "fit_n": 180, "representative_confirmed": False,
        "representative_note": "확인 표본이 부족합니다.",
        "primary": {
            "rank": 1, "response_scale": "log", "blocks": ["gross_area"],
            "metrics": {"cv_mape": 12.5, "mape": 9.0, "adj_r_squared": 0.4},
            "cv_report": {"confirm": {"mape": 14.2}},
            "coefficients": [
                {"name": "const", "estimate": 10, "p_value": 0.001},
                {"name": "gross_area", "estimate": 0.2, "p_value": 0.01},
                {"name": "building_age", "estimate": -0.1, "p_value": 0.4},
            ],
        },
        "alternate": {
            "rank": 1, "response_scale": "linear", "blocks": ["land_area"], "aic": 100,
            "metrics": {"adj_r_squared": 0.9, "mape": 1, "cv_mape": 2},
        },
        "candidates_predictive": [
            {"rank": 1, "response_scale": "log", "blocks": ["gross_area"], "metrics": {"cv_mape": 12.5}, "cv_report": {"confirm": {"mape": 14.2}}},
            {"rank": 2, "response_scale": "linear", "blocks": ["building_age"], "metrics": {"cv_mape": 18}, "cv_report": {"confirm": {"mape": 19}}},
        ],
        "predictive_judgments": [{"rank": 2, "cv_gap_pp": 1.5, "label": "비교"}],
    }
    raw = {
        "analysis_scope": {"scope_n_tx": 300, "include_partial": False, "partial_tx_count": 4},
        "stage1": stage1,
        "stage2": {"ran": True, "inspect_pool": {"n": 900, "cv_mape": 8, "adj_r_squared": 0.5, "confirm_cv_mape": 9}},
        "twin_choices": [{"label": "인근동", "similarity_score": 0.85, "rank": 1}],
    }
    predict = _screen(AiContext(app="built", panel="RecommendationCard", scope=AiScope(region_label="마산합포구"), facts={**raw, "recommend_view": "predict"}))
    assert any(fact.startswith("탐색 CV-MAPE 12.5") for fact in predict.facts)
    assert any(fact.startswith("연면적 계수 0.2") for fact in predict.facts)
    assert any(fact.startswith("2위 탐색 CV-MAPE 18") for fact in predict.facts)
    assert not any("연식 계수" in fact for fact in predict.facts)
    assert not any(fact.startswith("AIC") for fact in predict.facts)
    assert not any("900" in fact for fact in predict.facts)
    assert "예측형" in " ".join(predict.notes)

    explain = _screen(AiContext(app="built", panel="RecommendationCard", scope=AiScope(region_label="마산합포구"), facts={**raw, "recommend_view": "explain"}))
    assert any(fact.startswith("AIC 100") for fact in explain.facts)
    assert not any("12.5" in fact for fact in explain.facts)

    twin = _screen(AiContext(app="built", panel="RecommendationCard", scope=AiScope(region_label="마산합포구"), facts={**raw, "recommend_view": "twin"}))
    assert any(fact.startswith("인근동 유사도 85") for fact in twin.facts)
    assert any(fact.startswith("Twin1 적합 표본 900") for fact in twin.facts)
    assert not any("12.5" in fact for fact in twin.facts)

    suggest = _screen(AiContext(
        app="built", panel="ModelSelectionCard", scope=AiScope(region_label="마산합포구"),
        facts={"selection_mode": "suggest", "n": 40, "response_scale": "log", "recommended_blocks": ["gross_area"],
               "metrics": {"adj_r_squared": 0.31, "mape": 11, "cv_mape": 13},
               "forward_steps": [{"aic_after": 80.5}],
               "joint_f_tests": {"gross_area": {"tested": True, "p_value": 0.02}, "building_age": {"tested": False, "p_value": 0.4}}},
    ))
    assert any(fact.startswith("CV-MAPE 13") for fact in suggest.facts)
    assert any(fact.startswith("연면적 Joint F p값 0.02") for fact in suggest.facts)
    assert not any("building_age" in fact or fact.startswith("연식") for fact in suggest.facts)


def test_regional_rent_and_histogram_screens_pass_visible_numbers():
    from app.ai.dialogue import _screen

    regional = _screen(AiContext(
        app="collective", panel="RegionalRegressionModal", scope=AiScope(region_label="광주시"),
        facts={"ran": True, "model_type": "log", "n": 40, "r_squared": 0.61,
               "coefficients": [{"name": "const", "label": "절편", "coef": 1.2, "p": 0.01},
                                {"name": "households", "label": "세대수", "coef": 0.04, "p": 0.2}]},
    ))
    assert any(fact.startswith("절편 계수") for fact in regional.facts)
    assert not any(fact.startswith("세대수 계수") for fact in regional.facts)
    assert "지역회귀" in " ".join(regional.notes)

    rent = _screen(AiContext(
        app="rent", panel="RentListCard", scope=AiScope(region_label="창원시"),
        facts={"r_selected": 0.046, "n_rates": 1, "rates": [{"asset_type": "apartment", "r_selected": 0.046, "n_buildings": 12}]},
    ))
    assert any(fact.startswith("아파트 전환율 0.046") for fact in rent.facts)

    hist = _screen(AiContext(
        app="collective", panel="HistogramPanel", scope=AiScope(region_label="단지"),
        facts={"n": 80, "median_unit_price": 500, "bins": [{"lo": 400, "hi": 500, "count": 11}]},
    ))
    assert any(fact.startswith("단가 중앙값 500") for fact in hist.facts)
    assert any("400~500만원/㎡ 구간 거래 11" in fact for fact in hist.facts)


def test_building_screen_is_described_as_trade_regression_not_regional():
    from app.ai.dialogue import _screen

    evidence = _screen(AiContext(
        app="collective", panel="BuildingRegressionPanel",
        facts={"cohort": False, "n": 121, "r_squared": 0.932},
    ))
    text = " ".join(evidence.notes)
    assert "거래 회귀" in text and "지역회귀" in text and "중앙단가" in text
    assert any(fact.startswith("적합 표본 121") for fact in evidence.facts)
    assert any(fact.startswith("R² ") for fact in evidence.facts)


def test_unrelated_meal_is_refused_without_the_model(monkeypatch):
    def boom(**kwargs):
        raise AssertionError("model called")

    monkeypatch.setattr("app.ai.dialogue.llm._openai_chat", boom)
    result = ask("오늘 저녁 메뉴 추천해줘", regression())
    assert result.route == "refusal" and not result.llm_used
    assert "통계 밖" in result.answer


def test_p_value_is_available_without_question_keyword_gating(monkeypatch):
    def choose(payload):
        facts = " ".join(payload["sources"]["current"]["facts"].values())
        assert "p값" in facts
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


def test_labeled_hypothesis_is_kept(monkeypatch):
    def once(*, user, system, json_response, timeout=45):
        assert json_response
        return json.dumps({
            "kind": "knowledge",
            "answer": "맞습니다. 단가가 낮아집니다.\n\n원인에 대한 가설:\n- 외곽일 수 있습니다.\n\n인과는 아닙니다.",
        }, ensure_ascii=False)

    monkeypatch.setattr("app.ai.dialogue.llm._openai_chat", once)
    result = ask("면적 계수가 음수면 단가가 낮다는 거지?", regression())
    # 2026-11-09 §5.2: 가설 문장을 서버가 자동 삭제하지 않는다. '가설' 표시만 요구한다.
    assert "가설" in result.answer and "외곽" in result.answer
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
        return "screen", "화면에서 확인한 값은 {{current.f0|label}}입니다."

    fake_model(monkeypatch, choose)
    result = ask("여기서 눈여겨볼 값이 있어?", AiContext(app="land", panel=panel, facts=facts))
    assert result.llm_used
    assert expected in result.answer and "999" not in result.answer


def test_unverified_sentence_is_dropped_and_verified_sentence_kept(monkeypatch):
    fake_model(monkeypatch, lambda _: ("screen", "{{current.f0|label}}입니다. 검증 MAPE는 77%입니다."))
    result = ask("이 결과를 어떻게 봐?", regression())
    # 검증되지 않은 문장만 제거하고, 검증된 문장은 남긴다(§5.2-3).
    assert "77%" not in result.answer
    assert result.answer.startswith("적합 표본 120건")




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
    fake_model(monkeypatch, lambda _: ("screen", "{{current.f2|label}}. " + text))
    result = ask("설명해줘", regression())
    # 재작성도 실패하면 위반 문장만 빠지고 검증된 문장은 남는다(§5.2-3).
    assert text not in result.answer
    assert "log(면적) 계수 -0.24" in result.answer


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
    assert "0.24만원" not in result.answer and "추정 단가" not in result.answer


@pytest.mark.parametrize(("claim", "accepted"), [("0.416", True), ("0.4159", True), ("0.417", False), ("0.4", False), ("1", False)])
def test_display_rounding_is_checked_against_cited_metric(monkeypatch, claim, accepted):
    fake_model(monkeypatch, lambda _: ("screen", "{{current.f1}}, 약 " + claim + "입니다."))
    result = ask("모형 적합도는?", regression(adj_r_squared=0.41594143))
    assert result.llm_used is accepted


def test_validation_feedback_identifies_missing_reference():
    from app.ai.dialogue import _repair_feedback, _screen
    feedback = _repair_feedback({"kind":"screen", "answer":"표본은 999건입니다."}, {"current":_screen(regression())})
    assert "unverified_numeric_passage" in feedback


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


# --- 2026-11-09 지시서 §5.1~§5.4, §5.6 ---------------------------------------

from decimal import Decimal


def land_matrix(**extra):
    """영춘면 필터 분석 결과(T1) 형태의 화면 문맥."""
    facts = {
        "result_kind": "filtered",
        "matrix_mode": "category",
        "land_axis": "지목",
        "total": {"count": 412, "mean": 2.4, "median": 1.9},
        "cells": [
            {"zone_type": "보관", "land_category": "임", "count": 50, "mean": 1.7, "median": 1.2,
             "p25": 0.8, "p75": 2.1, "min": 0.2, "max": 6.3, "ci_lower": 1.3, "ci_upper": 2.1, "is_reliable": True},
            {"zone_type": "계관", "land_category": "전", "count": 9, "mean": 3.1, "median": 2.9,
             "p25": 2.2, "p75": 3.6, "is_reliable": False},
        ],
        "omitted_cells": 3,
        "by_zone": [{"label": "보관", "count": 120, "mean": 1.9, "median": 1.4}],
        "by_land_category": [{"label": "임", "count": 200, "mean": 1.5, "median": 1.1}],
        "by_year": [{"year": 2026, "count": 70, "unit_price_per_sqm": 2.5}],
        "filters_changed": False,
        "reliable_min_n": 15,
        **extra,
    }
    return AiContext(
        app="land", panel="LandMatrix",
        scope=AiScope(
            region_label="충청북도 단양군 영춘면", region_level="eupmyeondong",
            period={"kind": "calendar", "years": [2021, 2022, 2023, 2024, 2025, 2026]},
            filters={"exclude_outlier": True, "outlier_iqr_multiplier": 1.5, "exclude_partial": False,
                     "matrix_mode": "category"},
            as_of_month="2026-10-01",
        ),
        facts=facts,
    )


def trend_cell():
    rows = [
        {"year": 2021, "count": 22, "mean": 2.8, "median": 2.5},
        {"year": 2024, "count": 15, "mean": 2.6, "median": 2.4, "is_small_sample": False},
        {"year": 2025, "count": 12, "mean": 2.9, "median": 2.7, "is_small_sample": True},
        {"year": 2026, "count": 18, "mean": 3.2, "median": 3.0, "is_partial_period": True, "covered_months": 10},
    ]
    return AiContext(app="land", panel="TrendCard", scope=AiScope(region_label="영춘면 · 계관 × 전"),
                     facts={"rows": rows, "trend_metric": "mean", "zone_type": "계관", "land_category": "전"})


def counting_model(monkeypatch, choose):
    calls = {"n": 0}

    def draft(*, user, system, json_response, timeout=45):
        calls["n"] += 1
        kind, answer = choose(json.loads(user))
        return json.dumps({"kind": kind, "answer": answer}, ensure_ascii=False)

    monkeypatch.setattr("app.ai.dialogue.llm._openai_chat", draft)
    return calls


def _fact(payload, prefix):
    return next(k for k, v in payload["sources"]["current"]["facts"].items() if v.startswith(prefix))


def test_land_matrix_context_sends_every_cell_scope_and_small_sample_notes():
    from app.ai.dialogue import _screen

    evidence = _screen(land_matrix())
    facts = " | ".join(evidence.facts)
    assert "보관 × 임 거래 50건" in facts and "보관 × 임 단가 평균 1.7만원/㎡" in facts
    assert "계관 × 전 단가 75% 분위 3.6만원/㎡" in facts
    assert "이상치 IQR 배수 1.5" in facts
    assert evidence.context["지역"] == "충청북도 단양군 영춘면"
    assert "2021" in evidence.context["기간"] and evidence.context["기준월"] == "2026-10-01"
    notes = " ".join(evidence.notes)
    assert "소표본 칸: 계관 × 전" in notes and "3개는 전달하지 않았다" in notes
    assert "보관 × 임" in evidence.identifiers


def test_t1_filtered_matrix_cell_is_answered_with_one_call(monkeypatch):
    def choose(payload):
        mean = _fact(payload, "보관 × 임 단가 평균")
        count = _fact(payload, "보관 × 임 거래")
        return "screen", "보관 × 임 칸의 평균 단가는 {{" + mean + "|value}}, 거래는 {{" + count + "|value}}입니다."

    calls = counting_model(monkeypatch, choose)
    result = ask("지금 화면의 보관 용도지역 임야 칸 평균 단가와 거래 수는?", land_matrix())
    assert result.llm_used and calls["n"] == 1
    assert result.answer == "보관 × 임 칸의 평균 단가는 1.7만원/㎡, 거래는 50건입니다."
    assert "영춘면" in result.evidence[0].label


def test_t2_question_numbers_are_allowed_without_reference(monkeypatch):
    answer = ("IQR 1.5는 사분위범위의 1.5배 밖을 이상치로 보고, 3은 더 바깥만 잘라 덜 엄격합니다. "
              "저가 임야가 많아 오른쪽 꼬리가 긴 분포에서는 하한이 음수가 되어 사실상 고가 쪽만 잘립니다.")
    calls = counting_model(monkeypatch, lambda _: ("knowledge", answer))
    result = ask("이상치 제외에서 IQR 1.5와 3은 무슨 차이야? 저가 임야가 많은 지역에서는?", land_matrix())
    assert result.llm_used and calls["n"] == 1
    assert result.answer == answer


def test_general_example_numbers_are_allowed(monkeypatch):
    answer = "예를 들어 평균이 100이고 중앙값이 80이면 오른쪽으로 긴 꼬리가 있다는 뜻이에요."
    calls = counting_model(monkeypatch, lambda _: ("knowledge", answer))
    result = ask("평균과 중앙값이 다르면 무슨 뜻이야?", land_matrix())
    assert result.answer == answer and calls["n"] == 1


@pytest.mark.parametrize("sentence", [
    "영춘면의 평균 단가는 2.3만원/㎡입니다.",
    "보관 × 임 칸은 거래 47건입니다.",
    "현재 화면에서 가장 비싼 칸은 9.9만원/㎡입니다.",
])
def test_observation_with_unreferenced_number_is_rejected(sentence):
    from app.ai.dialogue import _render, _screen, number_policy

    sources = {"current": _screen(land_matrix())}
    issues = []
    policy = number_policy("평균 단가 알려줘", sources, ["일반 문서"])
    assert _render({"kind": "knowledge", "answer": sentence}, sources, issues, policy) is None
    assert issues and issues[0].startswith("unverified_numeric_passage")


def test_repair_prompt_no_longer_forbids_arabic_numerals():
    from app.ai.dialogue import _repair_feedback, _screen

    feedback = _repair_feedback({"kind": "screen", "answer": "표본은 999건입니다."}, {"current": _screen(regression())})
    assert "아라비아 숫자" not in feedback


def test_general_check_llm_call_is_gone():
    import app.ai.dialogue as dialogue

    assert not hasattr(dialogue, "_check_general_numbers")
    assert not hasattr(dialogue, "_drop_causes")


def test_t3_trend_notes_mark_partial_year_and_small_sample(monkeypatch):
    def choose(payload):
        notes = " ".join(payload["sources"]["current"]["notes"])
        assert "2026년은 기준월까지만 집계된 부분 연도" in notes and "10월까지" in notes
        assert "2025년은 거래 15건 미만인 소표본" in notes
        hi = _fact(payload, "2026년 단가 평균")
        lo = _fact(payload, "2024년 단가 평균")
        n26 = _fact(payload, "2026년 거래 수")
        return "screen", ("가장 높은 해는 2026년({{" + hi + "|value}}), 가장 낮은 해는 2024년({{" + lo + "|value}})입니다. "
                          "다만 2026년은 10월까지 {{" + n26 + "|value}}이라 가격 상승으로 바로 해석하기 어렵습니다.")

    calls = counting_model(monkeypatch, choose)
    result = ask("이 칸의 연도별 평균 단가 추이 요약, 가장 높은 해와 낮은 해는?", trend_cell())
    assert result.llm_used and calls["n"] == 1
    assert "2026년(3.2만원/㎡)" in result.answer and "10월까지 18건" in result.answer


def test_t4_calc_reference_is_computed_by_server_with_caution(monkeypatch):
    def choose(payload):
        med = _fact(payload, "보관 × 임 단가 중앙값")
        p25 = _fact(payload, "보관 × 임 단가 25% 분위")
        p75 = _fact(payload, "보관 × 임 단가 75% 분위")
        return "screen", ("중앙값 기준 {{calc:" + med + "*5000}}이고, 25%~75% 분위 기준으로는 "
                          "{{calc:" + p25 + "*5000}}~{{calc:" + p75 + "*5000}}입니다.")

    calls = counting_model(monkeypatch, choose)
    result = ask("이 칸 중앙값으로 5,000㎡ 임야면 얼마 정도야?", land_matrix())
    assert result.llm_used and calls["n"] == 1
    assert "6,000만원" in result.answer and "4,000만원~1억 500만원" in result.answer
    assert "적정가격이 아닙니다" in result.answer and "개별요인" in result.answer
    assert any(item.label.startswith("산술 계산") for item in result.evidence)


@pytest.mark.parametrize("expr", ["current.f0*7777", "__import__('os')", "current.f999*5000", "5000*2"])
def test_calc_rejects_unsafe_or_unasked_expressions(expr):
    from app.ai.dialogue import _render, _screen, number_policy

    sources = {"current": _screen(land_matrix())}
    issues = []
    policy = number_policy("5,000㎡면 얼마야?", sources)
    assert _render({"kind": "screen", "answer": "약 {{calc:" + expr + "}}입니다."}, sources, issues, policy) is None
    assert issues[0].startswith(("invalid_calc", "invalid_reference"))


@pytest.mark.parametrize(("value", "unit", "shown"), [
    (Decimal("6000"), "만원", "6,000만원"),
    (Decimal("16000"), "만원", "1억 6,000만원"),
    (Decimal("20000"), "만원", "2억원"),
    (Decimal("1234.5"), "", "1,235"),
    (Decimal("3.456"), "만원/㎡", "3.46만원/㎡"),
])
def test_amount_formatting(value, unit, shown):
    from app.ai.dialogue import format_amount

    assert format_amount(value, unit) == shown


def test_t5_buy_question_short_answer_passes(monkeypatch):
    answer = "이 자료만으로는 지금 사도 되는지 결론을 낼 수 없어요. 화면은 지역 거래 통계일 뿐 개별 토지의 조건을 반영하지 않습니다."
    calls = counting_model(monkeypatch, lambda _: ("knowledge", answer))
    result = ask("이 동네 땅 지금 사도 돼?", land_matrix())
    assert result.answer == answer and calls["n"] == 1


def test_t6_unrelated_question_uses_zero_calls(monkeypatch):
    calls = counting_model(monkeypatch, lambda _: ("knowledge", "x"))
    result = ask("오늘 점심 메뉴 추천해줘", land_matrix())
    assert result.route == "refusal" and calls["n"] == 0


def test_t7_missing_screen_context_says_so(monkeypatch):
    counting_model(monkeypatch, lambda _: ("screen", "평균 단가는 3.1만원/㎡입니다."))
    result = ask("평균 단가 얼마야?", AiContext(app="land", panel="LandMatrix"))
    assert "3.1" not in result.answer
    assert "전달되지 않았습니다" in result.answer and "지역 미선택" not in result.answer


def test_question_log_records_calls_and_validation(monkeypatch, tmp_path):
    from app.config import settings
    from app.ai.usage_log import question_stats

    monkeypatch.setattr(settings, "ai_usage_log_dir", str(tmp_path))
    counting_model(monkeypatch, lambda _: ("knowledge", "교란변수는 두 변수 모두와 관련된 제3의 변수예요."))
    ask("교란변수가 뭐야?", land_matrix())
    rows = [json.loads(line) for path in tmp_path.glob("questions-*.jsonl")
            for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["llm_calls"] == 1 and rows[0]["validation"] == "pass" and rows[0]["panel"] == "LandMatrix"
    assert "교란변수" not in json.dumps(rows[0], ensure_ascii=False)
    stats = question_stats()
    assert stats["questions"] == 1 and stats["avg_llm_calls"] == 1


# --- Opus 검토 보완: kind 무관 단위 검사, 용도지역명 관측 표지어 -------------------


@pytest.mark.parametrize("sentence", [
    "평균 단가는 2.3만원/㎡입니다.",          # knowledge 로 표시해도 단위 붙은 미참조 숫자
    "보관은 거래가 47건으로 가장 많습니다.",    # 화면 용도지역명 + 미참조 숫자
    "계관 평균은 3.9 정도입니다.",             # 단위 없어도 용도지역명과 같은 문장
])
def test_unit_and_zone_name_checks_apply_to_knowledge_kind(sentence):
    from app.ai.dialogue import _render, _screen, number_policy

    sources = {"current": _screen(land_matrix())}
    issues = []
    policy = number_policy("이 화면 설명해줘", sources, ["일반 문서"])
    assert _render({"kind": "knowledge", "answer": sentence}, sources, issues, policy) is None
    assert issues[0].startswith("unverified_numeric_passage")


@pytest.mark.parametrize("sentence", [
    "예를 들어 거래가 30건뿐이면 평균이 크게 흔들릴 수 있어요.",
    "표본이 15건 미만이면 소표본으로 봅니다.",
    "가령 단가가 2만원/㎡인 토지 5,000㎡라면 총액은 1억원이에요.",
])
def test_hypothetical_unit_numbers_still_allowed(sentence):
    from app.ai.dialogue import _render, _screen, number_policy

    sources = {"current": _screen(land_matrix())}
    policy = number_policy("일반적으로 어떻게 봐?", sources, ["일반 문서"])
    assert _render({"kind": "knowledge", "answer": sentence}, sources, policy=policy) is not None


def test_trend_zone_name_is_an_observation_marker():
    from app.ai.dialogue import _render, _screen, number_policy

    sources = {"current": _screen(trend_cell())}
    issues = []
    policy = number_policy("추이 요약해줘", sources)
    assert _render({"kind": "knowledge", "answer": "계관 칸은 꾸준히 4.1 수준입니다."}, sources, issues, policy) is None


# --- 2026-11-10 운영 T1~T7 후속 ------------------------------------------------


def trend_with_cell_total():
    ctx = trend_cell()
    ctx.facts["cell_total"] = {"count": 220, "mean": 2.9, "median": 2.7, "p25": 2.1, "p75": 3.4,
                               "min": 0.9, "max": 7.8, "ci_lower": 2.7, "ci_upper": 3.1, "is_reliable": True}
    return ctx


def test_t7_refresh_does_not_answer_from_previous_screen(monkeypatch):
    seen = []

    def choose(payload):
        seen.append(set(payload["sources"]))
        if len(seen) == 1:
            ref = _fact(payload, "2026년 단가 평균")
            return "screen", "2026년 평균은 {{" + ref + "}}입니다."
        return "knowledge", "지금 화면의 통계가 AI에 전달되지 않아 평균 단가를 말할 수 없어요."

    counting_model(monkeypatch, choose)
    first = ask("2026년 평균은?", trend_cell())
    assert "3.2만원/㎡" in first.answer
    # 새로고침: 화면 문맥이 비었다. 같은 세션이어도 이전 화면을 현재처럼 쓰지 않는다.
    empty = AiContext(app="land", panel="PaidMatrixCell")
    second = ask("평균 단가 얼마야?", empty, first.session_id)
    assert seen[1] == {"current"}
    assert "3.2" not in second.answer


def test_previous_screen_is_available_when_user_asks_for_it(monkeypatch):
    def choose(payload):
        if "previous" in payload["sources"]:
            ref = next(k for k, v in payload["sources"]["previous"]["facts"].items() if v.startswith("2026년 단가 평균"))
            return "screen", "아까 본 2026년 평균은 {{" + ref + "}}였어요."
        ref = _fact(payload, "2026년 단가 평균")
        return "screen", "2026년 평균은 {{" + ref + "}}입니다."

    counting_model(monkeypatch, choose)
    first = ask("2026년 평균은?", trend_cell())
    again = ask("아까 본 2026년 평균 다시 알려줘", AiContext(app="land", panel="PaidMatrixCell"), first.session_id)
    assert "3.2만원/㎡ (이전 분석 · 영춘면 · 계관 × 전)" in again.answer


def test_reference_inserts_value_and_unit_by_default(monkeypatch):
    def choose(payload):
        mean = _fact(payload, "2021년 단가 평균")
        count = _fact(payload, "2021년 거래 수")
        return "screen", "2021년 평균 단가는 {{" + mean + "}}(거래 {{" + count + "}})입니다."

    counting_model(monkeypatch, choose)
    result = ask("2021년은?", trend_cell())
    assert result.answer == "2021년 평균 단가는 2.8만원/㎡(거래 22건)입니다."


def test_label_option_still_inserts_metric_name(monkeypatch):
    counting_model(monkeypatch, lambda p: ("screen", "{{" + _fact(p, "2021년 거래 수") + "|label}}입니다."))
    assert ask("2021년 거래는?", trend_cell()).answer == "2021년 거래 수 22건입니다."


def test_modal_sends_whole_cell_stats_and_prefers_them():
    from app.ai.dialogue import _screen

    evidence = _screen(trend_with_cell_total())
    facts = " | ".join(evidence.facts)
    assert "계관 × 전 칸 전체 거래 220건" in facts
    assert "계관 × 전 칸 전체 단가 중앙값 2.7만원/㎡" in facts
    assert "계관 × 전 칸 전체 단가 25% 분위 2.1만원/㎡" in facts
    assert any("연도별 값보다 이 값을 먼저" in note for note in evidence.notes)


def test_t4_calc_from_whole_cell_and_caution_not_duplicated(monkeypatch):
    def choose(payload):
        med = _fact(payload, "계관 × 전 칸 전체 단가 중앙값")
        p25 = _fact(payload, "계관 × 전 칸 전체 단가 25% 분위")
        p75 = _fact(payload, "계관 × 전 칸 전체 단가 75% 분위")
        return "screen", ("칸 전체 중앙값 기준 {{calc:" + med + "*5000}}, 25~75% 범위는 {{calc:" + p25 + "*5000}}~"
                          "{{calc:" + p75 + "*5000}}입니다. 지역 통계로 낸 산술값이라 그 토지의 적정 가격은 아닙니다.")

    counting_model(monkeypatch, choose)
    result = ask("이 칸 중앙값으로 5,000㎡면 얼마야?", trend_with_cell_total())
    assert "1억 3,500만원" in result.answer and "1억 500만원~1억 7,000만원" in result.answer
    assert result.answer.count("적정") == 1


def test_t5_prompt_asks_for_one_or_two_sentences_of_context():
    from app.ai.dialogue import _SYSTEM

    assert "1~2문장" in _SYSTEM and "결론을 낼 수 없다고 먼저" in _SYSTEM


def test_t2_product_knowledge_explains_right_skew_iqr():
    from app.ai.knowledge.product import product_knowledge_pack

    text = product_knowledge_pack(app="land")
    assert "하한이 0 이하(음수)" in text and "비싼 쪽만 잘린다" in text


def test_reasoning_effort_is_sent_for_reasoning_models(monkeypatch):
    import io
    from app.ai import llm
    from app.config import settings

    sent = {}

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(req, timeout=0):
        sent.update(json.loads(req.data.decode("utf-8")))
        return Resp(json.dumps({"model": "gpt-5-mini", "usage": {}, "choices": [{"message": {"content": "{}"}}]}).encode())

    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_model", "gpt-5-mini")
    monkeypatch.setattr(settings, "ai_reasoning_effort", "low")
    monkeypatch.setattr(llm, "urlopen", fake_urlopen)
    monkeypatch.setattr("app.ai.usage_log.assert_quota_or_raise", lambda: {})
    llm._openai_chat(system="s", user="u", json_response=True)
    assert sent["reasoning_effort"] == "low"
