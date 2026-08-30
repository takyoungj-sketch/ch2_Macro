"""CH2 AI 헌법 — 시스템 프롬프트·금지 패턴·고정 면책."""

from __future__ import annotations

import re

CONSTITUTION_VERSION = "2"

SYSTEM_PERSONALITY = """당신은 CH2 Macro의 분석 보조 AI입니다.

역할:
- CH2가 계산한 숫자(Bundle·History)만 인용합니다.
- 분석 목적에 맞는 경로를 제안하고, 지금 화면에서 실행 가능한지 말합니다.
- 엔진 결과의 한계를 먼저 말하고, Caveat는 조건→판단→다음 행동만 합니다.

허용: 분석 경로 추천 (통합회귀가 적합, 인접지역 검토 등)
금지:
- 가격·투자·적정가격·매수/매도·저평가 판단
- 미래 가격 전망
- Bundle/History에 없는 수치·신뢰도 % 만들기
- 실행할 데이터가 없는데 기능만 추천

톤: 간결, 중립, 존댓말.
"""

ROUTE_PROMPTS: dict[str, str] = {
    "ch2": (
        "Grounded Dialogue: CH2 Facts·Product Knowledge·Playbook·Caveat·History만 사용. "
        "경로 질문이면 실행 가능성을 말하고 없는 계수를 invent하지 않음. "
        "질문에 직접 답 → 근거 2~4문장 → 한계 1문장. "
        "JSON/Bundle 수치를 인용하고 재계산 금지. "
        "기초 정의(Adj R²·VIF 등)는 UI ? 팝업으로 유도."
    ),
    "explain": (
        "AnalysisExplain + Bundle facts로 이번 결과 해석. "
        "새로운 수치 invent 금지. 정의만 묻으면 UI ? 안내."
    ),
    "statistics": (
        "순수 정의 질문은 UI ? 유도. "
        "해석형이면 Bundle facts와 결합해 설명."
    ),
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
        r"감정\s*평가",
        r"평가액",
        r"가치\s*평가",
        r"감정에\s*(?:적용|쓸|사용|쓰)",
        r"싸(?:다|요|니|게)?",
        r"비싸(?:다|요|니|게)?",
        r"투자\s*(?:할|해|가치|추천)",
        r"사(?:도|야)\s*(?:될|할)",
        r"팔(?:아|아야)",
        r"전망",
        r"오를(?:까|것|거)",
        r"내릴(?:까|것|거)",
        r"상승\s*(?:할|예상)",
        r"하락\s*(?:할|예상)",
        r"매수",
        r"매도",
        r"저평가",
        r"고평가",
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
    "어떻게 봐",
    "어떻게 읽",
    "이 화면",
    "무엇을 보여",
    "무슨 의미",
    "공식이",
    "한계",
    "주의",
    "이 결과가",
    "이번",
    "이 표본",
    "왜 단순평균",
    "왜 이 방법",
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
    "전환율",
    "단순평균",
    "원점회귀",
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


_ANALYSIS_PATH_HINTS = (
    "분석 경로",
    "어떻게 분석",
    "어떻게 접근",
    "통합회귀",
    "코호트",
    "어떤 분석",
    "어떤 경로",
    "인접지역",
    "지역회귀",
)

_INVESTMENT_RECOMMEND_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.I)
    for p in [
        r"(?:이|저)\s*(?:아파트|오피스텔|단지|물건|집).{0,24}추천",
        r"매수.{0,8}추천",
        r"투자.{0,8}추천",
    ]
]


def is_refusal_message(message: str) -> bool:
    text = message.strip()
    if any(p.search(text) for p in _INVESTMENT_RECOMMEND_PATTERNS):
        return True
    if not any(p.search(text) for p in _REFUSAL_PATTERNS):
        return False
    # 「분석 경로를 추천해 줘」는 허용. 매수·적정가는 그대로 거절.
    if any(h in text for h in _ANALYSIS_PATH_HINTS) and not any(
        k in text for k in ("매수", "매도", "투자", "적정", "저평가", "고평가", "감정")
    ):
        return False
    return True


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(k.lower() in lower for k in keywords)


def classify_route(message: str) -> str:
    """refusal | ch2 | explain | statistics | opinion | web"""
    if is_refusal_message(message):
        return "refusal"
    # 해석형 통계 질문은 explain/ch2 우선 (정의 KB 낭독 방지)
    from app.ai.stats_kb import is_pure_definition_question

    if _contains_any(message, _STATISTICS_KEYWORDS) and not is_pure_definition_question(message):
        if _contains_any(message, _EXPLAIN_KEYWORDS) or _contains_any(message, _CH2_KEYWORDS):
            return "explain"
    if _contains_any(message, _STATISTICS_KEYWORDS) and is_pure_definition_question(message):
        return "statistics"
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
