"""세션 scope 스냅샷 비교 — comparison bundle."""

from __future__ import annotations

from typing import Any, Optional

from app.ai.sessions import AiSession


def is_comparison_question(message: str) -> bool:
    keys = ("비교", "차이", "왜 다르", "달라", " vs ", "versus", "다른 scope", "다른 지역")
    lower = message.lower()
    return any(k in message or k in lower for k in keys)


def narrative_scope_comparison(session: AiSession, *, current_label: str) -> Optional[str]:
    snaps = [s for s in session.context_snapshots if isinstance(s, dict)]
    if len(snaps) < 2:
        return None

    prev, curr = snaps[-2], snaps[-1]
    prev_label = str(prev.get("scope", {}).get("region_label") or prev.get("scope_label") or "이전 scope")
    curr_label = str(curr.get("scope", {}).get("region_label") or curr.get("scope_label") or current_label)

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
