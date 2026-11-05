"""단일 프로세스 로컬 시험용 상태. 기존 AI/AI2 저장소와 공유하지 않는다."""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from fastapi import HTTPException
from app.config import settings
from app.ai3.schemas import ExecutionOut, Plan

LOCK = threading.RLock()
MAX_SESSIONS = 100
MAX_EXECUTIONS = 50


@dataclass
class State:
    id: str
    owner: str
    touched: float = field(default_factory=time.time)
    turns: list[dict] = field(default_factory=list)
    plans: dict[str, Plan] = field(default_factory=dict)
    executions: dict[str, ExecutionOut] = field(default_factory=dict)
    current_plan: str | None = None
    history: list[str] = field(default_factory=list)
    target_refs: dict[str, str] = field(default_factory=dict)
    draft_request: dict | None = None
    chat_lock: threading.Lock = field(default_factory=threading.Lock)


STATES: dict[str, State] = {}


def session(owner: str, sid: str | None) -> State:
    with LOCK:
        now = time.time()
        for key, value in list(STATES.items()):
            active = any(e.status in ("running", "cancel_requested") for e in value.executions.values())
            if now - value.touched > settings.ai3_session_ttl_seconds and not active:
                del STATES[key]
        if sid:
            value = STATES.get(sid)
            if value is None or not secrets.compare_digest(value.owner, owner):
                raise HTTPException(404, "AI3 세션이 없거나 접근할 수 없습니다.")
            value.touched = now
            return value
        if len(STATES) >= MAX_SESSIONS:
            raise HTTPException(429, "AI3 시험 세션 상한입니다. 이전 세션 만료 후 다시 시도하세요.")
        value = State(id=secrets.token_urlsafe(24), owner=owner)
        STATES[value.id] = value
        return value


def save_plan(state: State, tool_id: str, label: str, arguments: dict) -> Plan:
    with LOCK:
        now = time.time()
        state.plans = {key: plan for key, plan in state.plans.items() if plan.expires_at > now}
        plan = Plan(id=secrets.token_urlsafe(24), tool_id=tool_id, label=label,
                    arguments=arguments, created_at=now, expires_at=now + 600)
        state.plans[plan.id] = plan
        if len(state.plans) > 20:
            state.plans.pop(next(iter(state.plans)))
        state.current_plan = plan.id
        return plan
