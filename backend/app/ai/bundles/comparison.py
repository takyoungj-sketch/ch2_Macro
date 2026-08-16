"""세션 scope 스냅샷 비교 — comparison bundle."""

from __future__ import annotations

import re
from typing import Any, Optional

from app.ai.sessions import AiSession

_MODEL_COMPARISON_HINTS = (
    "로그회귀",
    "로그 회귀",
    "log-log",
    "log log",
    "loglog",
    "semi-log",
    "semi log",
    "반로그",
    "선형회귀",
    "선형 회귀",
    "linear",
    "box-cox",
    "box cox",
    "종속",
    "독립변수",
    "모형",
    "모델",
    "ols",
)

_MODEL_COMPARISON_TRIGGERS = (
    "차이",
    "비교",
    " vs ",
    "versus",
    "무엇",
    "뭐",
    "다른",
    "나을",
    "좋을",
    "trade-off",
    "트레이드",
)

_SCOPE_COMPARISON_HINTS = (
    "scope",
    "지역",
    "동",
    "읍",
    "면",
    "구",
    "시",
    "다른 scope",
    "다른 지역",
    "운암",
    "가경",
    "와 ",
    "과 ",
)


def is_model_comparison_question(message: str) -> bool:
    """로그·선형·log-log 등 모형/방법론 비교 질문."""
    lower = message.lower()
    has_model = any(h in message or h in lower for h in _MODEL_COMPARISON_HINTS)
    has_log_pair = ("log" in lower and ("log-log" in lower or "log log" in lower or "로그" in message))
    has_trigger = any(t in message or t in lower for t in _MODEL_COMPARISON_TRIGGERS)
    if has_log_pair and has_trigger:
        return True
    return has_model and has_trigger


def is_scope_comparison_question(message: str) -> bool:
    """지역·scope 간 비교 — 모형 비교와 구분."""
    if is_model_comparison_question(message):
        return False
    lower = message.lower()
    keys = ("비교", "차이", "왜 다르", "달라", " vs ", "versus", "다른 scope", "다른 지역")
    if not any(k in message or k in lower for k in keys):
        return False
    # scope 비교: 지명·scope 언급, 또는 명시적 두 대상 (A와 B)
    if any(h in message for h in _SCOPE_COMPARISON_HINTS):
        return True
    if re.search(r"[가-힣]{2,}\s*(?:과|와|랑)\s*[가-힣]{2,}", message):
        # "가경동과 운암동" — but exclude "로그회귀와 log-log"
        if not is_model_comparison_question(message):
            return True
    # follow-up: "표본수 차이", "Adj R² 차이" after session — handled by keys alone
    if "adj" in lower or "표본" in message or "r²" in message or "r2" in lower:
        return True
    return False


def is_comparison_question(message: str) -> bool:
    """하위 호환 — scope 비교만 (모형 비교 제외)."""
    return is_scope_comparison_question(message)


def narrative_scope_comparison(session: AiSession, *, current_label: str) -> Optional[str]:
    snaps = [s for s in session.context_snapshots if isinstance(s, dict)]
    if len(snaps) < 2:
        return None

    prev, curr = snaps[-2], snaps[-1]
    prev_label = str(prev.get("scope", {}).get("region_label") or prev.get("scope_label") or "이전 scope")
    curr_label = str(curr.get("scope", {}).get("region_label") or curr.get("scope_label") or current_label)

    if prev_label.strip() == curr_label.strip():
        return None

    def _fmt_snap(s: dict[str, Any]) -> list[str]:
        lines = []
        n = s.get("n")
        adj = s.get("adj_r_squared")
        if n is not None:
            lines.append(f"표본 **{n}건**")
        if adj is not None:
            lines.append(f"Adj R² **{float(adj):.3f}**")
        return lines

    prev_stats = _fmt_snap(prev)
    curr_stats = _fmt_snap(curr)

    body = [
        "### 요약",
        "",
        f"**{prev_label}**과(와) **{curr_label}** scope를 CH2 세션 기록 기준으로 비교했습니다.",
        "",
        "### 이유",
        "",
        f"- **{prev_label}**: " + (" · ".join(prev_stats) if prev_stats else "진단 수치 없음"),
        f"- **{curr_label}**: " + (" · ".join(curr_stats) if curr_stats else "진단 수치 없음"),
        "",
        "표본수·설명력·필터·기간이 다르면 같은 변수라도 계수 부호·유의성이 달라질 수 있습니다. "
        "인과·어느 쪽이 '맞는' 가격인지 판단하지 않습니다.",
        "",
        "### 사용한 데이터",
        "",
        "✓ CH2 세션 scope 기록",
        "✓ 회귀분석 요약(표본·Adj R²)",
        "",
        "### 주의",
        "",
        "세션에 저장된 **최근 두 scope**만 비교합니다. 다른 panel·다른 변수는 포함되지 않을 수 있습니다.",
    ]
    return "\n".join(body)
