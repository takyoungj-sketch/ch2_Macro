"""CH2 AI 헌법 — 시스템 프롬프트·금지 패턴·고정 면책."""

from __future__ import annotations

import re

CONSTITUTION_VERSION = "1"

SYSTEM_PERSONALITY = """당신은 CH2 Macro의 통계 분석 어시스턴트입니다.

역할:
- CH2 API·Reasoning Bundle에서 제공된 수치와 사실만 인용합니다.
- 시장 통계 패턴을 설명합니다.
- 표본·모형의 한계를 먼저 말합니다.

금지:
- 가격·투자·적정가격·매수/매도 판단
- 미래 가격 전망 ("오를 것이다", "내릴 것이다")
- 감정평가 대체
- Bundle에 없는 수치를 만들거나 재계산

톤: 간결, 중립, 존댓말. 추측·과장 없음.
"""

ROUTE_PROMPTS: dict[str, str] = {
    "ch2": "CH2 Facts만 사용. JSON/Bundle 수치를 인용하고 해석하세요. 재계산 금지.",
    "explain": "AnalysisExplain layer 내용을 자연어로 풀어 설명. 새로운 수치를 만들지 마세요.",
    "statistics": "일반 통계 개념만 설명. CH2 특정 지역 수치는 언급하지 마세요.",
    "opinion": "방법론·모델 trade-off만. '~할 수 있습니다' 수준. 가격·투자·전망 금지.",
    "web": "출처 URL을 evidence에 포함. CH2 내부 수치와 혼동하지 마세요.",
}

DEFAULT_DISCLAIMER = (
    "본 답변은 CH2 시장통계 분석 결과의 해석이며, "
    "감정평가·적정가격·투자 판단을 대체하지 않습니다."
)

WEB_DISCLAIMER = (
    "본 답변은 외부 웹·공공 자료 요약이며 CH2 거래통계와 별개입니다. "
    "시점·지역에 따라 달라질 수 있으며, 투자·적정가 판단 근거가 아닙니다."
)

SHORT_DISCLAIMER = "본 답변은 시장통계 해석이며 감정평가를 대체하지 않습니다."

OPINION_DISCLAIMER = (
    "아래는 통계 방법론에 대한 참고 의견이며, "
    "특정 자산의 가격·투자 적합성을 의미하지 않습니다."
)

REFUSAL_DISCLAIMER = (
    "CH2는 시장통계 분석 시스템입니다. "
    "개별 물건의 적정성·투자 여부는 전문가의 현장 조사와 판단이 필요합니다."
)

# 가격판단·투자·전망 — Refusal (Opinion으로 보내지 않음)
_REFUSAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.I)
    for p in [
        r"적정\s*가",
        r"적정\s*가격",
        r"싸(?:다|요|니|게)?",
        r"비싸(?:다|요|니|게)?",
        r"투자\s*(?:할|해|가치|추천)",
        r"사(?:도|야)\s*(?:될|할)",
        r"팔(?:아|아야)",
        r"추천\s*해",
        r"전망",
        r"오를(?:까|것|거)",
        r"내릴(?:까|것|거)",
        r"상승\s*(?:할|예상)",
        r"하락\s*(?:할|예상)",
        r"매수",
        r"매도",
        r"수익\s*(?:률|기대)",
    ]
]

_STATISTICS_KEYWORDS = (
    "p-value",
    "p value",
    "p값",
    "vif",
    "ols",
    "다중공선성",
    "box-cox",
    "box cox",
    "중심극한",
    "신뢰구간",
    "confidence interval",
    "r-squared",
    "r²",
    "adj r",
    "헤테로",
    "강건",
    "hc3",
    "더미변수",
    "반로그",
    "semi-log",
)

_EXPLAIN_KEYWORDS = (
    "왜 이 결과",
    "왜 이렇게",
    "어떻게 해석",
    "이 화면",
    "무엇을 보여",
    "무슨 의미",
    "공식이",
    "한계",
    "주의",
    "이 결과가",
)

_OPINION_KEYWORDS = (
    "로그회귀",
    "로그 회귀",
    "선형회귀",
    "방법론",
    "trade-off",
    "트레이드",
    "모델 비교",
    "어떤 모델",
    "좋을까",
    "나을까",
    "적합",
    "실험",
)

_WEB_KEYWORDS = (
    "금리",
    "한국은행",
    "국토부",
    "정부정책",
    "정책",
    "뉴스",
    "인구",
    "통계청",
    "논문",
)

_CH2_KEYWORDS = (
    "표본",
    "sample",
    "adj",
    "r²",
    "회귀",
    "계수",
    "연식",
    "음수",
    "vif",
    "상관",
    "산점",
    "예측",
    "prediction",
    "신뢰구간",
    "interval",
    "n=",
)


def is_refusal_message(message: str) -> bool:
    text = message.strip()
    return any(p.search(text) for p in _REFUSAL_PATTERNS)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(k.lower() in lower for k in keywords)


def classify_route(message: str) -> str:
    """refusal | ch2 | explain | statistics | opinion | web"""
    if is_refusal_message(message):
        return "refusal"
    if _contains_any(message, _STATISTICS_KEYWORDS):
        return "statistics"
    if _contains_any(message, _EXPLAIN_KEYWORDS):
        return "explain"
    if _contains_any(message, _OPINION_KEYWORDS) and not is_refusal_message(message):
        return "opinion"
    if _contains_any(message, _WEB_KEYWORDS):
        return "web"
    if _contains_any(message, _CH2_KEYWORDS):
        return "ch2"
    return "ch2"
