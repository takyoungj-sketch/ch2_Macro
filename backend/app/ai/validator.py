"""응답 검증 — 금지 표현·면책."""

from __future__ import annotations

import json
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


# 0~1 비율로 두고 퍼센트로 말할 수 있는 항목. 계수·표본수·이미 퍼센트인 값은 여기 없다.
_RATIO_KEYS = frozenset({
    "r_squared",
    "adj_r_squared",
    "adj_r2",
    "price_adj_r_squared",
    "model_adj_r_squared",
    "partial_r_squared",
    "similarity_score",
    "count_share_by_type",
    "amount_share_by_type",
})


def _json_value(sources: str):
    text = sources.lstrip()
    if not text.startswith(("{", "[")):
        return None
    try:
        value, _end = json.JSONDecoder().raw_decode(text)
    except json.JSONDecodeError:
        return None
    return value


def _ratio_display_bases(sources: str) -> set[Decimal]:
    """지정한 비율 항목 가운데 절댓값이 1 이하인 값만 100배 퍼센트로 허용한다."""
    found: set[Decimal] = set()

    def add(value: object) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return
        try:
            number = Decimal(str(value))
        except InvalidOperation:
            return
        if abs(number) <= 1:
            found.add(number)

    def walk(node: object, under_ratio: bool) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, under_ratio or str(key) in _RATIO_KEYS)
        elif isinstance(node, list):
            for item in node:
                walk(item, under_ratio)
        elif under_ratio:
            add(node)

    root = _json_value(sources)
    if root is not None:
        walk(root, False)
    return found


def numbers_grounded(candidate: str, sources: str) -> bool:
    allowed = numeric_claims(sources)
    # 설명력·유사도·비중처럼 0~1 비율만 55% 같은 표시로 허용한다.
    bases = _ratio_display_bases(sources)

    def checked_percent(match: re.Match) -> str:
        value = Decimal(match.group(1).replace("−", "-"))
        if abs(value) <= 100 and value / 100 in bases:
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
