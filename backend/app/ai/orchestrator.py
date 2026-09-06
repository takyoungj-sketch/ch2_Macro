"""AI Chat orchestrator — Router + Bundle + 템플릿/LLM."""

from __future__ import annotations

from typing import Any

from app.ai.bundles import build_bundle, resolve_bundle_id, suggested_questions
from app.ai.bundles.comparison import is_scope_comparison_question, narrative_scope_comparison
from app.ai.casual_dialogue import (
    casual_dialogue_enabled,
    casual_followups,
    casual_off_topic_answer,
    casual_smalltalk_answer,
    casual_unrelated_prompt,
    is_casual_smalltalk,
    is_substantive_off_topic,
    should_auto_explain_screen,
)
from app.ai.open_mode import open_mode_enabled, soft_facts_snapshot
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
    OFFER_EXTERNAL_DISCLAIMER,
    OPINION_DISCLAIMER,
    REFUSAL_DISCLAIMER,
    SHORT_DISCLAIMER,
    WEB_DISCLAIMER,
    classify_route,
    is_external_confirm,
    is_refusal_message,
    offer_external_answer,
)
from app.ai.panel_capabilities import (
    get_panel_capability,
    is_out_of_scope_message,
    out_of_scope_answer,
)
from app.ai.llm import (
    chat_completion,
    casual_synthesis_addon,
    llm_configured,
    numbers_preserved,
    open_mode_chat_completion,
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
    AiHistoryRecordRequest,
    AiHistoryRecordResponse,
    AiScreenAction,
    AnalysisExplain,
    EvidenceItem,
)
from app.ai.sessions import AiSession, SessionTurn, get_or_create, session_summary
from app.ai.knowledge.caveats import format_caveats_for_prompt
from app.ai.knowledge.history import (
    format_history_compare,
    format_history_for_prompt,
    format_memo,
    maybe_record,
)
from app.ai.knowledge.planner import (
    actions_for_plan,
    format_plan_answer,
    is_history_compare_question,
    is_knowledge_source_question,
    is_memo_request,
    is_path_intent_question,
    plan_analysis,
)
from app.ai.knowledge.product import (
    format_howto_answer,
    format_knowledge_source_answer,
    is_howto_ui_question,
    product_knowledge_excerpt,
)
from app.ai.stats_kb import (
    answer_statistics_question,
    answer_statistics_with_context,
    is_pure_definition_question,
)
from app.ai.synthesis import try_grounded_synthesis
from app.ai.targeted_qa import (
    answer_conversion_method_question,
    is_generic_screen_question,
    try_targeted_answer,
)
from app.ai.validator import ensure_disclaimer, reject_if_user_refusal_topic_in_opinion, validate_answer
from app.config import settings
from app.ai.usage_log import AiQuotaExceeded, bind_usage_meta, month_snapshot, reset_usage_meta


def _public_quota(snap: dict[str, Any] | None = None) -> dict[str, Any]:
    s = snap or month_snapshot()
    return {
        "month": s["month"],
        "calls": s["calls"],
        "call_limit": s["call_limit"],
        "krw": s["krw"],
        "budget_krw": s["budget_krw"],
        "warn": s["warn"],
        "stopped": s["stopped"],
        "warning": s.get("warning"),
    }


def _is_targeted_answer(answer: str) -> bool:
    return answer.strip().startswith("### 답변")


def _record_successful_analysis(session: Any, ctx: AiContext, bundle: AiDiagnosticPack, message: str = "") -> None:
    maybe_record(
        session,
        ctx,
        bundle_id=bundle.bundle_id,
        diagnostics=bundle.diagnostics or {},
        message=message,
    )


def _planner_or_memo_response(
    *,
    session: Any,
    req: AiChatRequest,
    ctx: AiContext,
    bundle: AiDiagnosticPack,
) -> AiChatResponse | None:
    """경로 질문·분석 메모. 해당 없으면 None."""
    fired = bundle.diagnostics.get("caveats") or []
    caveats_text = format_caveats_for_prompt(fired) if fired else ""
    history_text = format_history_for_prompt(session.analysis_history)

    if is_memo_request(req.message):
        answer = format_memo(session.analysis_history)
        resp = AiChatResponse(
            session_id=session.session_id,
            route="ch2",
            answer=validate_answer(answer, "ch2"),
            evidence=[
                EvidenceItem(type="ch2_history", label="Analysis History", confidence="high"),
            ],
            bundle_id=bundle.bundle_id,
            suggested_followups=(
                ["아까와 비교해 주세요", "이 결과의 한계는?"]
                if session.analysis_history
                else ["집합에서 회귀를 실행하면 History가 생깁니다."]
            ),
            disclaimer=SHORT_DISCLAIMER,
            llm_used=False,
            trust_level="high" if session.analysis_history else "medium",
            trust_sources=["CH2 Analysis History"],
            ai_interpretation=_ai_interpretation_label(llm_used=False),
        )
        session.add_turn(SessionTurn(role="user", message=req.message, route="ch2", bundle_id=bundle.bundle_id))
        session.add_turn(SessionTurn(role="assistant", message=answer[:500], route="ch2", bundle_id=bundle.bundle_id))
        return resp

    if is_history_compare_question(req.message):
        answer = format_history_compare(session.analysis_history)
        resp = AiChatResponse(
            session_id=session.session_id,
            route="ch2",
            answer=validate_answer(answer, "ch2"),
            evidence=[
                EvidenceItem(type="ch2_history", label="Analysis History 비교", confidence="high"),
            ],
            bundle_id=bundle.bundle_id,
            suggested_followups=["지금까지 분석을 정리해 주세요", "이 결과의 한계는?"],
            disclaimer=SHORT_DISCLAIMER,
            llm_used=False,
            trust_level="high" if len(session.analysis_history) >= 2 else "medium",
            trust_sources=["CH2 Analysis History"],
            ai_interpretation=_ai_interpretation_label(llm_used=False),
        )
        session.add_turn(SessionTurn(role="user", message=req.message, route="ch2", bundle_id=bundle.bundle_id))
        session.add_turn(SessionTurn(role="assistant", message=answer[:500], route="ch2", bundle_id=bundle.bundle_id))
        return resp

    if is_howto_ui_question(req.message):
        return None
    if is_knowledge_source_question(req.message):
        answer = format_knowledge_source_answer(app=ctx.app)
        resp = AiChatResponse(
            session_id=session.session_id,
            route="ch2",
            answer=validate_answer(answer, "ch2"),
            evidence=[
                EvidenceItem(type="ch2_product", label="CH2 Product Knowledge", confidence="high"),
                EvidenceItem(type="ch2_playbook", label="CH2 Playbook 역할", confidence="medium"),
            ],
            bundle_id=bundle.bundle_id,
            suggested_followups=[
                "복합에서 상가와 단독은 어떻게 비교하나요?",
                "유형별 데이터는 어떻게 들어오나요?",
                "외부자료를 조사해 주세요",
            ],
            disclaimer=SHORT_DISCLAIMER,
            llm_used=False,
            trust_level="high",
            trust_sources=["CH2 Product Knowledge", "CH2 Playbook"],
            ai_interpretation=_ai_interpretation_label(llm_used=False),
        )
        session.add_turn(SessionTurn(role="user", message=req.message, route="ch2", bundle_id=bundle.bundle_id))
        session.add_turn(SessionTurn(role="assistant", message=answer[:500], route="ch2", bundle_id=bundle.bundle_id))
        return resp
    if not is_path_intent_question(req.message, ctx):
        return None

    plan = plan_analysis(req.message, ctx)
    template = format_plan_answer(plan, caveats_text=caveats_text)
    actions = [AiScreenAction.model_validate(a) for a in actions_for_plan(plan, ctx)]
    followups = [
        "지금 화면에서 바로 실행할 수 있나요?",
        "아까와 비교해 주세요",
        "지금까지 분석을 정리해 주세요.",
    ]
    syn_ans, syn_fu, _syn_nr, syn_used = try_grounded_synthesis(
        message=req.message,
        route="ch2",
        context=ctx,
        bundle=bundle,
        template_answer=template,
        template_followups=followups,
        session_summary=session_summary(session),
        planner_text=template,
        caveats_text=caveats_text,
        history_text=history_text,
    )
    answer = syn_ans if syn_used else template
    resp = AiChatResponse(
        session_id=session.session_id,
        route="ch2",
        answer=validate_answer(answer, "ch2"),
        evidence=[
            EvidenceItem(type="ch2_playbook", label="CH2 분석 경로 (Playbook)", confidence="medium"),
        ]
        + (
            [EvidenceItem(type="ch2_caveat", label="Caveat", confidence="medium")]
            if fired
            else []
        ),
        bundle_id=bundle.bundle_id,
        suggested_followups=syn_fu or followups,
        actions=actions,
        disclaimer=DEFAULT_DISCLAIMER,
        llm_used=bool(syn_used),
        trust_level="medium",
        trust_sources=["CH2 Playbook", "Active Context"],
        ai_interpretation=_ai_interpretation_label(llm_used=bool(syn_used), synthesized=bool(syn_used)),
    )
    session.add_turn(SessionTurn(role="user", message=req.message, route="ch2", bundle_id=bundle.bundle_id))
    session.add_turn(SessionTurn(role="assistant", message=answer[:500], route="ch2", bundle_id=bundle.bundle_id))
    return resp


def _casual_response(
    *,
    session,
    message: str,
    ctx: AiContext,
    scope_label: str,
    bundle_id: str | None = None,
    diagnostics: dict[str, Any] | None = None,
    off_topic: bool = False,
) -> AiChatResponse:
    if off_topic:
        ans = casual_off_topic_answer(
            message,
            panel=ctx.panel,
            app=ctx.app,
            scope_label=scope_label,
            diagnostics=diagnostics or {},
        )
        label = "CH2 scope boundary"
    else:
        ans = casual_smalltalk_answer(message, scope_label=scope_label)
        label = "CH2 casual dialogue (experiment)"

    resp = AiChatResponse(
        session_id=session.session_id,
        route="casual",
        answer=validate_answer(ans, "ch2"),
        evidence=[
            EvidenceItem(
                type="casual_policy",
                label=label,
                confidence="high",
            ),
        ],
        bundle_id=bundle_id,
        suggested_followups=casual_followups(ctx.panel, ctx.app),
        disclaimer=SHORT_DISCLAIMER,
        llm_used=False,
        trust_level="medium",
        trust_sources=["CH2 casual experiment"],
        ai_interpretation=_ai_interpretation_label(llm_used=False),
    )
    session.add_turn(SessionTurn(role="user", message=message, route="casual"))
    session.add_turn(SessionTurn(role="assistant", message=ans[:500], route="casual"))
    return resp


def _ai_interpretation_label(*, llm_used: bool, polished: bool = False, synthesized: bool = False) -> str:
    if llm_used:
        model = settings.openai_model or "GPT"
        if synthesized:
            return f"{model} (합성)"
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


def _related_followups(context: AiContext) -> list[str]:
    cap = get_panel_capability(context.panel)
    qs = [q for q in cap.on_screen_questions if str(q).strip()]
    if not qs:
        qs = suggested_questions(context.panel, context.purpose, app=context.app)
    return qs[:4]


def _refusal_answer(context: AiContext, message: str) -> AiChatResponse:
    followups = _related_followups(context)
    lines = [
        "### 안내",
        "",
        "이 질문은 **CH2가 답하지 않는 범위**입니다.",
        "",
        "CH2는 **시장통계 분석** 시스템입니다. "
        "감정평가액·적정가격·투자 적합성, 이 모형을 감정평가에 쓸 수 있는지는 판단하지 않습니다.",
        "화면에 있는 회귀·예측 숫자는 선택 지역 거래의 **통계 패턴**일 뿐, 감정·적정가를 대체하지 않습니다.",
        "",
        "가격·투자 판단은 현장 조사와 전문가 판단이 필요합니다.",
        "",
        "### 대신 이런 질문을 해 보세요",
        "",
    ]
    for q in followups:
        lines.append(f"- {q}")

    return AiChatResponse(
        session_id="",
        route="refusal",
        answer="\n".join(lines).strip(),
        evidence=[
            EvidenceItem(
                type="refusal_policy",
                label="CH2 서비스 정책",
                confidence="high",
            ),
        ],
        bundle_id=resolve_bundle_id(context.panel),
        suggested_followups=followups,
        disclaimer=REFUSAL_DISCLAIMER,
        llm_used=False,
    )


def _out_of_scope_chat(context: AiContext) -> AiChatResponse:
    followups = _related_followups(context)
    body = out_of_scope_answer(context.panel, context.app)
    answer = "\n".join(
        [
            "### 안내",
            "",
            "이 질문은 **현재 화면의 통계·분석과 관련이 없어** 답하지 않습니다.",
            "",
            body,
        ]
    )
    return AiChatResponse(
        session_id="",
        route="casual",
        answer=answer,
        evidence=[
            EvidenceItem(
                type="casual_policy",
                label="CH2 질문 범위",
                confidence="high",
            ),
        ],
        bundle_id=resolve_bundle_id(context.panel),
        suggested_followups=followups,
        disclaimer=SHORT_DISCLAIMER,
        llm_used=False,
    )


def _commit_limit_response(session: Any, req: AiChatRequest, resp: AiChatResponse) -> AiChatResponse:
    resp.session_id = session.session_id
    session.add_turn(SessionTurn(role="user", message=req.message, route=resp.route))
    session.add_turn(SessionTurn(role="assistant", message=resp.answer[:500], route=resp.route))
    return resp


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
    if bid == "recommend_diagnostic":
        return isinstance(d.get("stage1"), dict)
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
    if bid == "recommend_diagnostic" or context.panel == "RecommendationCard":
        from app.ai.built_recommend_narrative import interpret_built_recommend

        return interpret_built_recommend(
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
    targeted = try_targeted_answer(message, bundle.diagnostics)
    if targeted:
        return targeted, None, None

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
        if is_generic_screen_question(message):
            parts = [f"**{ex.title}**", ex.summary]
            if ex.formula:
                parts.append(f"공식: {ex.formula}")
            if ex.interpretation:
                parts.extend(ex.interpretation[:4])
            if ex.limitations:
                parts.append("한계: " + " ".join(ex.limitations[:3]))
            return "\n\n".join(parts), None, None
    if _has_facts_narrative(bundle) and should_auto_explain_screen(message):
        nr = _regression_narrative(context, bundle, message)
        return nr.answer, nr.followups, nr
    if not should_auto_explain_screen(message):
        scope_label = str(context.scope.region_label or bundle.diagnostics.get("scope_label") or "선택 scope")
        return casual_unrelated_prompt(scope_label=scope_label), casual_followups(context.panel, context.app), None
    if ex:
        parts = [f"**{ex.title}**", ex.summary]
        return "\n\n".join(parts), None, None
    return (
        "현재 화면에 Explain 메타가 없습니다. CH2 Facts(회귀·통계)를 먼저 실행해 주세요.",
        None,
        None,
    )


def _ch2_template_answer(
    message: str, bundle: AiDiagnosticPack, context: AiContext
) -> tuple[str, list[str] | None, NarrativeResult | None]:
    targeted = try_targeted_answer(message, bundle.diagnostics)
    if targeted:
        return targeted, None, None
    if is_howto_ui_question(message):
        return format_howto_answer(context.app, message), [
            "단지를 연 다음 추세 탭은 어디에 있나요?",
            "유형 격차를 보려면 어떻게 하나요?",
        ], None
    if _has_facts_narrative(bundle) and should_auto_explain_screen(message):
        nr = _regression_narrative(context, bundle, message)
        return nr.answer, nr.followups, nr
    if not should_auto_explain_screen(message):
        scope_label = str(context.scope.region_label or bundle.diagnostics.get("scope_label") or "선택 scope")
        return casual_unrelated_prompt(scope_label=scope_label), casual_followups(context.panel, context.app), None
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


def _pending_external_query(session: AiSession) -> str | None:
    turns = session.turns
    if len(turns) < 2:
        return None
    last = turns[-1]
    if last.role != "assistant" or last.route != "offer_external":
        return None
    for t in reversed(turns[:-1]):
        if t.role == "user":
            return t.message
    return None


def handle_chat(req: AiChatRequest) -> AiChatResponse:
    session = get_or_create(req.session_id)
    ctx = req.context

    # 전환율 채택 이유(D-040)는 Open Mode에서도 실험 확정문을 우선한다.
    early_bundle = build_bundle(ctx)
    locked = answer_conversion_method_question(req.message, early_bundle.diagnostics)
    if locked:
        session.add_turn(SessionTurn(role="user", message=req.message, route="opinion"))
        session.add_turn(SessionTurn(role="assistant", message=locked[:500], route="opinion"))
        return AiChatResponse(
            session_id=session.session_id,
            route="opinion",
            answer=locked,
            evidence=[
                EvidenceItem(
                    type="ai_opinion",
                    label="전환율 실험 종료 (D-040, mean_simple)",
                    confidence="high",
                )
            ],
            bundle_id=early_bundle.bundle_id,
            suggested_followups=suggested_questions(ctx.panel, ctx.purpose, app=ctx.app)[:4],
            disclaimer=SHORT_DISCLAIMER,
            llm_used=False,
            trust_level="high",
            trust_sources=["RENT_CONVERSION_EXPERIMENT"],
        )

    if is_refusal_message(req.message):
        return _commit_limit_response(session, req, _refusal_answer(ctx, req.message))
    if is_out_of_scope_message(req.message):
        return _commit_limit_response(session, req, _out_of_scope_chat(ctx))

    _record_successful_analysis(session, ctx, early_bundle, req.message)
    planner_resp = _planner_or_memo_response(
        session=session, req=req, ctx=ctx, bundle=early_bundle
    )
    if planner_resp:
        return planner_resp

    # ── Open Mode: 라우팅/템플릿 우회 → LLM 우선 ─────────────────────────
    if open_mode_enabled():
        bundle = early_bundle
        scope_label = str(
            ctx.scope.region_label or bundle.diagnostics.get("scope_label") or "선택 scope"
        )
        session.push_context(
            {
                "panel": ctx.panel,
                "purpose": ctx.purpose,
                "scope": ctx.scope.model_dump(),
                "bundle_id": bundle.bundle_id,
                "app": ctx.app,
                "n": bundle.diagnostics.get("n"),
                "adj_r_squared": bundle.diagnostics.get("adj_r_squared"),
                "scope_label": scope_label,
                "open_mode": True,
            }
        )
        facts = soft_facts_snapshot(bundle, scope_label=scope_label, context=ctx)
        meta_tok = bind_usage_meta(
            route="open",
            app=ctx.app,
            panel=ctx.panel,
            scope_label=scope_label,
        )
        quota_snap: dict[str, Any] | None = None
        try:
            llm_ans = open_mode_chat_completion(
                user_message=req.message,
                scope_label=scope_label,
                screen_facts=facts,
                session_summary=session_summary(session, max_turns=10),
                product_knowledge=product_knowledge_excerpt(
                    app=ctx.app, panel=ctx.panel or "", message=req.message
                ),
            )
        except AiQuotaExceeded as exc:
            llm_ans = None
            quota_snap = exc.snapshot
            answer = exc.user_message
            llm_used = False
        else:
            if llm_ans:
                answer = llm_ans
                llm_used = True
            else:
                answer = (
                    "### 답변\n\n"
                    "Open Mode인데 LLM 응답을 받지 못했습니다. "
                    "`OPENAI_API_KEY`와 네트워크를 확인한 뒤 다시 시도해 주세요.\n\n"
                    f"참고 — 현재 화면 soft facts: `{facts.get('stats')}`"
                )
                llm_used = False
        finally:
            reset_usage_meta(meta_tok)
        if quota_snap is None:
            quota_snap = month_snapshot()
        if llm_used and quota_snap.get("warning"):
            answer = f"> {quota_snap['warning']}\n\n" + answer
        resp = AiChatResponse(
            session_id=session.session_id,
            route="open",
            answer=answer,
            evidence=[
                EvidenceItem(
                    type="open_mode",
                    label="AI Open Mode (routing bypass)",
                    confidence="medium",
                ),
                EvidenceItem(
                    type="ch2_sample",
                    label="screen_facts (soft)",
                    value=scope_label,
                    confidence="high",
                ),
            ],
            bundle_id=bundle.bundle_id,
            suggested_followups=suggested_questions(ctx.panel, ctx.purpose, app=ctx.app)[:4],
            disclaimer="Open Mode (개발·검증): 라우팅/템플릿 우회. 화면 숫자는 soft cite.",
            llm_used=llm_used,
            trust_level="medium" if llm_used else "low",
            trust_sources=["OpenAI (open mode)", "CH2 screen_facts soft"],
            ai_interpretation=_ai_interpretation_label(llm_used=llm_used),
            quota=_public_quota(quota_snap),
        )
        session.add_turn(
            SessionTurn(
                role="user",
                message=req.message,
                route="open",
                bundle_id=bundle.bundle_id,
                scope_label=scope_label,
            )
        )
        session.add_turn(
            SessionTurn(role="assistant", message=answer[:500], route="open", bundle_id=bundle.bundle_id)
        )
        return resp

    route = classify_route(req.message)
    route = reject_if_user_refusal_topic_in_opinion(req.message, route)
    web_query = req.message.strip()
    pending = _pending_external_query(session)
    if req.external_research:
        route = "web"
    elif pending and is_external_confirm(req.message):
        route = "web"
        web_query = pending

    if route == "refusal":
        resp = _refusal_answer(ctx, req.message)
        resp.session_id = session.session_id
        session.add_turn(SessionTurn(role="user", message=req.message, route=route))
        session.add_turn(SessionTurn(role="assistant", message=resp.answer[:500], route=route))
        return resp

    scope_label = str(ctx.scope.region_label or "선택 scope")

    # 인사·감사 — 플래그와 무관하게 화면 회귀 내러티브 반복 방지
    if is_casual_smalltalk(req.message) and route not in ("web", "offer_external"):
        return _casual_response(
            session=session,
            message=req.message,
            ctx=ctx,
            scope_label=scope_label,
        )

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

    if (
        casual_dialogue_enabled()
        and is_substantive_off_topic(req.message)
        and route not in ("web", "offer_external")
    ):
        return _casual_response(
            session=session,
            message=req.message,
            ctx=ctx,
            scope_label=scope_label,
            bundle_id=bundle.bundle_id,
            diagnostics=bundle.diagnostics,
            off_topic=True,
        )

    if is_scope_comparison_question(req.message):
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
    synthesized = False
    disclaimer: str | None = None
    narrative_followups: list[str] | None = None
    narrative_result: NarrativeResult | None = None
    scope_label = str(ctx.scope.region_label or bundle.diagnostics.get("scope_label") or "선택 scope")

    if route == "offer_external":
        answer = offer_external_answer(req.message, scope_label=scope_label)
        evidence = [
            EvidenceItem(
                type="ch2_playbook",
                label="외부조사 제안 (D-062)",
                confidence="high",
            )
        ]
        resp = AiChatResponse(
            session_id=session.session_id,
            route="offer_external",
            answer=validate_answer(answer, "offer_external"),
            evidence=evidence,
            bundle_id=bundle.bundle_id,
            suggested_followups=[
                "외부자료를 조사해 주세요",
                "이 화면 통계만 이어서 보기",
            ],
            disclaimer=OFFER_EXTERNAL_DISCLAIMER,
            llm_used=False,
            trust_level="high",
            trust_sources=["CH2 제품 범위"],
            ai_interpretation=_ai_interpretation_label(llm_used=False),
        )
        session.add_turn(
            SessionTurn(
                role="user",
                message=req.message,
                route="offer_external",
                bundle_id=bundle.bundle_id,
                scope_label=ctx.scope.region_label,
            )
        )
        session.add_turn(
            SessionTurn(role="assistant", message=answer[:500], route="offer_external", bundle_id=bundle.bundle_id)
        )
        return resp

    if route == "web":
        search_q = web_query
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
        targeted = try_targeted_answer(req.message, bundle.diagnostics)
        if targeted:
            answer = targeted
        else:
            answer = (
                answer_statistics_question(req.message)
                or answer_statistics_with_context(req.message, bundle.diagnostics)
                or (
                    "해당 통계 개념에 대한 CH2 내장 설명이 아직 없습니다. "
                    "회귀 카드 지표 옆 **`?`** 를 확인하거나, "
                    "「이 표본에서 설명력이 제한적인 이유는?」처럼 해석형으로 질문해 보세요."
                )
            )
        if (
            not targeted
            and _has_facts_narrative(bundle)
            and llm_configured()
            and not is_pure_definition_question(req.message)
        ):
            syn_ans, syn_fu, syn_nr, syn_used = try_grounded_synthesis(
                message=req.message,
                route="statistics",
                context=ctx,
                bundle=bundle,
                template_answer=answer,
                template_followups=suggested_questions(ctx.panel, ctx.purpose, app=ctx.app),
                session_summary=session_summary(session),
            )
            if syn_used:
                answer = syn_ans
                narrative_followups = syn_fu
                narrative_result = syn_nr
                llm_used = True
                synthesized = True
        disclaimer = DEFAULT_DISCLAIMER
    elif route == "explain":
        answer, narrative_followups, narrative_result = _explain_answer(ctx, req.message, bundle)
        if not _is_targeted_answer(answer):
            syn_ans, syn_fu, syn_nr, syn_used = try_grounded_synthesis(
                message=req.message,
                route="explain",
                context=ctx,
                bundle=bundle,
                template_answer=answer,
                template_followups=narrative_followups,
                narrative_result=narrative_result,
                session_summary=session_summary(session),
            )
            if syn_used:
                answer = syn_ans
                narrative_followups = syn_fu
                narrative_result = syn_nr
                llm_used = True
                synthesized = True
            else:
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
        targeted = try_targeted_answer(req.message, bundle.diagnostics)
        if targeted:
            answer = targeted
        else:
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
        if not _is_targeted_answer(answer):
            syn_ans, syn_fu, syn_nr, syn_used = try_grounded_synthesis(
                message=req.message,
                route="ch2",
                context=ctx,
                bundle=bundle,
                template_answer=answer,
                template_followups=narrative_followups,
                narrative_result=narrative_result,
                session_summary=session_summary(session),
            )
            if syn_used:
                answer = syn_ans
                narrative_followups = syn_fu
                narrative_result = syn_nr
                llm_used = True
                synthesized = True
            else:
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
        ai_interpretation=_ai_interpretation_label(
            llm_used=llm_used, polished=polished, synthesized=synthesized
        ),
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
    synthesized = False
    syn_ans, syn_fu, syn_nr, syn_used = try_grounded_synthesis(
        message=msg,
        route="explain",
        context=ctx,
        bundle=bundle,
        template_answer=answer,
        template_followups=narrative_followups,
        narrative_result=narrative_result,
        session_summary="",
    )
    if syn_used:
        answer = syn_ans
        narrative_followups = syn_fu
        narrative_result = syn_nr
        llm_used = True
        synthesized = True
    else:
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
        ai_interpretation=_ai_interpretation_label(
            llm_used=llm_used, polished=polished, synthesized=synthesized
        ),
    )


def build_from_explain_or_bundle(ctx: AiContext) -> AiDiagnosticPack:
    return build_bundle(ctx)


def handle_history_record(req: AiHistoryRecordRequest) -> AiHistoryRecordResponse:
    """회귀 성공 등 — 채팅 없이 History 슬롯만 남긴다. 실패 Gate는 recorded=false."""
    session = get_or_create(req.session_id)
    ctx = req.context
    bundle = build_bundle(ctx)
    slot = maybe_record(
        session,
        ctx,
        bundle_id=bundle.bundle_id,
        diagnostics=bundle.diagnostics or {},
        message=req.message or "",
    )
    return AiHistoryRecordResponse(
        session_id=session.session_id,
        recorded=slot is not None,
        slot_id=slot.id if slot else None,
        history_len=len(session.analysis_history),
    )
