"""화면별 AI 질문 범위 — out_of_scope · scope_refusal · 추천 질문."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ai.constitution import (
    _CH2_KEYWORDS,
    _EXPLAIN_KEYWORDS,
    _OPINION_KEYWORDS,
    _STATISTICS_KEYWORDS,
    _contains_any,
)
from app.ai.bundles.comparison import is_comparison_question
from app.ai.bundles.registry import suggested_questions
from app.ai.schemas import AiApp, AiPurpose, ScreenRedirectHint


@dataclass(frozen=True)
class _RedirectTarget:
    panel: str
    label: str
    example_question: str
    benefit: str


@dataclass(frozen=True)
class PanelCapability:
    panel: str
    label: str
    bundle_id: str
    blocked_keywords: tuple[str, ...]
    redirects: tuple[tuple[tuple[str, ...], _RedirectTarget], ...]
    on_screen_questions: tuple[str, ...]


# --- 범위 밖 (일반 ChatGPT) ---
_OUT_OF_SCOPE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.I)
    for p in [
        r"너는\s*누구",
        r"당신은\s*누구",
        r"who\s+are\s+you",
        r"chatgpt",
        r"날씨",
        r"코스피|코스닥|주식\s*시장|나스닥|s&p",
        r"엑셀|vlookup|피벗",
        r"번역\s*해|translate",
        r"코딩|python|javascript|프로그래밍\s*짜",
        r"시\s*집|레시피|맛집",
        r"오늘\s*기분|심심",
    ]
]

_CH2_HELP_KEYWORDS = (
    "ch2",
    "사용법",
    "어떻게 쓰",
    "기능",
    "화면",
    "매크로",
    "실거래",
    "감정평가",
    "통계분석",
    "회귀",
    "추세",
    "예측",
    "전환율",
    "전월세",
    "전세환산",
)

_TREND_KEYWORDS = (
    "거래량",
    "거래 추이",
    "거래변동",
    "거래 변동",
    "volume",
    "장기추세",
    "장기 추세",
    "long term",
    "cagr",
    "변동률",
    "변곡",
    "연도별",
    "yearly",
    "추이",
    "추세",
)

_REGRESSION_KEYWORDS = (
    "회귀계수",
    "회귀식",
    "회귀 계수",
    "coefficient",
    "vif",
    "다중공선",
    "ols",
    "adj r",
    "r²",
    "신뢰구간",
    "예측값",
    "y_hat",
)

_REDIRECT_TREND = _RedirectTarget(
    panel="LongTermTrendPanel",
    label="장기추세 화면",
    example_question="거래량 감소 추이는?",
    benefit="거래량 변화와 가격 추세",
)

_REDIRECT_REGRESSION = _RedirectTarget(
    panel="RegressionCard",
    label="회귀분석 화면",
    example_question="VIF가 높으면 어떻게 하나요?",
    benefit="회귀·VIF·계수",
)

_REDIRECT_COMPARE = _RedirectTarget(
    panel="TwinRegionPanel",
    label="지역 비교 화면",
    example_question="유사 지역과 비교해 주세요.",
    benefit="지역·scope 비교",
)

_COMPARE_KEYWORDS = (
    "지역 비교",
    "다른 지역",
    "유사 지역",
    "twin",
    "비교분석",
)

PANEL_CAPABILITIES: dict[str, PanelCapability] = {
    "RegressionCard": PanelCapability(
        panel="RegressionCard",
        label="회귀분석",
        bundle_id="regression_diagnostic",
        blocked_keywords=_TREND_KEYWORDS + _COMPARE_KEYWORDS,
        redirects=(
            (_TREND_KEYWORDS, _REDIRECT_TREND),
            (_COMPARE_KEYWORDS, _REDIRECT_COMPARE),
        ),
        on_screen_questions=(
            "왜 연식 계수가 음수인가요?",
            "Adj R²는 어떻게 해석하나요?",
            "VIF가 높으면 어떻게 하나요?",
            "로그회귀와 선형회귀 차이는?",
            "신뢰구간이 넓은 이유는?",
        ),
    ),
    "RegressionScatterCard": PanelCapability(
        panel="RegressionScatterCard",
        label="회귀 산점도",
        bundle_id="regression_diagnostic",
        blocked_keywords=_TREND_KEYWORDS + _COMPARE_KEYWORDS,
        redirects=(
            (_TREND_KEYWORDS, _REDIRECT_TREND),
            (_COMPARE_KEYWORDS, _REDIRECT_COMPARE),
        ),
        on_screen_questions=(
            "통제 전·후 산점도 차이는?",
            "r은 작은데 β가 유의한 이유는?",
            "부분회귀도 기울기선은 무엇인가요?",
            "부분 R²는 어떻게 봐야 하나요?",
            "왜 통제 전 산점도도 필요한가요?",
        ),
    ),
    "ModelSelectionCard": PanelCapability(
        panel="ModelSelectionCard",
        label="모형 추천·비교",
        bundle_id="recommend_diagnostic",
        blocked_keywords=_TREND_KEYWORDS,
        redirects=(
            (_TREND_KEYWORDS, _REDIRECT_TREND),
        ),
        on_screen_questions=(
            "왜 이 변수 블록이 제외됐나요?",
            "AIC와 BIC 차이는?",
            "추천과 모형 비교 차이는?",
            "linear vs log는 어떻게 고르나요?",
            "Forward가 멈춘 이유는?",
        ),
    ),
    "RecommendationCard": PanelCapability(
        panel="RecommendationCard",
        label="모형 탐색·판정",
        bundle_id="recommend_diagnostic",
        blocked_keywords=_TREND_KEYWORDS,
        redirects=(
            (_TREND_KEYWORDS, _REDIRECT_TREND),
        ),
        on_screen_questions=(
            "AI 진단을 요약해 주세요.",
            "왜 예측이 부적합한가요?",
            "Twin을 써도 안 되면 어떻게 하나요?",
            "다음에 무엇을 하면 좋나요?",
            "설명형 회귀는 어떻게 활용하나요?",
        ),
    ),
    "BuildingRegressionPanel": PanelCapability(
        panel="BuildingRegressionPanel",
        label="집합 회귀분석",
        bundle_id="regression_diagnostic",
        blocked_keywords=_TREND_KEYWORDS + _COMPARE_KEYWORDS,
        redirects=(
            (_TREND_KEYWORDS, _RedirectTarget(
                panel="TrendCard",
                label="추세 카드",
                example_question="거래량 감소 패턴이 보이나요?",
                benefit="연도별 거래·가격 추세",
            )),
            (_COMPARE_KEYWORDS, _REDIRECT_COMPARE),
        ),
        on_screen_questions=(
            "이 결과를 어떻게 해석하나요?",
            "로그회귀와 선형회귀 차이는?",
            "신뢰구간이 넓은 이유는?",
            "VIF가 높으면 어떻게 하나요?",
        ),
    ),
    "CommercialRegressionPanel": PanelCapability(
        panel="CommercialRegressionPanel",
        label="상가·공장 회귀",
        bundle_id="regression_diagnostic",
        blocked_keywords=_TREND_KEYWORDS + _COMPARE_KEYWORDS,
        redirects=(
            (_TREND_KEYWORDS, _RedirectTarget(
                panel="TrendCard",
                label="추세 화면",
                example_question="거래량 추이를 요약해 주세요.",
                benefit="거래량·가격 추세",
            )),
            (_COMPARE_KEYWORDS, _REDIRECT_COMPARE),
        ),
        on_screen_questions=(
            "공식이 어떻게 만들어졌나요?",
            "신뢰구간이 넓은 이유는?",
            "VIF가 높으면 어떻게 하나요?",
        ),
    ),
    "LandRegressionTab": PanelCapability(
        panel="LandRegressionTab",
        label="토지 회귀",
        bundle_id="regression_diagnostic",
        blocked_keywords=_TREND_KEYWORDS + _COMPARE_KEYWORDS,
        redirects=((_TREND_KEYWORDS, _REDIRECT_TREND), (_COMPARE_KEYWORDS, _REDIRECT_COMPARE)),
        on_screen_questions=(
            "면적 계수는 어떻게 봐야 하나요?",
            "신뢰구간이 넓은 이유는?",
            "표본수가 적으면 어떤 문제가 생기나요?",
        ),
    ),
    "PaidMatrixCell": PanelCapability(
        panel="PaidMatrixCell",
        label="토지 매트릭스",
        bundle_id="matrix_cell_explain",
        blocked_keywords=_TREND_KEYWORDS + ("회귀계수", "vif", "ols"),
        redirects=((_TREND_KEYWORDS, _REDIRECT_TREND),),
        on_screen_questions=(
            "이 결과를 어떻게 해석하나요?",
            "용도지역별 차이를 설명해 주세요.",
            "신뢰구간이 넓은 이유는?",
        ),
    ),
    "LongTermTrendPanel": PanelCapability(
        panel="LongTermTrendPanel",
        label="장기추세",
        bundle_id="trend_diagnostic",
        blocked_keywords=_REGRESSION_KEYWORDS,
        redirects=((_REGRESSION_KEYWORDS, _REDIRECT_REGRESSION),),
        on_screen_questions=(
            "장기추세를 요약해 주세요.",
            "거래량 감소 패턴이 보이나요?",
            "변곡점은 언제인가요?",
            "CAGR는 어떻게 봐야 하나요?",
        ),
    ),
    "TrendCard": PanelCapability(
        panel="TrendCard",
        label="추세",
        bundle_id="trend_diagnostic",
        blocked_keywords=_REGRESSION_KEYWORDS,
        redirects=((_REGRESSION_KEYWORDS, _REDIRECT_REGRESSION),),
        on_screen_questions=(
            "연도별 추이를 요약해 주세요.",
            "거래량 감소 패턴이 보이나요?",
            "최근 상승 원인을 통계적으로 설명해 주세요.",
        ),
    ),
    "PredictionCard": PanelCapability(
        panel="PredictionCard",
        label="예측",
        bundle_id="prediction_explain",
        blocked_keywords=_TREND_KEYWORDS + _COMPARE_KEYWORDS,
        redirects=((_TREND_KEYWORDS, _REDIRECT_TREND),),
        on_screen_questions=(
            "예측값과 신뢰구간을 설명해 주세요.",
            "신뢰구간(PI)이 넓은 이유는?",
            "예측구간과 평균 신뢰구간 차이는?",
        ),
    ),
    "FloorIndexPanel": PanelCapability(
        panel="FloorIndexPanel",
        label="층별 지수",
        bundle_id="floor_index_diagnostic",
        blocked_keywords=_TREND_KEYWORDS + _COMPARE_KEYWORDS,
        redirects=((_TREND_KEYWORDS, _REDIRECT_TREND),),
        on_screen_questions=(
            "층별 지수를 어떻게 해석하나요?",
            "기준층은 어떻게 정해지나요?",
        ),
    ),
    "RentListCard": PanelCapability(
        panel="RentListCard",
        label="주거 전월세",
        bundle_id="rent_conversion",
        blocked_keywords=_TREND_KEYWORDS + _COMPARE_KEYWORDS,
        redirects=(),
        on_screen_questions=(
            "왜 단순평균 전환율인가요?",
            "적용 전환율은 공식값인가요?",
            "전세전환값은 시세인가요?",
            "연립은 왜 편차가 큰가요?",
            "읍면동 전환율이 없을 때는?",
        ),
    ),
    "SangkwonCard": PanelCapability(
        panel="SangkwonCard",
        label="상권분석",
        bundle_id="sangkwon_reb",
        blocked_keywords=_TREND_KEYWORDS + _COMPARE_KEYWORDS,
        redirects=(),
        on_screen_questions=(
            "임대료와 임대수입이 다른 이유는?",
            "연간 임대료는 어떻게 환산하나요?",
            "공실률을 NOI에 곱하면 안 되는 이유는?",
            "연간 투자수익률은 평균인가요 복리인가요?",
            "이 상권 공표는 주거 전월세와 같나요?",
        ),
    ),
    "CommercialFloorIndexPanel": PanelCapability(
        panel="CommercialFloorIndexPanel",
        label="상가·공장 효용지수",
        bundle_id="floor_index_diagnostic",
        blocked_keywords=_TREND_KEYWORDS,
        redirects=((_TREND_KEYWORDS, _REDIRECT_TREND),),
        on_screen_questions=(
            "층별 지수를 어떻게 해석하나요?",
            "기준층은 어떻게 정해지나요?",
            "면적형 지수는 어떻게 봐야 하나요?",
        ),
    ),
}

_DEFAULT_CAPABILITY = PANEL_CAPABILITIES["RegressionCard"]


def get_panel_capability(panel: str) -> PanelCapability:
    return PANEL_CAPABILITIES.get(panel, _DEFAULT_CAPABILITY)


def is_out_of_scope_message(message: str) -> bool:
    text = message.strip()
    return any(p.search(text) for p in _OUT_OF_SCOPE_PATTERNS)


def is_ch2_related_message(message: str) -> bool:
    """CH2 통계·화면·방법론 관련 질문인지 (범위 밖이면 False)."""
    if is_out_of_scope_message(message):
        return False
    if is_comparison_question(message):
        return True
    if _contains_any(message, _STATISTICS_KEYWORDS):
        return True
    if _contains_any(message, _EXPLAIN_KEYWORDS):
        return True
    if _contains_any(message, _OPINION_KEYWORDS):
        return True
    if _contains_any(message, _CH2_KEYWORDS):
        return True
    if _contains_any(message, _CH2_HELP_KEYWORDS):
        return True
    if _contains_any(message, _TREND_KEYWORDS):
        return True
    if _contains_any(message, _REGRESSION_KEYWORDS):
        return True
    return False


def is_statistics_theory_message(message: str) -> bool:
    """일반 통계이론 — panel blocked 토픽이어도 허용."""
    return _contains_any(message, _STATISTICS_KEYWORDS)


@dataclass
class PanelScopeMismatch:
    panel_label: str
    topic_label: str
    redirect: _RedirectTarget


def check_panel_scope_fit(panel: str, message: str) -> PanelScopeMismatch | None:
    """현재 panel에서 답할 수 없는 질문이면 redirect 정보 반환."""
    if is_statistics_theory_message(message):
        return None
    if is_comparison_question(message):
        return None
    cap = get_panel_capability(panel)
    msg = message.strip()
    for keywords, target in cap.redirects:
        if _contains_any(msg, keywords):
            if any(k in keywords for k in _TREND_KEYWORDS) and cap.bundle_id == "trend_diagnostic":
                continue
            if any(k in keywords for k in _REGRESSION_KEYWORDS) and cap.bundle_id == "regression_diagnostic":
                continue
            topic = target.label
            if _contains_any(msg, _TREND_KEYWORDS):
                topic = "거래량·장기추세"
            elif _contains_any(msg, _REGRESSION_KEYWORDS):
                topic = "회귀·VIF·계수"
            elif _contains_any(msg, _COMPARE_KEYWORDS):
                topic = "지역 비교"
            return PanelScopeMismatch(panel_label=cap.label, topic_label=topic, redirect=target)
    return None


def out_of_scope_answer(panel: str, app: AiApp = "built") -> str:
    cap = get_panel_capability(panel)
    examples = cap.on_screen_questions[:4]
    lines = [
        "저는 **CH2 통계분석 어시스턴트**입니다.",
        "",
        "현재 화면의 **통계·회귀분석·장기추세·통계이론·CH2 사용법** 등에 대해 답변할 수 있습니다.",
        "일반 ChatGPT 질문(날씨·주식·번역·코딩 등)은 범위 밖입니다.",
        "",
        "예를 들어 다음과 같은 질문을 해보세요.",
    ]
    for ex in examples:
        lines.append(f"• {ex}")
    return "\n".join(lines)


def scope_refusal_answer(mismatch: PanelScopeMismatch) -> str:
    t = mismatch.redirect
    return (
        f"현재 **{mismatch.panel_label}** 화면에는 **{mismatch.topic_label}** 정보가 없습니다.\n\n"
        f"**{t.label}**에서 같은 질문을 하시면 {t.benefit}을(를) 함께 분석해 드릴 수 있습니다.\n\n"
        f"예: 「{t.example_question}」"
    )


def panel_question_hints(
    panel: str,
    purpose: AiPurpose = "statistics",
    *,
    app: AiApp = "built",
) -> tuple[list[str], list[ScreenRedirectHint]]:
    cap = get_panel_capability(panel)
    on_screen = list(cap.on_screen_questions[:5])
    if not on_screen:
        on_screen = suggested_questions(panel, purpose, app=app)[:5]

    other: list[ScreenRedirectHint] = []
    seen: set[str] = set()
    for _keywords, target in cap.redirects:
        if target.panel in seen:
            continue
        seen.add(target.panel)
        other.append(
            ScreenRedirectHint(
                panel=target.panel,
                label=target.label,
                example_question=target.example_question,
            )
        )
    return on_screen, other
