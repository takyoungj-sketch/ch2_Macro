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


_GROUNDED_SYSTEM = """당신은 CH2 Macro 통계 분석 어시스턴트입니다.

역할 (Grounded Dialogue):
- 사용자 질문에 **직접** 답합니다.
- Product Knowledge·Bundle facts·Explain만 근거로 사용합니다.
- Bundle에 없는 숫자·표본·계수·예측값을 **절대 invent하지 마세요.**

출력 형식 (마크다운):
### 답변
(질문에 맞는 2~5문장 — 이번 화면 수치 인용)

### 근거
- Bundle/Explain에서 인용한 사실 2~4개 (숫자 포함 가능)

### 한계
(표본·모형·데이터 한계 1문장)

금지: 적정가, 투자 추천, 미래 가격 전망, 교과서 정의 장문 나열(→ UI ? 유도).
기초 정의만 묻는 경우 한 줄로 UI ? 안내 후 이번 결과 해석으로 유도.
톤: 한국어 존댓말, 간결·중립.
"""

_CASUAL_SYNTHESIS_ADDON = """
[실험: Casual Dialogue]
- 짧은 인사·리액션은 자연스럽게 가능합니다.
- **사실·숫자·통계·제품 설명**은 Product Knowledge·Bundle·Explain만 사용하세요.
- Bundle에 없는 일반 상식(날씨·뉴스·코딩 등)은 답하지 말고 CH2 화면으로 부드럽게 유도하세요.
- 여전히 적정가·투자·전망 금지.
"""

_OPEN_MODE_SYSTEM = """당신은 CH2 Macro에 연동된 대화형 AI입니다. (Open Mode — 개발·검증)

목표:
- 사용자 질문에 **직접·자연스럽게** 답합니다.
- 통계·방법론·제품·일반 질문까지 폭넓게 대화할 수 있습니다.
- 연속 대화를 이어가며, 앞 턴의 맥락을 활용합니다.

화면 facts (soft):
- 제공된 `screen_facts`에 있는 **숫자·표본·계수**를 인용할 때는 **그대로** 쓰세요.
- screen_facts에 없는 화면 수치를 **새로 만들지 마세요.**
- 질문이 화면과 무관하면 facts를 무시해도 됩니다.

톤: 한국어 존댓말, 친절하고 명확. 마크다운 가능.
"""


def casual_synthesis_addon() -> str:
    from app.ai.casual_dialogue import casual_dialogue_enabled

    return _CASUAL_SYNTHESIS_ADDON if casual_dialogue_enabled() else ""


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
    model = _model()
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    # gpt-5* 계열은 temperature 커스텀 미지원 (default 1만 허용)
    if not model.lower().startswith("gpt-5"):
        body["temperature"] = temperature
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


def open_mode_chat_completion(
    *,
    user_message: str,
    scope_label: str,
    screen_facts: dict[str, Any],
    session_summary: str = "",
) -> Optional[str]:
    """Open Mode: 라우팅/템플릿 없이 LLM 직접 대화. screen_facts는 soft cite."""
    if not llm_configured():
        return None
    user_content = {
        "question": user_message,
        "scope_label": scope_label,
        "screen_facts": screen_facts,
        "recent_turns": session_summary or None,
    }
    return _openai_chat(
        system=_OPEN_MODE_SYSTEM,
        user=json.dumps(user_content, ensure_ascii=False),
        temperature=0.4,
    )


def synthesize_grounded_answer(
    *,
    user_message: str,
    route: str,
    scope_label: str,
    product_knowledge: str,
    bundle: Optional[AiDiagnosticPack] = None,
    explain: Optional[dict[str, Any]] = None,
    purpose: str = "statistics",
    session_summary: str = "",
    template_fallback: str = "",
) -> Optional[str]:
    """in-scope 질문 — Product Knowledge + Bundle + Explain 합성."""
    if not llm_configured():
        return None

    pack_json = bundle.model_dump() if bundle else {}
    system = (
        SYSTEM_PERSONALITY
        + "\n\n"
        + ROUTE_PROMPTS.get(route, "")
        + "\n\n"
        + _GROUNDED_SYSTEM
        + casual_synthesis_addon()
    )
    user_content = {
        "question": user_message,
        "route": route,
        "purpose": purpose,
        "scope_label": scope_label,
        "product_knowledge": product_knowledge,
        "bundle": pack_json,
        "explain": explain,
        "session_summary": session_summary or None,
        "template_fallback_hint": template_fallback[:800] if template_fallback else None,
    }
    synthesized = _openai_chat(
        system=system,
        user=json.dumps(user_content, ensure_ascii=False),
        temperature=0.25,
    )
    if not synthesized:
        return None
    if template_fallback and not numbers_preserved(template_fallback, synthesized):
        _LOG.warning("grounded synthesis rejected: numeric drift vs template")
        return None
    return synthesized


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
