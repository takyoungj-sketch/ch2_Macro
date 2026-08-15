"""통계 개념 KB — 정의형은 UI ? 유도, 해석형은 화면 facts 결합."""

from __future__ import annotations

import re
from typing import Any

_STATS_TERMS: dict[str, str] = {
    "p-value": "p-value",
    "vif": "VIF",
    "ols": "OLS",
    "adj r": "Adj R²",
    "신뢰구간": "예측 신뢰구간",
    "r²": "R²",
    "r-squared": "R²",
    "mape": "MAPE",
    "cv-mape": "CV-MAPE",
    "계수": "회귀 계수",
    "전환율": "적용 전환율",
    "전세전환": "전세전환값",
    "월세전환": "월세전환값",
    "상권": "상권 공표",
    "순영업소득": "순영업소득",
    "공실률": "공실률",
    "소득수익률": "소득수익률",
    "임대가격지수": "임대가격지수",
}

_DEFINITION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.I)
    for p in [
        r"(?:란|이란|란\?|이란\?)\s*$",
        r"(?:뭐야|무엇|정의|의미)(?:\?|요|니|인가)?\s*$",
        r"^what is ",
        r"^define ",
        r"(?:설명해\s*줘|알려\s*줘)\s*$",
    ]
]

_INTERPRETATION_HINTS = (
    "어떻게",
    "왜",
    "이번",
    "이 결과",
    "이 표본",
    "중간",
    "낮",
    "높",
    "제한",
    "해석",
)


def is_pure_definition_question(message: str) -> bool:
    """교과서 정의만 묻는 질문 — UI ? 유도."""
    text = message.strip()
    if not any(_DEFINITION_PATTERNS):
        pass
    if any(p.search(text) for p in _DEFINITION_PATTERNS):
        if not any(h in text for h in _INTERPRETATION_HINTS):
            return True
    # "Adj R²란?" style
    if re.search(r"(?:란|이란)\??\s*$", text) and not any(h in text for h in ("왜", "이번", "이 결과")):
        return True
    return False


def _detect_term(message: str) -> str | None:
    lower = message.lower()
    if "p값" in message or "p-value" in lower or "p value" in lower:
        return "p-value"
    if "다중공선" in message or "vif" in lower:
        return "vif"
    if "adj" in lower and ("r" in lower or "²" in message):
        return "adj r"
    if "mape" in lower and "cv" in lower:
        return "cv-mape"
    if "mape" in lower:
        return "mape"
    if "신뢰구간" in message or "confidence interval" in lower:
        return "신뢰구간"
    if "ols" in lower:
        return "ols"
    if "계수" in message and is_pure_definition_question(message):
        return "계수"
    if any(k in message for k in ("상권", "순영업", "공실률", "소득수익", "임대가격지수", "상업용")):
        if "전환율" in message:
            return "상권"
        if "공실" in message:
            return "공실률"
        if "순영업" in message:
            return "순영업소득"
        if "소득수익" in message:
            return "소득수익률"
        if "지수" in message:
            return "임대가격지수"
        return "상권"
    if "전환율" in message:
        return "전환율"
    if "전세전환" in message or "전세환산" in message:
        return "전세전환"
    if "월세전환" in message or "월세환산" in message:
        return "월세전환"
    for key in _STATS_TERMS:
        if key.lower() in lower:
            return key
    return None


def redirect_to_glossary_answer(term: str | None) -> str:
    label = _STATS_TERMS.get(term or "", term or "해당 지표")
    sangkwon = term in {"상권", "순영업소득", "공실률", "소득수익률", "임대가격지수"}
    where = (
        "상권분석 표 지표 옆 **`?` 버튼**"
        if sangkwon
        else "회귀 결과 카드·계수 표 옆 **`?` 버튼**"
    )
    return (
        f"**{label}**의 기본 정의는 {where}에서 확인할 수 있습니다.\n\n"
        "AI 어시스턴트는 **이번 화면 수치에 맞춘 해석**에 집중합니다. "
        f"예: 「이 표본에서 {label}이 중간인 이유는?」, 「유의 변수가 적은 이유는?」"
    )


def answer_statistics_question(message: str) -> str | None:
    if is_pure_definition_question(message):
        return redirect_to_glossary_answer(_detect_term(message))
    return None


def answer_statistics_with_context(message: str, diagnostics: dict[str, Any]) -> str | None:
    """정의+화면 수치 결합 (LLM 없을 때 짧은 폴백)."""
    term = _detect_term(message)
    if not term:
        return None
    label = _STATS_TERMS.get(term, term)
    n = diagnostics.get("n")
    adj = diagnostics.get("adj_r_squared")
    parts = [f"**{label}** — 이번 화면 기준:"]
    if n is not None:
        parts.append(f"- 표본 n={n}건")
    if adj is not None and term in ("adj r", "r²", "r-squared"):
        parts.append(f"- Adj R²={adj}")
    vif_list = diagnostics.get("vif")
    if term == "vif" and isinstance(vif_list, list) and vif_list:
        top = vif_list[0]
        if isinstance(top, dict):
            parts.append(f"- 예: {top.get('name')} VIF={top.get('vif')}")
    parts.append(
        f"기본 정의는 지표 옆 **`?`** 를 참고하세요. "
        "이번 결과 맥락 해석은 표본·변수·VIF·상관을 함께 봐야 합니다."
    )
    return "\n".join(parts)
