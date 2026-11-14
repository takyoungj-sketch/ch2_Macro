"""CH2 AI API — /api/ai/*"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, Request, Response
import secrets
from app.ai.sessions import session_owner
from app.ai.feature_filter import ai_feature_scope, filter_ai_body, make_tag, stored_result_visible
from app.platform.jwt_util import COOKIE_NAME, decode_access_token

from app.ai.bundles.registry import BUNDLE_REGISTRY, suggested_questions
from app.ai.constitution import CONSTITUTION_VERSION
from app.ai.casual_dialogue import casual_dialogue_enabled
from app.ai.open_mode import open_mode_enabled
from app.ai.llm import llm_configured, polish_enabled, _model
from app.ai.web_search import web_search_configured
from app.ai.orchestrator import handle_chat, handle_explain, handle_history_record
from app.ai.rate_limit import check_ai_rate_limit
from app.ai.schemas import (
    AiApp,
    AiChatRequest,
    AiChatResponse,
    AiExplainRequest,
    AiHealthResponse,
    AiHistoryRecordRequest,
    AiHistoryRecordResponse,
    AiPurpose,
)

router = APIRouter(prefix="/ai", tags=["CH2 AI Assistant"])


def _owner(request: Request, response: Response) -> str:
    payload = decode_access_token(request.cookies.get(COOKIE_NAME, ""))
    if payload and payload.get("sub"):
        return f"user:{payload['sub']}"
    # Local development has no signed-in user. A server-issued HttpOnly browser
    # cookie isolates those sessions without changing product access rules.
    browser = request.cookies.get("ch2_ai_browser", "")
    if not browser or len(browser) != 43:
        browser = secrets.token_urlsafe(32)
        response.set_cookie("ch2_ai_browser", browser, httponly=True, samesite="lax",
                            secure=request.url.scheme == "https", path="/api/ai", max_age=86400)
    return f"browser:{browser}"


@router.get("/health", response_model=AiHealthResponse)
def ai_health():
    return AiHealthResponse(
        llm_configured=llm_configured(),
        polish_enabled=polish_enabled(),
        web_search_configured=web_search_configured(),
        model=_model() if llm_configured() else None,
        constitution_version=CONSTITUTION_VERSION,
        casual_dialogue_enabled=casual_dialogue_enabled(),
        open_mode_enabled=open_mode_enabled(),
    )


@router.post("/chat", response_model=AiChatResponse)
def ai_chat(body: AiChatRequest, request: Request, response: Response):
    """세션 기반 AI 대화 — Screen-bound + Reasoning Bundle."""
    check_ai_rate_limit(request)
    body = filter_ai_body(body, request)  # D-085 비공개 기능 값 걷어내기
    with ai_feature_scope(request, body.context):  # 세션 재생·제품 지식도 같은 기준
        return _run_with_allowance(body, request, response, handle_chat)


def _run_with_allowance(body, request, response, handler):
    from app.config import settings
    from app.ai import allowances as quota
    from fastapi import HTTPException
    if not settings.ai_subscription_quota_enabled:
        with session_owner(_owner(request, response)):
            return handler(body)
    user = quota.request_user(request)
    if user is None:
        raise HTTPException(401, "AI 이용량을 확인하려면 로그인해 주세요.")
    if user.role == "admin":
        with session_owner(f"user:{user.id}"):
            return handler(body)
    engine, grant = quota.grant_for_user(user)
    if grant is None:
        raise HTTPException(403, "Macro 구독이 필요합니다.")
    import json
    if len(json.dumps(body.model_dump(), ensure_ascii=False)) > 120_000:
        raise HTTPException(413, "AI 입력이 너무 큽니다. 분석 범위나 대화 입력을 줄여 주세요.")
    ticket = quota.reserve(engine, grant, "macro_question", 1,
        body.request_id or request.headers.get("Idempotency-Key", ""),
        quota.fingerprint(body.model_dump(exclude={"request_id"})))
    if ticket.replay is not None:
        # D-085: 재시도 재생도 같은 관문(표지 기반 허용 목록). 거절이면 없는 작업처럼 답한다.
        if not stored_result_visible(ticket.replay):
            raise HTTPException(404, "작업을 찾을 수 없습니다.")
        result = AiChatResponse.model_validate(ticket.replay)
        result.quota = {**quota.snapshot(engine, grant), "request_id": ticket.id}
        return result
    try:
        with quota.tracking(ticket), session_owner(f"user:{user.id}"):
            result = handler(body)
        # Deterministic refusals and failed model answers do not consume questions.
        success = result.llm_used and not result.error_code and result.route != "refusal"
        result.quota = {"request_id": ticket.id}
        stored = None
        if success:
            stored = result.model_dump(mode="json")
            # D-085: 이 결과가 쓴 비공개 기능. 결과 조회 때 현재 요청자 기준으로 거른다.
            stored["feature_tags"] = make_tag()  # 현재 요청 ∪ 이전 근거(답을 만든 뒤 시점)
        quota.finish(ticket, stored,
                     error=result.error_code or (None if success else "not_chargeable"))
        result.quota = {**quota.snapshot(engine, grant), "request_id": ticket.id}
        return result
    except BaseException:
        quota.finish(ticket, error="request_failed")
        raise


@router.get("/allowance")
def ai_allowance(request: Request):
    from app.config import settings
    from app.ai import allowances as quota
    if not settings.ai_subscription_quota_enabled:
        return {"mode": "legacy", "items": []}
    user = quota.request_user(request)
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(401, "로그인이 필요합니다.")
    if user.role == "admin":
        return {"mode": "staff", "items": []}
    engine, grant = quota.grant_for_user(user)
    return quota.snapshot(engine, grant) if grant else {"mode": "no_subscription", "items": []}


@router.get("/requests/{request_id}")
def ai_request_result(request_id: str, request: Request):
    from app.ai import allowances as quota
    from fastapi import HTTPException
    from sqlalchemy import select
    user = quota.request_user(request)
    if user is None:
        raise HTTPException(401, "로그인이 필요합니다.")
    from app.platform.db import get_platform_engine
    engine = get_platform_engine()
    with engine.connect() as c:
        row = c.execute(select(quota.jobs).where((quota.jobs.c.id == request_id) | (quota.jobs.c.key == request_id),
                        quota.jobs.c.user_id == user.id)).mappings().first()
        if not row:
            raise HTTPException(404, "작업을 찾을 수 없습니다.")
        payload = c.execute(select(quota.results.c.payload).where(quota.results.c.request_id == row["id"])).scalar()
    import json
    result = json.loads(payload) if payload else None
    if result is not None:
        # D-085: 저장된 결과도 재생 관문(표지 기반 허용 목록, 표지 없으면 비관리자 거절)을 거친다.
        with ai_feature_scope(request):
            visible = stored_result_visible(result)
        if not visible:
            result = None
        else:
            result.pop("feature_tags", None)
    return {"request_id": request_id, "status": row["status"], "result": result}


@router.post("/history", response_model=AiHistoryRecordResponse)
def ai_history_record(body: AiHistoryRecordRequest, request: Request, response: Response):
    """성공한 분석 Bundle을 Analysis History에 자동 기록 (채팅 없이)."""
    check_ai_rate_limit(request)
    body = filter_ai_body(body, request)  # D-085
    with ai_feature_scope(request, body.context), session_owner(_owner(request, response)):
        return handle_history_record(body)


@router.post("/explain", response_model=AiChatResponse)
def ai_explain(body: AiExplainRequest, request: Request, response: Response):
    """Explain layer만 자연어화 (LLM 없이 presets 우선)."""
    check_ai_rate_limit(request)
    body = filter_ai_body(body, request)  # D-085
    with ai_feature_scope(request, body.context):
        return _ai_explain(body, request, response)


def _ai_explain(body: AiExplainRequest, request: Request, response: Response):
    from app.config import settings
    if settings.ai_subscription_quota_enabled:
        return _run_with_allowance(AiChatRequest(message=body.message or "이 화면을 설명해 주세요.",
            context=body.context, request_id=body.request_id), request, response, lambda _: handle_explain(body))
    with session_owner(_owner(request, response)):
        return handle_explain(body)


@router.get("/suggested-questions")
def ai_suggested_questions(
    app: AiApp = Query("built"),
    panel: str = Query("RegressionCard"),
    purpose: AiPurpose = Query("statistics"),
):
    return {
        "app": app,
        "panel": panel,
        "purpose": purpose,
        "questions": suggested_questions(panel, purpose, app=app),
    }


@router.get("/bundles/{bundle_id}")
def ai_bundle_spec(bundle_id: str):
    spec = BUNDLE_REGISTRY.get(bundle_id)
    if not spec:
        return {"detail": "unknown bundle_id", "available": list(BUNDLE_REGISTRY.keys())}
    return {
        "bundle_id": spec.bundle_id,
        "description": spec.description,
        "panels": list(spec.panels),
    }
