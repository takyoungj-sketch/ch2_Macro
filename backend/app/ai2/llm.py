"""AI2 문장 해석. 화면 어시스턴트와 같은 OpenAI 클라이언트만 쓰고, 프롬프트와 세션은 따로다."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from app.ai.llm import _extract_number_tokens, _openai_chat, llm_configured
from app.ai2.case_tools import UNAVAILABLE_ANALYSIS
from app.ai2.catalog import get_spec, list_specs
from app.ai2.types import AnalysisContext

_LOG = logging.getLogger(__name__)

_FORBIDDEN_REPORT = ("적정", "매수", "매도", "싸다", "전망")

_SYSTEM = """당신은 CH2 AI2다. 화면 통계 어시스턴트가 아니다. 회귀나 가격을 계산하지 않는다.
문장을 분석 맥락 JSON으로만 바꾼다.
허용 키: region, property_type, analysis_type, target, period, measure, claim.
analysis_type은 허용 목록에 있는 값만 쓴다. 목록에 없으면 null.
property_type은 apartment, land, built, collective_shop, collective_factory, rent, profile 또는 null.
measure는 total, unit_price 또는 null.
claim은 적정가·감정을 묻는 경우에만 appraisal, 아니면 null.
지역 전체는 target을 "region"으로 둔다. 단지 또는 도로 이름은 target 문자열이다.
표본 수, 가격, 지수를 넣지 않는다. JSON 외의 문장은 쓰지 않는다.
"""

_PERIOD = re.compile(r"^\d{4}-\d{2}~\d{4}-\d{2}$")
_PROPERTIES = frozenset({
    "apartment",
    "land",
    "built",
    "collective_shop",
    "collective_factory",
    "rent",
    "profile",
})
_MEASURES = frozenset({"total", "unit_price"})


@dataclass
class LlmDraft:
    region: str | None = None
    property_type: str | None = None
    analysis_type: str | None = None
    target: str | None = None
    period: str | None = None
    measure: str | None = None
    claim: str | None = None
    unknown_analysis: bool = False


def draft_from_model_json(data: dict) -> LlmDraft | None:
    if not isinstance(data, dict):
        return None
    analysis = data.get("analysis_type")
    unknown = False
    if analysis is not None:
        analysis = str(analysis).strip() or None
    if analysis is not None and get_spec(analysis) is None and analysis not in UNAVAILABLE_ANALYSIS:
        unknown = True
        analysis = None
    prop = data.get("property_type")
    if prop is not None:
        prop = str(prop).strip()
        if prop not in _PROPERTIES:
            prop = None
    measure = data.get("measure")
    if measure is not None:
        measure = str(measure).strip()
        if measure not in _MEASURES:
            measure = None
    claim = "appraisal" if data.get("claim") == "appraisal" else None
    period = data.get("period")
    if period is not None:
        period = str(period).strip()
        if not _PERIOD.match(period):
            period = None
    region = _text(data.get("region"))
    target = _text(data.get("target"))
    if not any((region, prop, analysis, target, period, measure, claim, unknown)):
        return None
    return LlmDraft(
        region=region,
        property_type=prop,
        analysis_type=analysis,
        target=target,
        period=period,
        measure=measure,
        claim=claim,
        unknown_analysis=unknown,
    )


def read_sentence(sentence: str, ctx: AnalysisContext) -> LlmDraft | None:
    if not llm_configured():
        return None
    payload = {
        "sentence": sentence,
        "current": ctx.to_dict(),
        "analyses": [
            {
                "analysis_type": spec.analysis_type,
                "property_types": sorted(spec.property_types),
                "needs_target": spec.needs_target,
                "needs_measure": spec.needs_measure,
            }
            for spec in list_specs()
        ],
        "unavailable": sorted(UNAVAILABLE_ANALYSIS),
    }
    try:
        raw = _openai_chat(
            system=_SYSTEM,
            user=json.dumps(payload, ensure_ascii=False),
            temperature=0,
        )
    except Exception:
        _LOG.warning("AI2 sentence call failed", exc_info=True)
        return None
    if not raw:
        return None
    return draft_from_model_json(_load_json(raw) or {})


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _load_json(raw: str) -> dict | None:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


_REPORT_SYSTEM = """당신은 CH2 AI2다. 화면 통계 어시스턴트가 아니다.
아래 사실만으로 한국어 존댓말 2~4문장을 쓴다.
사실에 없는 숫자를 만들지 않는다. 있는 숫자도 바꾸지 않는다.
적정가, 매수, 매도, 싸다, 전망을 쓰지 않는다.
어느 결과가 맞다고 고르지 않는다. 도구 이름을 늘어놓지 않는다.
원문에 「쌍둥이는 결론으로 쓰지 않음」, 「어느 결과를 채택하지 않습니다」, 「전세 시세가 아닙니다.」가 있으면 그 문장을 그대로 남긴다.
"""

_KEPT_CLAUSES = (
    "쌍둥이는 결론으로 쓰지 않음",
    "어느 결과를 채택하지 않습니다",
    "전세 시세가 아닙니다.",
)


def numbers_allowed(source: str, prose: str) -> bool:
    source_numbers = {_normalize_number(token) for token in _extract_number_tokens(source)}
    prose_numbers = {_normalize_number(token) for token in _extract_number_tokens(prose)}
    return prose_numbers <= source_numbers


def restore_required_clauses(source: str, prose: str) -> str:
    text = prose.strip()
    for clause in _KEPT_CLAUSES:
        if clause in source and clause not in text:
            text = f"{text} {clause}".strip()
    return text


def accept_report(source: str, prose: str) -> bool:
    text = prose.strip()
    if not text:
        return False
    if any(word in text for word in _FORBIDDEN_REPORT):
        return False
    return numbers_allowed(source, text)


def choose_alternative(alternatives: list, facts: dict) -> str | None:
    if not llm_configured():
        return None
    allowed = [getattr(alt, "id", None) for alt in alternatives]
    payload = {
        "allowed": [
            {"id": getattr(alt, "id", None), "change": getattr(alt, "change", None)}
            for alt in alternatives
        ],
        "facts": facts,
    }
    try:
        raw = _openai_chat(system=_CHOOSE_SYSTEM, user=json.dumps(payload, ensure_ascii=False), temperature=0)
    except Exception:
        _LOG.warning("AI2 tool choice failed", exc_info=True)
        return None
    data = _load_json(raw or "")
    if not data:
        return None
    tool_id = data.get("tool_id")
    if tool_id not in allowed:
        return None
    return str(tool_id)


_CHOOSE_SYSTEM = """당신은 CH2 AI2다. 화면 통계 어시스턴트가 아니다. 계산하지 않는다.
다음 도구는 allowed에 있는 id 중 정확히 하나다.
JSON만 출력한다. 형식은 {"tool_id":"허용된 id"} 다.
목록에 없는 도구는 고르지 않는다.
"""


def write_report(source: str) -> str | None:
    if not llm_configured():
        return None
    try:
        raw = _openai_chat(system=_REPORT_SYSTEM, user=source, temperature=0)
    except Exception:
        _LOG.warning("AI2 report call failed", exc_info=True)
        return None
    if not raw or not accept_report(source, raw):
        return None
    return restore_required_clauses(source, raw)


def _normalize_number(token: str) -> str:
    if "." in token:
        token = token.rstrip("0").rstrip(".")
    return token
