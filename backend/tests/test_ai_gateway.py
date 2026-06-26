"""AI Router·Validator 테스트."""

from unittest.mock import patch

from app.ai.constitution import classify_route, is_refusal_message
from app.ai.llm import numbers_preserved
from app.ai.orchestrator import handle_chat
from app.ai.schemas import AiChatRequest, AiContext, AiScope
from app.ai.validator import validate_answer
from app.ai.web_answer import web_template_answer
from app.ai.web_search import WebHit


def test_refusal_appropriate_price():
    assert is_refusal_message("이 물건은 적정가격인가?")
    assert classify_route("이 물건은 적정가격인가?") == "refusal"


def test_refusal_future_price():
    assert classify_route("가경동은 앞으로 오를까?") == "refusal"


def test_opinion_log_regression():
    assert classify_route("복합부동산은 로그회귀가 좋을까?") == "opinion"


def test_statistics_pvalue():
    assert classify_route("p-value가 뭐야?") == "statistics"


def test_explain_why_result():
    assert classify_route("왜 이 결과가 나왔나요?") == "explain"


def test_chat_refusal_response():
    req = AiChatRequest(
        message="적정가격인가요?",
        context=AiContext(
            app="built",
            panel="RegressionCard",
            scope=AiScope(region_label="가경동"),
            facts={"primary": {"n": 140, "prediction": 97040}},
        ),
    )
    resp = handle_chat(req)
    assert resp.route == "refusal"
    assert resp.session_id
    assert any(e.type == "refusal_policy" for e in resp.evidence)
    assert "적정" not in resp.answer or "판단하지 않습니다" in resp.answer


def test_chat_regression_bundle():
    req = AiChatRequest(
        message="왜 연식이 음수인가?",
        context=AiContext(
            app="built",
            panel="RegressionCard",
            facts={
                "primary": {
                    "n": 120,
                    "adj_r_squared": 0.89,
                    "scope_label": "흥덕구",
                    "coefficients": [
                        {"name": "연식", "estimate": -726, "p_value": 0.00001},
                    ],
                },
                "correlations": [
                    {"label": "연식", "variable": "building_age", "pearson_r": -0.116},
                ],
                "vif": [{"name": "building_age", "vif": 1.8}],
            },
        ),
    )
    resp = handle_chat(req)
    assert resp.route == "ch2"
    assert resp.bundle_id == "regression_diagnostic"
    assert "### 요약" in resp.answer
    assert "낮아지는 경향" in resp.answer
    assert "인과관계" in resp.answer
    assert "estimate=" not in resp.answer
    assert "### 💡 AI Insight" in resp.answer or "다른 변수를 통제" in resp.answer
    assert resp.suggested_followups
    assert any("연식" in q for q in resp.suggested_followups)
    assert resp.trust_level in ("high", "medium", "low")


def test_explain_small_sample_detailed():
    req = AiChatRequest(
        message="이 결과를 어떻게 해석하나요?",
        context=AiContext(
            app="built",
            panel="RegressionCard",
            scope=AiScope(region_label="흥덕구"),
            facts={
                "primary": {
                    "n": 77,
                    "adj_r_squared": 0.72,
                    "scope_label": "흥덕구",
                    "coefficients": [
                        {"name": "gross_area", "estimate": 120.5, "p_value": 0.0001},
                    ],
                },
            },
        ),
    )
    resp = handle_chat(req)
    assert "77건" in resp.answer
    assert "방향성" in resp.answer or "주의" in resp.answer
    assert resp.trust_level == "medium"


def test_explain_interpret_built():
    req = AiChatRequest(
        message="이 결과를 어떻게 해석하나요?",
        context=AiContext(
            app="built",
            panel="RegressionCard",
            scope=AiScope(region_label="흥덕구 가경동"),
            facts={
                "primary": {
                    "n": 2031,
                    "adj_r_squared": 0.8206,
                    "scope_label": "흥덕구",
                    "coefficients": [
                        {"name": "building_age", "estimate": -50.2, "p_value": 0.001},
                        {"name": "gross_area", "estimate": 120.5, "p_value": 0.0001},
                    ],
                },
                "correlations": [
                    {"label": "연식", "variable": "building_age", "pearson_r": -0.054},
                ],
            },
        ),
    )
    resp = handle_chat(req)
    assert resp.route == "explain"
    assert "### 요약" in resp.answer
    assert "설명력" in resp.answer
    assert "### 💡 AI Insight" in resp.answer
    assert "| 영향 | 크기 |" in resp.answer
    assert "사용한 데이터" in resp.answer
    assert "회귀분석" in resp.answer
    assert "estimate=" not in resp.answer
    assert "coef=None" not in resp.answer


def test_land_regression_narrative():
    req = AiChatRequest(
        message="이 결과를 어떻게 해석하나요?",
        context=AiContext(
            app="land",
            panel="PaidMatrixCell",
            scope=AiScope(region_label="충북 청주시 흥덕구"),
            facts={
                "n": 88,
                "adj_r_squared": 0.61,
                "model_type": "log",
                "zone_type": "제1종일반주거",
                "land_category": "대",
                "coefficients": [
                    {"name": "area_sqm", "label": "면적", "coef": 0.42, "p": 0.0001},
                ],
            },
        ),
    )
    resp = handle_chat(req)
    assert resp.route == "explain"
    assert "### 요약" in resp.answer
    assert "88건" in resp.answer


def test_collective_regression_narrative():
    req = AiChatRequest(
        message="로그회귀와 선형회귀 차이는?",
        context=AiContext(
            app="collective",
            panel="BuildingRegressionPanel",
            scope=AiScope(region_label="래미안", asset_type="apartment"),
            facts={
                "n": 142,
                "adj_r_squared": 0.55,
                "display_name": "래미안",
                "coefficients": [
                    {"name": "exclusive_area", "label": "전용면적", "coef": 120.5, "p": 0.001},
                ],
            },
        ),
    )
    resp = handle_chat(req)
    assert resp.route in ("ch2", "opinion", "explain")
    assert resp.session_id


def test_scope_comparison():
    ctx = AiContext(
        app="built",
        panel="RegressionCard",
        scope=AiScope(region_label="가경동"),
        facts={"primary": {"n": 50, "adj_r_squared": 0.7, "coefficients": []}},
    )
    r1 = handle_chat(AiChatRequest(message="회귀 해석", context=ctx))
    ctx2 = AiContext(
        app="built",
        panel="RegressionCard",
        scope=AiScope(region_label="운암동"),
        facts={"primary": {"n": 120, "adj_r_squared": 0.8, "coefficients": []}},
    )
    r2 = handle_chat(
        AiChatRequest(message="가경동과 운암동 차이를 비교해 주세요", context=ctx2, session_id=r1.session_id)
    )
    assert "비교" in r2.answer or "가경동" in r2.answer
    assert "운암동" in r2.answer


def test_validate_strips_bad_phrases():
    bad = "이 물건은 적정가격입니다. 투자를 추천합니다."
    out = validate_answer(bad, "ch2")
    assert "적정가격입니다" not in out


def test_land_trend_narrative():
    req = AiChatRequest(
        message="장기추세를 요약해 주세요.",
        context=AiContext(
            app="land",
            panel="TrendCard",
            purpose="market_analysis",
            scope=AiScope(region_label="충북 청주시 흥덕구"),
            facts={
                "zone_type": "제1종일반주거",
                "land_category": "대",
                "rows": [
                    {"year": 2020, "count": 12, "mean_unit_price_per_sqm": 800000},
                    {"year": 2021, "count": 18, "mean_unit_price_per_sqm": 920000},
                    {"year": 2022, "count": 15, "mean_unit_price_per_sqm": 950000},
                ],
            },
        ),
    )
    resp = handle_chat(req)
    assert resp.bundle_id == "trend_diagnostic"
    assert resp.route in ("ch2", "explain")
    assert "### 요약" in resp.answer
    assert "2020" in resp.answer or "상승" in resp.answer or "하락" in resp.answer


def test_built_prediction_narrative():
    req = AiChatRequest(
        message="예측값과 신뢰구간을 설명해 주세요.",
        context=AiContext(
            app="built",
            panel="PredictionCard",
            purpose="prediction",
            scope=AiScope(region_label="흥덕구", asset_type="detached"),
            facts={
                "y_hat": 85000,
                "pi_lower": 40000,
                "pi_upper": 130000,
                "ci_lower": 78000,
                "ci_upper": 92000,
                "regression_n": 2031,
                "adj_r_squared": 0.82,
                "warnings": [],
            },
        ),
    )
    resp = handle_chat(req)
    assert resp.bundle_id == "prediction_explain"
    assert resp.route in ("ch2", "explain", "statistics")
    assert "### 요약" in resp.answer or "예측" in resp.answer or "신뢰구간" in resp.answer
    assert "85,000" in resp.answer or "85000" in resp.answer or "예측" in resp.answer


def test_web_route_classify():
    assert classify_route("기준금리 정책이 뭐야?") == "web"


def test_web_template_answer():
    hits = [
        WebHit(
            title="한국은행 기준금리",
            url="https://example.com/bok",
            snippet="기준금리는 3.0%입니다.",
            source="tavily",
        )
    ]
    ans = web_template_answer("금리 정책", hits, scope_label="청주시")
    assert "### 요약" in ans
    assert "https://example.com/bok" in ans
    assert "청주시" in ans


@patch("app.ai.orchestrator.web_search")
def test_web_chat_with_hits(mock_search):
    mock_search.return_value = [
        WebHit(
            title="국토교통부 토지정책",
            url="https://example.com/molit",
            snippet="토지 거래 규제 완화 논의.",
            source="duckduckgo",
        )
    ]
    req = AiChatRequest(
        message="국토부 토지 정책 요약해줘",
        context=AiContext(
            app="land",
            panel="TrendCard",
            scope=AiScope(region_label="충북 청주시"),
            facts={"rows": []},
        ),
    )
    resp = handle_chat(req)
    assert resp.route == "web"
    assert resp.evidence
    assert any(e.url == "https://example.com/molit" for e in resp.evidence)
    assert "example.com" in resp.answer or "국토" in resp.answer


def test_numbers_preserved_polish_guard():
    template = "### 요약\n\n표본 **77건**, Adj R² **0.720**."
    ok = "### 요약\n\n표본 **77건**이며 Adj R²는 **0.720**입니다."
    bad = "### 요약\n\n표본 **100건**."
    assert numbers_preserved(template, ok)
    assert not numbers_preserved(template, bad)
