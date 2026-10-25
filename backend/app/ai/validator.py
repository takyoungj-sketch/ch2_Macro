"""응답 검증 — 금지 표현·면책."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.ai.constitution import DEFAULT_DISCLAIMER, is_refusal_message

_FORBIDDEN_OUTPUT = [
    re.compile(r"적정\s*가격\s*(?:입니다|이에요|이다)"),
    re.compile(r"투자\s*(?:를\s*)?추천"),
    re.compile(r"반드시\s*오를"),
    re.compile(r"반드시\s*내릴"),
    re.compile(r"싸(?:다|요)\s*[,.]?\s*추천"),
]


def numeric_claims(text: str) -> set[Decimal]:
    """숫자 목록 표식과 CH2/R2 같은 식별자를 제외한 수치 토큰.

    수치의 존재 여부를 검증하며, 지표와 수치의 의미적 대응까지 보증하지 않는다.
    """
    text = re.sub(r"(?m)^\s*\d+[.)]\s+", "", text)
    out: set[Decimal] = set()
    for match in re.finditer(r"(?<![A-Za-z0-9_.])[+\-−]?\d+(?:,\d{3})*(?:\.\d+)?(?:[eE][+\-]?\d+)?", text):
        try:
            out.add(Decimal(match.group().replace(",", "").replace("−", "-")))
        except InvalidOperation:
            continue
    return out


def numbers_grounded(candidate: str, sources: str) -> bool:
    allowed = numeric_claims(sources)
    # 0.55를 55%로 설명하는 표시 변환은 허용한다. 새 통계 계산은 아니다.
    def checked_percent(match: re.Match) -> str:
        value = Decimal(match.group(1).replace("−", "-"))
        if abs(value) <= 100 and value / 100 in allowed:
            return ""
        return match.group()
    remaining = re.sub(r"(?<![A-Za-z0-9_.])([+\-−]?\d+(?:\.\d+)?)\s*%", checked_percent, candidate)
    return numeric_claims(remaining).issubset(allowed)


def validate_answer(text: str, route: str) -> str:
    """금지 출력 완화 — refusal/ch2/opinion에서 가치판단 패턴 제거."""
    if route == "refusal":
        return text
    out = text
    for pat in _FORBIDDEN_OUTPUT:
        if pat.search(out):
            out = pat.sub("[해당 표현은 CH2 정책상 제공하지 않습니다]", out)
    return out


def ensure_disclaimer(route: str, existing: str | None) -> str | None:
    if route == "refusal":
        return existing
    if route in ("ch2", "explain", "opinion"):
        return existing or DEFAULT_DISCLAIMER
    return existing


def reject_if_user_refusal_topic_in_opinion(message: str, route: str) -> str:
    if route == "opinion" and is_refusal_message(message):
        return "refusal"
    return route
