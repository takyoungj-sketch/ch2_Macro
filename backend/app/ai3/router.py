"""AI3 별도 시험 API. 기본 비활성·소유권 쿠키·동일 출처·요청 제한."""
from __future__ import annotations

from collections import deque
import hmac
import os
import secrets
import time
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from app.config import settings
from app.ai.llm import llm_configured
from app.ai3.catalog import public_catalog
from app.ai3.execution import start, get, cancel
from app.ai3.orchestrator import chat
from app.ai3.schemas import ChatIn, ChatOut, ExecuteIn, ExecutionOut
from app.ai3.store import LOCK, session

_COOKIE = "ch2_ai3_owner"
_BUCKETS: dict[str, deque] = {}


def access(request: Request, response: Response) -> str:
    if not settings.ai3_enabled:
        raise HTTPException(404, "AI3 시험이 비활성입니다. 로컬 서버에서 AI3_ENABLED=true를 설정해 주세요.")
    if int(os.environ.get("WEB_CONCURRENCY", "1")) != 1:
        raise HTTPException(503, "AI3 첫 시험은 단일 worker 전용입니다.")
    expected = settings.ai3_access_token.strip()
    peer = request.client.host if request.client else ""
    if expected:
        if not hmac.compare_digest(request.headers.get("x-ai3-token", ""), expected):
            raise HTTPException(401, "AI3 시험 접근 토큰이 필요합니다.")
    elif request.url.hostname not in ("127.0.0.1", "localhost", "::1", "testserver") or peer not in ("127.0.0.1", "::1", "testclient") or any(
        key in request.headers for key in ("forwarded", "x-forwarded-for", "x-real-ip")
    ):
        raise HTTPException(401, "로컬 직접 접근만 허용합니다. 프록시·외부 접근은 AI3_ACCESS_TOKEN을 설정해야 합니다.")
    origin = request.headers.get("origin")
    if origin:
        parsed = urlsplit(origin)
        # 같은 host의 별도 Vite 포트는 로컬 시험에서 허용한다.
        if parsed.hostname != request.url.hostname or parsed.scheme != request.url.scheme:
            raise HTTPException(403, "다른 출처에서 AI3를 호출할 수 없습니다.")
    owner = request.cookies.get(_COOKIE)
    if not owner or len(owner) != 43:
        owner = secrets.token_urlsafe(32)
        response.set_cookie(_COOKIE, owner, httponly=True, samesite="strict", secure=request.url.scheme == "https",
                            path="/api/ai3", max_age=settings.ai3_session_ttl_seconds)
    now = time.time()
    # 쿠키 교체로 요청 제한을 우회하지 못하도록 네트워크 접근 주체로 제한한다.
    key = peer
    with LOCK:
        for stale in [k for k, q in _BUCKETS.items() if not q or q[-1] < now - 60]:
            del _BUCKETS[stale]
        bucket = _BUCKETS.setdefault(key, deque())
        while bucket and bucket[0] < now - 60:
            bucket.popleft()
        # 상태 폴링을 포함한 시험 상한. LLM·동시 엔진 실행은 별도 상한이 있다.
        if len(bucket) >= 120:
            raise HTTPException(429, "AI3 분당 요청 상한입니다.")
        bucket.append(now)
    return owner


router = APIRouter(prefix="/ai3", tags=["AI3 trial"], include_in_schema=False)


@router.get("/health")
def health(owner: str = Depends(access)):
    return dict(enabled=True, llm_configured=llm_configured(), storage="single_worker_memory",
                model=settings.openai_model, monthly_call_limit=settings.ai3_monthly_call_limit,
                tools=public_catalog())


@router.post("/chat", response_model=ChatOut)
def post_chat(body: ChatIn, owner: str = Depends(access)):
    state = session(owner, body.session_id)
    try:
        return chat(state, body)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/executions", response_model=ExecutionOut)
def post_execution(body: ExecuteIn, owner: str = Depends(access)):
    return start(session(owner, body.session_id), body.plan_id)


@router.get("/executions/{eid}", response_model=ExecutionOut)
def get_execution(eid: str, session_id: str, owner: str = Depends(access)):
    return get(session(owner, session_id), eid)


@router.post("/executions/{eid}/cancel", response_model=ExecutionOut)
def cancel_execution(eid: str, body: ExecuteIn, owner: str = Depends(access)):
    return cancel(session(owner, body.session_id), eid)
