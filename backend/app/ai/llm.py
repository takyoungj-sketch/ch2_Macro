"""Optional OpenAI 호출 — chat · polish · web synthesis."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.ai.constitution import ROUTE_PROMPTS, SYSTEM_PERSONALITY
from app.ai.schemas import AiDiagnosticPack
from app.ai.web_search import WebHit
from app.config import settings

_LOG = logging.getLogger(__name__)

_POLISH_SYSTEM = """당신은 CH2 Macro 통계 분석 어시스턴트의 **문장 다듬기** 역할입니다.

규칙:
- 입력 템플릿의 **숫자·단위·표·섹션 제목(###)을 절대 바꾸지 마세요.**
- 새로운 수치·표본·계수·예측값을 **추가하지 마세요.**
- 가격·투자·적정가·전망 표현 금지.
- 한국어 존댓말, 간결·중립 톤.
- 마크다운 구조(###, |, **, -) 유지.
"""

_WEB_SYSTEM = """당신은 CH2 Macro 통계 분석 어시스턴트입니다.

역할:
- 제공된 **웹 검색 스니펫만** 요약합니다.
- CH2 내부 회귀·예측 수치와 **혼동하지 마세요.**

출력 형식:
### 요약
(2~4문장)

### 근거 (출처)
- 각 항목: 제목 + 핵심 1문장 + URL (반드시 포함)

### 주의
- 외부 자료 한계, 시점·지역 차이, 투자·적정가 금지

금지: 적정가, 투자 추천, 미래 가격 전망, Bundle에 없는 CH2 수치 invent.
"""


def llm_configured() -> bool:
    return bool((settings.openai_api_key or "").strip())


def polish_enabled() -> bool:
    return llm_configured() and bool(settings.ai_polish_enabled)


def _model() -> str:
    return (settings.openai_model or "gpt-4o-mini").strip()


def _openai_chat(
    *,
    system: str,
    user: str,
    temperature: float = 0.2,
    timeout: float = 45,
) -> Optional[str]:
    key = (settings.openai_api_key or "").strip()
    if not key:
        return None
    body = {
        "model": _model(),
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    req = Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices") or []
        if not choices:
            return None
        content = (choices[0].get("message") or {}).get("content")
        return str(content).strip() if content else None
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        _LOG.warning("OpenAI call failed: %s", exc)
        return None


def _extract_number_tokens(text: str) -> set[str]:
    raw = re.findall(r"\d[\d,]*\.?\d*", text)
    return {re.sub(r"[^\d.]", "", t) for t in raw if re.sub(r"[^\d.]", "", t)}


def numbers_preserved(template: str, candidate: str) -> bool:
    """템플릿 숫자가 polish 결과에 모두 남아 있는지."""
    orig = _extract_number_tokens(template)
    if not orig:
        return True
    got = _extract_number_tokens(candidate)
    return orig.issubset(got)


def chat_completion(
    *,
    user_message: str,
    route: str,
    bundle: Optional[AiDiagnosticPack] = None,
    session_summary: str = "",
) -> Optional[str]:
    if not llm_configured():
        return None

    pack_json = bundle.model_dump() if bundle else {}
    system = SYSTEM_PERSONALITY + "\n\n" + ROUTE_PROMPTS.get(route, "")
    user_content = {
        "question": user_message,
        "route": route,
        "bundle": pack_json,
        "session_summary": session_summary or None,
    }
    return _openai_chat(
        system=system,
        user=json.dumps(user_content, ensure_ascii=False),
    )


def polish_template_answer(
    *,
    template_answer: str,
    user_message: str,
    route: str,
    scope_label: str = "",
) -> Optional[str]:
    if not polish_enabled():
        return None
    user = json.dumps(
        {
            "question": user_message,
            "route": route,
            "scope_label": scope_label or None,
            "template_answer": template_answer,
        },
        ensure_ascii=False,
    )
    polished = _openai_chat(system=_POLISH_SYSTEM, user=user, temperature=0.1)
    if not polished:
        return None
    if not numbers_preserved(template_answer, polished):
        _LOG.warning("polish rejected: numeric drift detected")
        return None
    return polished


def synthesize_web_answer(
    *,
    message: str,
    hits: list[WebHit],
    scope_label: str = "",
) -> Optional[str]:
    if not llm_configured():
        return None
    sources = [
        {"title": h.title, "url": h.url, "snippet": h.snippet, "provider": h.source}
        for h in hits[:6]
    ]
    user = json.dumps(
        {
            "question": message,
            "ch2_scope_label": scope_label or None,
            "web_sources": sources,
        },
        ensure_ascii=False,
    )
    return _openai_chat(system=_WEB_SYSTEM, user=user, temperature=0.2)
