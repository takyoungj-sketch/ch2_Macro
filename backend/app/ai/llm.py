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

_OPEN_MODE_SYSTEM = """너는 CH2 Macro의 통계 분석 보조 AI다.

CH2 Macro 화면에서 제공하는 통계, 데이터, 분석 결과 및
그 결과를 이해하기 위해 필요한 통계 개념에 대해서만 답변한다.

사용자의 질문이 현재 CH2 Macro의 데이터나 분석과 관련되어 있으면
질문의 표현이 다소 넓더라도 적절히 해석하여 답변한다.
(예: 이 화면에서 「MAPE가 뭔데?」 → 이번 결과와 붙여 짧게 설명)

판단 기준은 질문의 단어가 아니라 **현재 화면/데이터와 연결되어 있는지**다.
screen_facts의 service·page·scope·analysis_type을 현재 컨텍스트로 쓴다.

현재 화면과 무관한 일반적인 생활, 투자, 날씨, 정치, 잡담,
다른 자산 전망, 코딩 공부 등에는 답하지 않는다.
거절할 때는 한두 문장으로 제한임을 알리고, 이 화면에서 물어볼 수 있는
통계 질문만 짧게 제안한다. 직전 답변의 결론·요약·Adj R²·MAPE를 복사하지 않는다.

화면 결과를 쉬운 말이나 보고서 문체로 풀어 쓰는 것은 허용한다.
감정평가액·적정가·투자·매수/매도·가격 전망은 제시하지 않는다.
CH2를 감정평가로 대체하지 않는다.
감정평가·적정가 적용 가능 여부 질문에는 화면 분석을 반복하지 말고 제한만 안내한다.

화면에 제공되지 않은 데이터를 임의로 만들어내지 않는다.
screen_facts에 있는 숫자·표본·계수는 그대로 인용한다.

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
        from app.ai.usage_log import assert_quota_or_raise, record_llm_call

        assert_quota_or_raise()
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices") or []
        if not choices:
            return None
        content = (choices[0].get("message") or {}).get("content")
        usage = data.get("usage") or {}
        details = usage.get("prompt_tokens_details") or {}
        try:
            record_llm_call(
                requested_model=model,
                served_model=str(data.get("model") or "") or None,
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
                cached_tokens=int(details.get("cached_tokens") or 0),
            )
        except Exception:
            _LOG.warning("AI usage log failed", exc_info=True)
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
