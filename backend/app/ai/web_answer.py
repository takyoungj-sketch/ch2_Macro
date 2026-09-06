"""웹 검색 결과 → 내러티브 답변 (템플릿 · LLM)."""

from __future__ import annotations

from app.ai.web_search import WebHit


def web_template_answer(message: str, hits: list[WebHit], *, scope_label: str = "") -> str:
    if not hits:
        scope = f" ({scope_label})" if scope_label else ""
        return (
            f"### 요약\n\n"
            f"「{message.strip()}」{scope}에 대한 **외부 검색 결과를 찾지 못했습니다.**\n\n"
            "동의한 외부조사에서 쓸 만한 결과를 찾지 못했습니다. "
            "질문을 더 구체적으로 해 주세요. 목록은 망라가 아닙니다."
        )

    lines = ["### 요약", "", f"「{message.strip()}」에 대한 **외부 자료** 요약입니다 (CH2 내부 통계와 별개).", ""]
    if scope_label:
        lines.append(f"- **현재 CH2 scope 참고:** {scope_label}")
        lines.append("")

    lines.append("### 근거 (출처)")
    for i, h in enumerate(hits[:5], 1):
        snippet = h.snippet.replace("\n", " ").strip()
        if len(snippet) > 180:
            snippet = snippet[:177] + "…"
        lines.append(f"{i}. **{h.title}**")
        lines.append(f"   - {snippet}")
        lines.append(f"   - 출처: {h.url}")
        lines.append("")

    lines.append("### 주의")
    lines.append(
        "- 위 내용은 **외부 웹·공공 자료**이며 CH2 거래통계와 **직접 연결되지 않습니다.**"
    )
    lines.append("- 정책·금리 등은 시점에 따라 달라질 수 있습니다.")
    lines.append("- 시기가 겹쳐도 그 때문에 가격이 움직였다고 단정하지 마세요. CH2는 그 효과를 측정하지 않습니다.")
    lines.append("- 개별 물건 가격·투자 판단 근거로 사용하지 마세요.")

    return "\n".join(lines)
