"""응답 검증 — 금지 표현·면책."""

from __future__ import annotations

import re

from app.ai.constitution import DEFAULT_DISCLAIMER, is_refusal_message

_FORBIDDEN_OUTPUT = [
    re.compile(r"적정\s*가격\s*(?:입니다|이에요|이다)"),
    re.compile(r"투자\s*(?:를\s*)?추천"),
    re.compile(r"반드시\s*오를"),
    re.compile(r"반드시\s*내릴"),
    re.compile(r"싸(?:다|요)\s*[,.]?\s*추천"),
]


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
