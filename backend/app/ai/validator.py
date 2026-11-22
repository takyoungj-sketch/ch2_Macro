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


# 이미 퍼센트 단위인 항목. 설명력처럼 0~1 비율로 둔 값과 구분한다.
_PERCENT_KEYS = frozenset({
    "vacancy",
    "rent_income_share",
    "other_income_share",
    "opex_share",
    "noi_pct",
    "income_yield",
    "capital_yield",
    "investment_yield",
    "conversion",
    "building_rate",
    "region_rate",
    "pool_rate",
})


def _is_percent_key(key: str) -> bool:
    return key in _PERCENT_KEYS or key == "mape" or key.endswith("_mape") or key.endswith("_pct")


def _json_value(sources: str):
    text = sources.lstrip()
    if not text.startswith(("{", "[")):
        return None
    try:
        value, _end = json.JSONDecoder().raw_decode(text)
    except json.JSONDecodeError:
        return None
    return value


def _split_percent_values(sources: str) -> tuple[set[Decimal], set[Decimal]]:
    """퍼센트 항목의 숫자와, 그 밖에 있는 숫자."""
    percent_vals: set[Decimal] = set()
    outside: set[Decimal] = set()

    def add(bucket: set[Decimal], value: object) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return
        try:
            bucket.add(Decimal(str(value)))
        except InvalidOperation:
            return

    def walk(node: object, under_percent: bool) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, under_percent or _is_percent_key(str(key)))
        elif isinstance(node, list):
            for item in node:
                walk(item, under_percent)
        elif under_percent:
            add(percent_vals, node)
        else:
            add(outside, node)

    root = _json_value(sources)
    if root is not None:
        walk(root, False)
    return percent_vals, outside


def _ratio_display_bases(sources: str) -> set[Decimal]:
    """100을 곱해 퍼센트로 말할 수 있는 비율.

    수익률·공실률·전환율·오차율처럼 이미 퍼센트인 숫자는 빼되,
    같은 숫자가 비율 항목에도 있으면 비율 표기는 남긴다.
    """
    allowed = numeric_claims(sources)
    percent_vals, outside = _split_percent_values(sources)
    return (allowed - percent_vals) | outside


def numbers_grounded(candidate: str, sources: str) -> bool:
    allowed = numeric_claims(sources)
    # 설명력 0.55를 55%로 말하는 표시 변환만 허용한다. 이미 퍼센트인 값에 100을 다시 곱하지 않는다.
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
