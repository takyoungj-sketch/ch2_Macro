"""승인한 서버 계획만 비동기로 실행. 단일 로컬 프로세스 시험용."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import logging
import secrets
import time
from fastapi import HTTPException
from app.ai3.store import LOCK, MAX_EXECUTIONS, State
from app.ai3.schemas import ExecutionOut
from app.ai3.tools import run_tool
from app.ai3.validation import extract_facts, external_view

_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ai3")
_LOG = logging.getLogger(__name__)


def start(state: State, plan_id: str) -> ExecutionOut:
    from app.ai3.store import STATES
    with LOCK:
        existing = next((e for e in state.executions.values() if e.plan_id == plan_id), None)
        if existing:
            return existing.model_copy(deep=True)
        plan = state.plans.get(plan_id)
        if plan is None or plan.expires_at < time.time():
            raise HTTPException(409, "실행 계획이 없거나 만료되었습니다. 다시 계획해 주세요.")
        if state.current_plan != plan_id:
            raise HTTPException(409, "더 새로운 계획이 있습니다. 현재 조건을 다시 확인해 주세요.")
        active = sum(e.status in ("running", "cancel_requested") for s in STATES.values() for e in s.executions.values())
        if active >= 2:
            raise HTTPException(429, "AI3 동시 실행 상한입니다. 진행 중인 분석이 끝난 뒤 실행하세요.")
        if len(state.executions) >= MAX_EXECUTIONS:
            raise HTTPException(429, "세션 실행 상한입니다. 새 대화를 시작해 주세요.")
        out = ExecutionOut(id=secrets.token_urlsafe(24), session_id=state.id, plan_id=plan_id,
                           tool_id=plan.tool_id, status="running", created_at=time.time(), applied_arguments=plan.arguments)
        state.executions[out.id] = out
        _POOL.submit(_run, state, out.id, plan.tool_id, dict(plan.arguments))
        return out.model_copy(deep=True)


def _run(state: State, eid: str, tool_id: str, arguments: dict) -> None:
    result, limitations, error = None, [], None
    try:
        with LOCK:
            if state.executions[eid].status == "cancel_requested":
                state.executions[eid].status = "cancelled"
                state.executions[eid].finished_at = time.time()
                return
        result, limitations = run_tool(tool_id, arguments)
    except HTTPException as exc:
        error = f"분석 거절 ({exc.status_code}): {exc.detail}"
    except ValueError as exc:
        error = f"입력 또는 엔진 게이트: {str(exc)[:500]}"
    except Exception:
        _LOG.exception("AI3 tool failed: %s", tool_id)
        error = "DB·분석 서비스에서 오류가 발생했습니다. 서버 로그와 연결 상태를 확인하세요."
    with LOCK:
        out = state.executions[eid]
        out.finished_at = time.time()
        state.touched = time.time()
        if out.status == "cancel_requested":
            out.status = "cancelled"
            out.limitations = ["취소 요청 후 작업 종료를 기다렸습니다. 결과는 성공 이력에 넣지 않았습니다."]
        elif error:
            out.status, out.error = "failed", error
        else:
            safe_result = external_view(result, state.target_refs)
            out.status, out.result, out.limitations = "succeeded", safe_result, limitations
            out.facts = extract_facts(safe_result, eid)
            state.history.append(eid)
            state.history = state.history[-12:]


def get(state: State, eid: str) -> ExecutionOut:
    with LOCK:
        value = state.executions.get(eid)
        if value is None:
            raise HTTPException(404, "AI3 실행이 없거나 접근할 수 없습니다.")
        return value.model_copy(deep=True)


def cancel(state: State, eid: str) -> ExecutionOut:
    with LOCK:
        value = state.executions.get(eid)
        if value is None:
            raise HTTPException(404, "AI3 실행이 없거나 접근할 수 없습니다.")
        if value.status == "running":
            value.status = "cancel_requested"
            value.limitations = ["취소 요청됨. 실행 중인 DB 작업은 제한시간까지 종료를 기다릴 수 있습니다."]
        return value.model_copy(deep=True)
