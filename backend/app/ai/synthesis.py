"""Grounded Dialogue — LLM 합성 + 템플릿 폴백."""

from __future__ import annotations

from typing import Any, Optional

from app.ai.built_narrative import NarrativeResult
from app.ai.knowledge.product import product_knowledge_excerpt
from app.ai.llm import llm_configured, numbers_preserved, synthesize_grounded_answer
from app.ai.schemas import AiContext, AiDiagnosticPack, AnalysisExplain


def _explain_payload(explain: AnalysisExplain | None) -> dict[str, Any] | None:
    if not explain:
        return None
    return {
        "title": explain.title,
        "summary": explain.summary,
        "formula": explain.formula,
        "interpretation": explain.interpretation[:6],
        "limitations": explain.limitations[:4],
        "interpretation_hints": explain.interpretation_hints[:6],
    }


def _template_fallback(
    template_answer: str,
    *,
    followups: list[str] | None = None,
    trust_level: str = "medium",
    trust_sources: list[str] | None = None,
) -> NarrativeResult:
    return NarrativeResult(
        answer=template_answer,
        followups=followups or [],
        trust_level=trust_level,  # type: ignore[arg-type]
        trust_sources=trust_sources or ["CH2 템플릿"],
    )


def try_grounded_synthesis(
    *,
    message: str,
    route: str,
    context: AiContext,
    bundle: AiDiagnosticPack,
    template_answer: str,
    template_followups: list[str] | None = None,
    narrative_result: NarrativeResult | None = None,
    session_summary: str = "",
    planner_text: str = "",
    caveats_text: str = "",
    history_text: str = "",
) -> tuple[str, list[str] | None, NarrativeResult | None, bool]:
    """
    in-scope 질문: LLM 합성 시도 → 실패 시 템플릿.
    Returns: answer, followups, narrative_result, llm_used
    """
    if not llm_configured():
        return template_answer, template_followups, narrative_result, False

    product = product_knowledge_excerpt(
        app=context.app,
        panel=context.panel,
        message=message,
    )
    explain = _explain_payload(context.explain)
    synthesized = synthesize_grounded_answer(
        user_message=message,
        route=route,
        scope_label=str(
            context.scope.region_label or bundle.diagnostics.get("scope_label") or "선택 scope"
        ),
        product_knowledge=product,
        bundle=bundle,
        explain=explain,
        purpose=context.purpose,
        session_summary=session_summary,
        template_fallback=template_answer,
        planner_text=planner_text,
        caveats_text=caveats_text,
        history_text=history_text,
    )
    if not synthesized:
        return template_answer, template_followups, narrative_result, False

    if not numbers_preserved(template_answer, synthesized):
        return template_answer, template_followups, narrative_result, False

    followups = template_followups or (narrative_result.followups if narrative_result else None)
    nr = NarrativeResult(
        answer=synthesized,
        followups=followups or [],
        focus_var=narrative_result.focus_var if narrative_result else None,
        trust_level=narrative_result.trust_level if narrative_result else "medium",
        trust_sources=(narrative_result.trust_sources if narrative_result else []) + ["GPT 합성"],
    )
    return synthesized, followups, nr, True


def bundle_number_tokens(bundle: AiDiagnosticPack) -> set[str]:
    """Bundle diagnostics에서 추출한 숫자 토큰 (validator 보조)."""
    tokens: set[str] = set()

    def _walk(obj: Any) -> None:
        if isinstance(obj, (int, float)):
            s = str(obj)
            if "." in s:
                tokens.add(s.rstrip("0").rstrip(".") if "." in s else s)
            tokens.add(s)
        elif isinstance(obj, dict):
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for v in obj:
                _walk(v)

    _walk(bundle.diagnostics)
    _walk(bundle.summary_lines)
    return tokens
