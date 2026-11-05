"""지식 답변·화면 해석·분석 계획을 하나의 세션에서 처리한다."""
from __future__ import annotations
import re
import json
from typing import Any
from pydantic import ValidationError
from app.ai.constitution import is_refusal_message
from app.ai.panel_capabilities import is_out_of_scope_message
from app.ai.llm import llm_configured
from app.ai.usage_log import AiQuotaExceeded
from app.ai3 import llm
from app.ai3.catalog import public_catalog, tools, validate_arguments
from app.ai3.knowledge import retrieve, offline_answer
from app.ai3.schemas import ChatIn, ChatOut, Evidence, Fact
from app.ai3.store import LOCK, State, save_plan
from app.ai3.validation import extract_facts, render_grounded, external_view


def _facts(state: State, request: ChatIn) -> tuple[list[Fact], list[str]]:
    output = extract_facts(request.context.metrics, "screen_snapshot")
    limits = ["화면 요약은 클라이언트 스냅샷이며 엔진 실행 이력과 구별합니다."] if output else []
    with LOCK:
        for eid in state.history[-3:]:
            execution = state.executions[eid]
            limits.extend(execution.limitations)
            view = dict(tool_id=execution.tool_id, result=execution.result,
                        applied_arguments=external_view(execution.applied_arguments, state.target_refs))
            for fact in extract_facts(view, eid, limit=100):
                fact.id = f"f{len(output)}"
                fact.label = f"{eid[:8]}.{fact.label}"
                output.append(fact)
    return output, list(dict.fromkeys(limits))


def _plan(state: State, tool_id: str, arguments: Any) -> ChatOut:
    if not isinstance(arguments, dict):
        raise ValueError("실행 조건은 항목별 값으로 입력해 주세요.")
    if len(json.dumps(arguments, ensure_ascii=False)) > 24000:
        raise ValueError("실행 조건이 너무 큽니다.")
    if tool_id in tools():
        state.draft_request = dict(tool_id=tool_id, arguments=arguments)
    normalized = validate_arguments(tool_id, arguments)
    if normalized.get("target_key") in state.target_refs:
        normalized["target_key"] = state.target_refs[normalized["target_key"]]
    plan = save_plan(state, tool_id, tools()[tool_id].label, normalized)
    state.draft_request = None
    return ChatOut(session_id=state.id, kind="plan", answer="아래 조건을 확인한 뒤 승인하고 실행해 주세요. 아직 분석을 실행하지 않았습니다.",
                   plan=plan, evidence=[Evidence(id="catalog", label=plan.label, source=tools()[tool_id].source)])


def chat(state: State, request: ChatIn) -> ChatOut:
    if not state.chat_lock.acquire(blocking=False):
        raise ValueError("이 대화의 이전 질문을 처리하고 있습니다.")
    try:
        result = _chat(state, request)
        with LOCK:
            state.turns.extend([dict(role="user", text=request.message[:2000]), dict(role="assistant", text=result.answer[:2000])])
            state.turns = state.turns[-20:]
            result.history_ids = list(state.history)
        return result
    finally:
        state.chat_lock.release()


def _chat(state: State, request: ChatIn) -> ChatOut:
    base = dict(session_id=state.id)
    if is_refusal_message(request.message):
        return ChatOut(**base, kind="refusal", answer="적정가격·투자·매수/매도·미래 가격 판단은 제공하지 않습니다. 통계 방법과 실제 분석 결과는 설명할 수 있습니다.",
                       evidence=[Evidence(id="policy", label="AI 헌법", source="docs/CH2_AI_CONSTITUTION.md")])
    if is_out_of_scope_message(request.message):
        return ChatOut(**base, kind="refusal", answer="CH2 Macro와 통계 분석에 관련된 질문을 도와드립니다. 제품 기능·통계 개념·분석 결과를 질문해 주세요.",
                       evidence=[Evidence(id="policy", label="AI 답변 범위", source="docs/CH2_AI_CONSTITUTION.md")])
    if request.tool_id:
        try:
            return _plan(state, request.tool_id, request.arguments)
        except (ValueError, ValidationError) as exc:
            return ChatOut(**base, kind="clarify", answer=f"실행 조건을 확인해 주세요: {exc}")
    facts, limits = _facts(state, request)
    knowledge, sources = retrieve(request.message, request.context.app)
    allow_plan = bool(re.search(r"분석해|분석 해|조회|계산해|실행|찾아|구해|예측해|비교해|검색", request.message))
    if state.draft_request and len(request.message) < 300 and not any(k in request.message for k in ("왜", "무엇", "뭐", "설명", "원리", "?")):
        allow_plan = True
    with LOCK:
        pending = state.plans.get(state.current_plan or "")
        turns = list(state.turns[-8:])
    payload = dict(question=request.message, context=request.context.model_dump(), knowledge=knowledge,
                   sources=[s.model_dump() for s in sources], facts=[f.model_dump() for f in facts],
                   limitations=limits, turns=turns, allow_plan=allow_plan,
                   incomplete_request=external_view(state.draft_request, state.target_refs),
                   pending_plan=external_view(pending.model_dump(), state.target_refs) if pending else None,
                   tools=public_catalog())
    try:
        drafted = llm.draft(payload)
    except (ValueError, AiQuotaExceeded) as exc:
        return ChatOut(**base, kind="unavailable", answer=getattr(exc, "user_message", str(exc)), facts=facts, limitations=limits)
    except Exception:
        drafted = None
    if drafted:
        evidence_ids = drafted.get("evidence_ids")
        if not isinstance(evidence_ids, list):
            evidence_ids = []
        allowed_ids = {s.id for s in sources}
        valid_evidence = all(isinstance(i, str) and i in allowed_ids for i in evidence_ids)
        prose = render_grounded(drafted["answer"], facts)
        if valid_evidence and prose:
            if drafted["kind"] == "plan":
                if allow_plan:
                    try:
                        args = drafted.get("arguments") or {}
                        material = request.message + " " + " ".join(f.value for f in facts)
                        for name in ("target_key", "sigungu_code", "beopjungri_code"):
                            if isinstance(args, dict) and args.get(name) and str(args[name]) not in material:
                                raise ValueError("지역 코드·대상키를 추정하지 않습니다. 먼저 이름으로 검색해 주세요.")
                        response = _plan(state, str(drafted.get("tool_id")), args)
                        response.llm_used = True
                        return response
                    except (ValueError, ValidationError) as exc:
                        return ChatOut(**base, kind="clarify", answer=str(exc), evidence=sources[:1], llm_used=True)
                return ChatOut(**base, kind="clarify", answer="새 분석 실행이 필요한 경우 분석 종류와 조건을 지정해 주세요.", evidence=sources[:1])
            evidence = [s for s in sources if s.id in evidence_ids] or sources[:1]
            evidence.extend(Evidence(id=f"run:{eid}", label="AI3 성공 분석 결과", source=eid) for eid in state.history[-3:])
            return ChatOut(**base, kind=drafted["kind"], answer=prose, evidence=evidence,
                           facts=facts, limitations=limits, llm_used=True)
    if facts:
        answer = "확인된 결과를 아래 근거 항목으로 표시합니다. 자연어 해석을 받지 못했으므로 새로운 결론은 덧붙이지 않습니다."
    else:
        answer = offline_answer(request.message, request.context.app)
    if allow_plan:
        answer += "\n분석을 실행하려면 아래 도구와 정확한 조건을 선택해 계획을 만들 수 있습니다."
    reason = "LLM 연결이 설정되지 않아 제품 지식과 통계 설명을 표시합니다." if not llm_configured() else "LLM 응답 실패 또는 근거 검증 실패로 확인된 지식·결과를 표시합니다."
    return ChatOut(**base, answer=answer, evidence=sources, facts=facts,
                   limitations=list(dict.fromkeys(limits + [reason])))
