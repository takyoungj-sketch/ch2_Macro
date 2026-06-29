"""질문 Intent — summary / methodology / interpretation / comparison."""

from __future__ import annotations

from enum import Enum

from app.ai.bundles.comparison import (
    is_comparison_question,
    is_model_comparison_followup,
    is_model_comparison_question,
    is_scope_comparison_question,
)


class QuestionIntent(str, Enum):
    SUMMARY = "summary"
    METHODOLOGY = "methodology"
    INTERPRETATION = "interpretation"
    COMPARISON = "comparison"


_METHODOLOGY_KEYWORDS = (
    "로그",
    "선형",
    "방법론",
    "ols",
    "모델",
    "spec",
    "공식",
    "trade-off",
    "트레이드",
    "vif",
    "다중공선",
    "box-cox",
    "box cox",
    "semi-log",
    "반로그",
    "더미",
    "hc3",
    "강건",
    "회귀식",
    "변수 선택",
)

_SUMMARY_KEYWORDS = (
    "요약",
    "패턴",
    "추이",
    "거래량",
    "장기",
    "변곡",
    "개요",
    "한눈",
    "전체",
    "몇 건",
    "표본수",
    "표본 수",
    "n=",
    "얼마",
)

_INTERPRETATION_KEYWORDS = (
    "해석",
    "어떻게",
    "왜",
    "의미",
    "지수",
    "계수",
    "설명",
    "무엇",
    "뭐",
    "정의",
)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(k.lower() in lower for k in keywords)


def classify_intent(
    message: str,
    route: str,
    *,
    comparison_hint: bool = False,
    model_comparison_hint: bool = False,
) -> QuestionIntent:
    """Route 이후 질문별 Intent 분류."""
    if model_comparison_hint or is_model_comparison_question(message):
        return QuestionIntent.METHODOLOGY
    if comparison_hint or is_scope_comparison_question(message):
        return QuestionIntent.COMPARISON
    if route == "opinion" or _contains_any(message, _METHODOLOGY_KEYWORDS):
        return QuestionIntent.METHODOLOGY
    if _contains_any(message, _SUMMARY_KEYWORDS):
        return QuestionIntent.SUMMARY
    if route == "explain" or _contains_any(message, _INTERPRETATION_KEYWORDS):
        return QuestionIntent.INTERPRETATION
    return QuestionIntent.INTERPRETATION
