"""실험: 일상 대화 톤 허용 — 전달 사실은 CH2 지식·화면 통계만."""

from __future__ import annotations

import re
from typing import Any

from app.ai.panel_capabilities import (
    is_ch2_related_message,
    is_out_of_scope_message,
    out_of_scope_answer,
    suggested_questions,
)
from app.ai.schemas import AiApp
from app.config import settings

_SMALLTALK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.I)
    for p in [
        r"^(?:안녕(?:하(?:세요|십니까|)?)?|반가워|처음\s*뵙)",
        r"^(?:고마워|감사(?:합니다|해요|)?|thanks|thank you)",
        r"^(?:잘\s*가|bye|goodbye)",
        r"^ㅎㅇ$",
        r"^(?:도와줘|help)\s*$",
        r"^(?:hello|hi|hey)\b",
    ]
]

_PIVOT_HINTS = (
    "이 화면",
    "회귀",
    "표본",
    "통계",
    "ch2",
    "추천",
    "산점",
    "추세",
)


def casual_dialogue_enabled() -> bool:
    return bool(settings.ai_casual_dialogue_enabled)


def is_casual_smalltalk(message: str) -> bool:
    text = message.strip()
    if len(text) > 80:
        return False
    if any(p.search(text) for p in _SMALLTALK_PATTERNS):
        return True
    if text in ("?", "!", "…", "...") :
        return False
    return False


def is_substantive_off_topic(message: str) -> bool:
    """CH2·통계와 무관한 **내용** 질문 (인사 제외)."""
    if is_ch2_related_message(message):
        return False
    if is_casual_smalltalk(message):
        return False
    if is_out_of_scope_message(message):
        return True
    # 키워드 없는 짧은 잡담도 off-topic 처리 (날씨 좋네 등)
    if len(message.strip()) < 120 and not any(h in message for h in _PIVOT_HINTS):
        # 숫자·통계 힌트 없으면 잡담 가능성
        if re.search(r"(날씨|심심|점심|커피|농담|재미)", message):
            return True
    return False


def _screen_teaser(diagnostics: dict[str, Any]) -> str | None:
    bits: list[str] = []
    n = diagnostics.get("n")
    adj = diagnostics.get("adj_r_squared")
    if n is not None:
        bits.append(f"표본 **{n}건**")
    if adj is not None:
        try:
            bits.append(f"Adj R² **{float(adj):.3f}**")
        except (TypeError, ValueError):
            pass
    if not bits:
        return None
    return "현재 화면 기준: " + " · ".join(bits)


def casual_smalltalk_answer(message: str, *, scope_label: str) -> str:
    lower = message.strip().lower()
    if any(x in lower for x in ("고마", "감사", "thank")):
        body = "천만에요. CH2 화면 통계 해석이 필요하면 편하게 물어보세요."
    elif any(x in lower for x in ("안녕", "hello", "hi", "ㅎㅇ", "반가")):
        body = (
            f"안녕하세요. **{scope_label}** 화면의 회귀·통계 결과를 함께 읽어 드리는 CH2 어시스턴트입니다. "
            "가격 판단·투자 조언은 드리지 않습니다."
        )
    elif any(x in lower for x in ("잘 가", "bye")):
        body = "네, 분석 화면에서 또 필요하시면 불러 주세요."
    else:
        body = "네, 말씀하세요. CH2 통계·화면 해석 위주로 도와드릴게요."
    return "\n\n".join(["### 답변", "", body])


def casual_off_topic_answer(
    message: str,
    *,
    panel: str,
    app: AiApp,
    scope_label: str,
    diagnostics: dict[str, Any],
) -> str:
    base = out_of_scope_answer(panel, app)
    teaser = _screen_teaser(diagnostics)
    lines = [
        "### 답변",
        "",
        "그 주제는 **일반 상식·잡담** 영역이라, CH2에 없는 내용은 답하지 않습니다. "
        "대신 **CH2 Macro 지식**과 **지금 화면 통계**만 근거로 말씀드릴 수 있어요.",
    ]
    if teaser:
        lines.extend(["", teaser])
    lines.extend(["", "---", "", base])
    return "\n".join(lines)


def casual_followups(panel: str, app: AiApp) -> list[str]:
    return suggested_questions(panel, "statistics", app=app)[:4]


def should_auto_explain_screen(message: str) -> bool:
    """질문과 무관하게 화면 회귀 내러티브를 덤프할지."""
    if is_casual_smalltalk(message):
        return False
    if casual_dialogue_enabled() and is_substantive_off_topic(message):
        return False
    return is_ch2_related_message(message)


def casual_unrelated_prompt(*, scope_label: str) -> str:
    return "\n\n".join(
        [
            "### 답변",
            "",
            f"**{scope_label}** 화면의 회귀·통계 해석을 도와드립니다. "
            "표본수, 변수 방향, 설명력 등 궁금한 점을 구체적으로 질문해 주세요.",
        ]
    )
