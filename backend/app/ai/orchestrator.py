"""AI Chat orchestrator — Router + Bundle + 템플릿/LLM."""

from __future__ import annotations

from typing import Any

from app.ai.bundles import build_bundle, resolve_bundle_id, suggested_questions
from app.ai.bundles.comparison import is_comparison_question, narrative_scope_comparison
from app.ai.built_explain import (
    built_prediction_explain,
    built_regression_explain_from_facts,
    interpret_built_regression,
)
from app.ai.built_narrative import NarrativeResult
from app.ai.collective_explain import collective_regression_explain_from_context
from app.ai.land_explain import land_matrix_regression_explain_from_facts, land_trend_explain
from app.ai.prediction_narrative import build_prediction_narrative
from app.ai.trend_narrative import build_trend_narrative
from app.ai.constitution import (
    DEFAULT_DISCLAIMER,
    OPINION_DISCLAIMER,
    REFUSAL_DISCLAIMER,
    SHORT_DISCLAIMER,
    WEB_DISCLAIMER,
    classify_route,
)
from app.ai.llm import (
    chat_completion,
    llm_configured,
    numbers_preserved,
    polish_enabled,
    polish_template_answer,
    synthesize_web_answer,
)
from app.ai.web_answer import web_template_answer
from app.ai.web_search import WebHit, web_search
from app.ai.schemas import (
    AiChatRequest,
    AiChatResponse,
    AiContext,
    AiDiagnosticPack,
    AiExplainRequest,
    AnalysisExplain,
    EvidenceItem,
)
from app.ai.sessions import SessionTurn, get_or_create, session_summary
from app.ai.stats_kb import answer_statistics_question
from app.ai.validator import ensure_disclaimer, reject_if_user_refusal_topic_in_opinion, validate_answer
from app.config import settings


def _ai_interpretation_label(*, llm_used: bool, polished: bool = False) -> str:
    if llm_used:
        model = settings.openai_model or "GPT"
        return f"{model} (polish)" if polished else model
    return "CH2 템플릿"


def _maybe_polish(
    answer: str,
    *,
    message: str,
    route: str,
    scope_label: str,
    narrative_result: NarrativeResult | None,
) -> tuple[str, bool]:
    if not narrative_result or not polish_enabled():
        return answer, False
    polished = polish_template_answer(
        template_answer=answer,
        user_message=message,
        route=route,
        scope_label=scope_label,
    )
    if polished and numbers_preserved(answer, polished):
        return polished, True
    return answer, False


def _web_evidence(hits: list[WebHit]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for h in hits[:5]:
        items.append(
            EvidenceItem(
                type="web",
                label=h.title[:120],
                url=h.url,
                value=h.snippet[:200] if h.snippet else None,
                confidence="medium",
            )
        )
    return items


def _refusal_answer(context: AiContext, message: str) -> AiChatResponse:
    lines = [
        "CH2는 **시장통계 분석 시스템**입니다.",
        "감정평가액·적정가격·투자 적합성을 판단하지 않습니다.",
    ]
    primary = (context.facts or {}).get("primary") or {}
    pred = primary.get("prediction") or context.facts.get("prediction")
    if pred is not None:
        lines.append(f"현재 화면의 회귀 예측값(API): {pred}")
        lines.append(
            "위 값은 동일 scope 거래를 바탕으로 한 **통계적 예측**이며, "
            "개별 물건의 적정가격을 의미하지 않습니다."
        )
    lines.append("가격·투자 판단은 현장 조사와 전문가 판단이 필요합니다.")

    evidence = [
        EvidenceItem(
            type="refusal_policy",
            label="CH2 서비스 정책",
            confidence="high",
        ),
    ]
    if pred is not None:
        evidence.append(
            EvidenceItem(
                type="ch2_regression",
                label="CH2 예측값 (참고)",
                value=str(pred),
                confidence="high",
            )
        )
    return AiChatResponse(
        session_id="",
        route="refusal",
        answer="\n\n".join(lines),
        evidence=evidence,
        bundle_id=resolve_bundle_id(context.panel),
        suggested_followups=suggested_questions(context.panel, context.purpose, app=context.app),
        disclaimer=REFUSAL_DISCLAIMER,
        llm_used=False,
    )


def _effective_explain(context: AiContext) -> AnalysisExplain | None:
    if context.explain:
        return context.explain
    facts = context.facts or {}
    if context.app == "built" and facts:
        if facts.get("y_hat") is not None:
            return built_prediction_explain(
                scope_label=str(
                    facts.get("scope_label") or context.scope.region_label or "선택 scope"
                ),
            )
        return built_regression_explain_from_facts(facts)
    if context.app == "land" and facts:
        if facts.get("series") or facts.get("rows"):
            return land_trend_explain(
                scope_label=context.scope.region_label or "선택 scope",
                is_long=bool(facts.get("series")),
            )
        return land_matrix_regression_explain_from_facts(
            scope_label=context.scope.region_label or "선택 scope",
            zone_type=facts.get("zone_type") if isinstance(facts.get("zone_type"), str) else None,
            land_category=facts.get("land_category") if isinstance(facts.get("land_category"), str) else None,
            model_type=facts.get("model_type") if isinstance(facts.get("model_type"), str) else None,
        )
    if context.app == "collective" and facts:
        asset = context.scope.asset_type or "apartment"
        cohort = bool(facts.get("building_keys") or facts.get("cohort_buildings"))
        explain_payload = facts.get("explain")
        return collective_regression_explain_from_context(
            asset_type=str(asset),
            cohort=cohort,
            explain_payload=explain_payload if isinstance(explain_payload, dict) else None,
        )
    return None


def _has_facts_narrative(bundle: AiDiagnosticPack) -> bool:
    bid = bundle.bundle_id
    d = bundle.diagnostics
    if bid == "regression_diagnostic":
        return d.get("n") is not None
    if bid == "trend_diagnostic":
        return bool(d.get("points"))
    if bid == "prediction_explain":
        return d.get("y_hat") is not None
    return bool(d.get("n") or d.get("points") or d.get("y_hat"))


def _regression_narrative(
    context: AiContext,
    bundle: AiDiagnosticPack,
    message: str,
) -> NarrativeResult:
    scope = (
        context.scope.region_label
        or bundle.diagnostics.get("scope_label")
        or "선택 scope"
    )
    bid = bundle.bundle_id
    if bid == "trend_diagnostic":
        return build_trend_narrative(
            diagnostics=bundle.diagnostics,
            scope_label=str(scope),
            message=message,
        )
    if bid == "prediction_explain":
        return build_prediction_narrative(
            diagnostics=bundle.diagnostics,
            scope_label=str(scope),
            message=message,
        )
    corrs = context.facts.get("correlations") if context.facts else None
    if not isinstance(corrs, list):
        corrs = bundle.diagnostics.get("correlations")
    return interpret_built_regression(
        diagnostics=bundle.diagnostics,
        scope_label=str(scope),
        message=message,
        correlations=corrs if isinstance(corrs, list) else None,
    )


def _explain_answer(
    context: AiContext, message: str, bundle: AiDiagnosticPack
) -> tuple[str, list[str] | None, NarrativeResult | None]:
    ex = _effective_explain(context)
    if ex:
        for preset in ex.presets:
            qn = preset.question.replace("?", "").replace("？", "").strip()
            if qn and qn in message.replace("?", "").replace("？", ""):
                if preset.answer.strip():
                    return preset.answer, None, None
                if _has_facts_narrative(bundle):
                    nr = _regression_narrative(context, bundle, message)
                    return nr.answer, nr.followups, nr
        if "해석" in message or "어떻게" in message:
            if _has_facts_narrative(bundle):
                nr = _regression_narrative(context, bundle, message)
                return nr.answer, nr.followups, nr
        parts = [f"**{ex.title}**", ex.summary]
        if ex.formula:
            parts.append(f"공식: {ex.formula}")
        if ex.interpretation:
            parts.extend(ex.interpretation[:4])
        if ex.limitations:
            parts.append("한계: " + " ".join(ex.limitations[:3]))
        return "\n\n".join(parts), None, None
    if _has_facts_narrative(bundle):
        nr = _regression_narrative(context, bundle, message)
        return nr.answer, nr.followups, nr
    return (
        "현재 화면에 Explain 메타가 없습니다. CH2 Facts(회귀·통계)를 먼저 실행해 주세요.",
        None,
        None,
    )


def _ch2_template_answer(
    message: str, bundle: AiDiagnosticPack, context: AiContext
) -> tuple[str, list[str] | None, NarrativeResult | None]:
    if _has_facts_narrative(bundle):
        nr = _regression_narrative(context, bundle, message)
        return nr.answer, nr.followups, nr
    lines = [f"**{context.scope.region_label or '선택 지역'}** · `{bundle.bundle_id}`"]
    if bundle.limitations:
        lines.append("⚠ " + bundle.limitations[0])
    lines.extend(f"• {s}" for s in bundle.summary_lines[:10])
    return "\n\n".join(lines), None, None


def _opinion_template(message: str, bundle: AiDiagnosticPack) -> str:
    n = bundle.diagnostics.get("n")
    base = (
        "방법론 관점에서, log(금액) semi-log 모형은 "
        "양의 왜도가 있는 거래금액 분포에서 잔차를 안정화하는 **선택지 중 하나**일 수 있습니다. "
        "선형(총액) OLS와 비교할 때 trade-off는 "
        "(1) 해석의 직관성 (2) 잔차 분산 (3) 표본 크기에 따라 달라집니다."
    )
    if n is not None and int(n) < 50:
        base += f"\n\n현재 scope 표본 n={n}으로, 복잡한 모형은 불안정할 수 있어 단순 spec을 우선 검토할 수 있습니다."
    if "로그" in message:
        return base
    return base + "\n\n구체 모형은 연구 목적·변수 스케일·잔차 진단을 함께 보아야 합니다."


def _evidence_for_route(
    route: str,
    bundle: AiDiagnosticPack,
    *,
    llm: bool = False,
) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    if route in ("ch2", "explain", "opinion", "refusal"):
        items.append(
            EvidenceItem(
                type="ch2_regression",
                label="회귀분석 결과",
                ref=bundle.bundle_id,
                confidence="high",
            )
        )
        n = bundle.diagnostics.get("n")
        if n is not None:
            items.append(
                EvidenceItem(
                    type="ch2_sample",
                    label="표본수",
                    value=f"{n}건",
                    confidence="high",
                )
            )
        if bundle.diagnostics.get("vif"):
            items.append(
                EvidenceItem(
                    type="ch2_vif",
                    label="다중공선성(VIF)",
                    confidence="high",
                )
            )
        if bundle.diagnostics.get("correlation_count") or bundle.diagnostics.get("correlations"):
            items.append(
                EvidenceItem(
                    type="ch2_correlation",
                    label="변수간 상관관계",
                    confidence="high",
                )
            )
    if route == "explain" and bundle.diagnostics.get("spec_id"):
        items.append(
            EvidenceItem(
                type="ch2_explain",
                label="CH2 Explain layer",
                ref=str(bundle.diagnostics.get("spec_id")),
                confidence="high",
            )
        )
    if route == "statistics":
        items.append(
            EvidenceItem(
                type="stats_knowledge",
                label="통계 일반 지식",
                confidence="medium",
            )
        )
    if route == "opinion":
        items.append(
            EvidenceItem(
                type="ai_opinion",
                label="방법론 분석 (AI)",
                confidence="low" if llm else "medium",
            )
        )
    if route == "web":
        items.append(
            EvidenceItem(
                type="web",
                label="웹 검색",
                confidence="medium",
            )
        )
    return items


def handle_chat(req: AiChatRequest) -> AiChatResponse:
    session = get_or_create(req.session_id)
    ctx = req.context

    route = classify_route(req.message)
    route = reject_if_user_refusal_topic_in_opinion(req.message, route)

    if route == "refusal":
        resp = _refusal_answer(ctx, req.message)
        resp.session_id = session.session_id
        session.add_turn(SessionTurn(role="user", message=req.message, route=route))
        session.add_turn(SessionTurn(role="assistant", message=resp.answer[:500], route=route))
        return resp

    bundle = build_bundle(ctx)
    session.push_context(
        {
            "panel": ctx.panel,
            "purpose": ctx.purpose,
            "scope": ctx.scope.model_dump(),
            "bundle_id": bundle.bundle_id,
            "app": ctx.app,
            "n": bundle.diagnostics.get("n"),
            "adj_r_squared": bundle.diagnostics.get("adj_r_squared"),
            "scope_label": ctx.scope.region_label or bundle.diagnostics.get("scope_label"),
        }
    )

    scope_label = str(ctx.scope.region_label or bundle.diagnostics.get("scope_label") or "선택 scope")
    if is_comparison_question(req.message):
        comp = narrative_scope_comparison(session, current_label=scope_label)
        if comp:
            resp = AiChatResponse(
                session_id=session.session_id,
                route="ch2",
                answer=validate_answer(comp, "ch2"),
                evidence=_evidence_for_route("ch2", bundle),
                bundle_id="cluster_compare",
                suggested_followups=[
                    "두 scope 표본수 차이는?",
                    "설명력(Adj R²) 차이는?",
                    "왜 연식 계수가 음수인가요?",
                ],
                disclaimer=SHORT_DISCLAIMER,
                llm_used=False,
                trust_level="medium",
                trust_sources=["CH2 세션 scope 기록", "회귀분석 요약"],
                ai_interpretation=_ai_interpretation_label(llm_used=False),
            )
            session.add_turn(
                SessionTurn(role="user", message=req.message, route="ch2", bundle_id="cluster_compare")
            )
            session.add_turn(SessionTurn(role="assistant", message=comp[:500], route="ch2"))
            return resp

    bundle_id = bundle.bundle_id
    llm_used = False
    polished = False
    disclaimer: str | None = None
    narrative_followups: list[str] | None = None
    narrative_result: NarrativeResult | None = None
    scope_label = str(ctx.scope.region_label or bundle.diagnostics.get("scope_label") or "선택 scope")

    if route == "web":
        search_q = req.message.strip()
        if ctx.scope.region_label:
            search_q = f"{ctx.scope.region_label} {search_q}"
        hits = web_search(search_q, max_results=5)
        llm_ans = synthesize_web_answer(message=req.message, hits=hits, scope_label=scope_label)
        if llm_ans:
            answer = llm_ans
            llm_used = True
        else:
            answer = web_template_answer(req.message, hits, scope_label=scope_label)
        disclaimer = WEB_DISCLAIMER
        evidence = _web_evidence(hits)
        if hits and ctx.scope.region_label:
            evidence.append(
                EvidenceItem(
                    type="ch2_regression",
                    label="CH2 scope (참고)",
                    value=scope_label,
                    confidence="high",
                )
            )
        answer = validate_answer(answer, route)
        disclaimer = ensure_disclaimer(route, disclaimer)
        followups = [
            "CH2 화면 통계와 외부 자료 차이는?",
            "표본수가 적으면 어떤 문제가 생기나요?",
            "신뢰구간이 넓은 이유는?",
        ]
        resp = AiChatResponse(
            session_id=session.session_id,
            route=route,  # type: ignore[arg-type]
            answer=answer,
            evidence=evidence,
            bundle_id=bundle_id,
            suggested_followups=followups,
            disclaimer=disclaimer,
            llm_used=llm_used,
            trust_level="low",
            trust_sources=[f"웹 검색 ({h.source})" for h in hits[:3]] or ["웹 검색"],
            ai_interpretation=_ai_interpretation_label(llm_used=llm_used),
        )
        session.add_turn(
            SessionTurn(
                role="user",
                message=req.message,
                route=route,
                bundle_id=bundle_id,
                scope_label=ctx.scope.region_label,
            )
        )
        session.add_turn(SessionTurn(role="assistant", message=answer[:500], route=route, bundle_id=bundle_id))
        return resp
    elif route == "statistics":
        answer = answer_statistics_question(req.message) or (
            "해당 통계 개념에 대한 CH2 내장 설명이 아직 없습니다. "
            "p-value, VIF, OLS, Adj R², 신뢰구간 등 키워드로 다시 질문해 보세요."
        )
        disclaimer = DEFAULT_DISCLAIMER
    elif route == "explain":
        answer, narrative_followups, narrative_result = _explain_answer(ctx, req.message, bundle)
        answer, polished = _maybe_polish(
            answer,
            message=req.message,
            route=route,
            scope_label=scope_label,
            narrative_result=narrative_result,
        )
        if polished:
            llm_used = True
        disclaimer = SHORT_DISCLAIMER if _has_facts_narrative(bundle) else DEFAULT_DISCLAIMER
    elif route == "opinion":
        answer = _opinion_template(req.message, bundle)
        if llm_configured():
            llm_ans = chat_completion(
                user_message=req.message,
                route=route,
                bundle=bundle,
                session_summary=session_summary(session),
            )
            if llm_ans:
                answer = llm_ans
                llm_used = True
        disclaimer = OPINION_DISCLAIMER
    else:
        answer, narrative_followups, narrative_result = _ch2_template_answer(req.message, bundle, ctx)
        answer, polished = _maybe_polish(
            answer,
            message=req.message,
            route=route,
            scope_label=scope_label,
            narrative_result=narrative_result,
        )
        if polished:
            llm_used = True
        elif ctx.app != "built" and llm_configured() and not narrative_result:
            llm_ans = chat_completion(
                user_message=req.message,
                route="ch2",
                bundle=bundle,
                session_summary=session_summary(session),
            )
            if llm_ans:
                answer = llm_ans
                llm_used = True
        disclaimer = SHORT_DISCLAIMER if narrative_result or _has_facts_narrative(bundle) else DEFAULT_DISCLAIMER

    answer = validate_answer(answer, route)
    disclaimer = ensure_disclaimer(route, disclaimer)
    evidence = _evidence_for_route(route, bundle, llm=llm_used)
    followups = narrative_followups or suggested_questions(ctx.panel, ctx.purpose, app=ctx.app)
    trust_level = narrative_result.trust_level if narrative_result else None
    trust_sources = narrative_result.trust_sources if narrative_result else []

    resp = AiChatResponse(
        session_id=session.session_id,
        route=route,  # type: ignore[arg-type]
        answer=answer,
        evidence=evidence,
        bundle_id=bundle_id,
        suggested_followups=followups,
        disclaimer=disclaimer,
        llm_used=llm_used,
        trust_level=trust_level,
        trust_sources=trust_sources,
        ai_interpretation=_ai_interpretation_label(llm_used=llm_used, polished=polished),
    )
    session.add_turn(
        SessionTurn(
            role="user",
            message=req.message,
            route=route,
            bundle_id=bundle_id,
            scope_label=ctx.scope.region_label,
        )
    )
    session.add_turn(SessionTurn(role="assistant", message=answer[:500], route=route, bundle_id=bundle_id))
    return resp


def handle_explain(req: AiExplainRequest) -> AiChatResponse:
    ctx = req.context
    bundle = build_from_explain_or_bundle(ctx)
    msg = req.message or "이 화면을 설명해 주세요."
    answer, narrative_followups, narrative_result = _explain_answer(ctx, msg, bundle)
    scope_label = str(ctx.scope.region_label or bundle.diagnostics.get("scope_label") or "선택 scope")
    polished = False
    llm_used = False
    answer, polished = _maybe_polish(
        answer,
        message=msg,
        route="explain",
        scope_label=scope_label,
        narrative_result=narrative_result,
    )
    if polished:
        llm_used = True
    return AiChatResponse(
        session_id="",
        route="explain",
        answer=answer,
        evidence=_evidence_for_route("explain", bundle),
        bundle_id=bundle.bundle_id,
        suggested_followups=narrative_followups
        or suggested_questions(ctx.panel, ctx.purpose, app=ctx.app),
        disclaimer=SHORT_DISCLAIMER if narrative_result or _has_facts_narrative(bundle) else DEFAULT_DISCLAIMER,
        llm_used=llm_used,
        trust_level=narrative_result.trust_level if narrative_result else None,
        trust_sources=narrative_result.trust_sources if narrative_result else [],
        ai_interpretation=_ai_interpretation_label(llm_used=llm_used, polished=polished),
    )


def build_from_explain_or_bundle(ctx: AiContext) -> AiDiagnosticPack:
    return build_bundle(ctx)
