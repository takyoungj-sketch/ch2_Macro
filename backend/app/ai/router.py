"""CH2 AI API — /api/ai/*"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, Request

from app.ai.bundles.registry import BUNDLE_REGISTRY, suggested_questions
from app.ai.constitution import CONSTITUTION_VERSION
from app.ai.llm import llm_configured, polish_enabled, _model
from app.ai.web_search import web_search_configured
from app.ai.orchestrator import handle_chat, handle_explain
from app.ai.rate_limit import check_ai_rate_limit
from app.ai.schemas import (
    AiApp,
    AiChatRequest,
    AiChatResponse,
    AiExplainRequest,
    AiHealthResponse,
    AiPurpose,
)

router = APIRouter(prefix="/ai", tags=["CH2 AI Assistant"])


@router.get("/health", response_model=AiHealthResponse)
def ai_health():
    return AiHealthResponse(
        llm_configured=llm_configured(),
        polish_enabled=polish_enabled(),
        web_search_configured=web_search_configured(),
        model=_model() if llm_configured() else None,
        constitution_version=CONSTITUTION_VERSION,
    )


@router.post("/chat", response_model=AiChatResponse)
def ai_chat(body: AiChatRequest, request: Request):
    """세션 기반 AI 대화 — Screen-bound + Reasoning Bundle."""
    check_ai_rate_limit(request)
    return handle_chat(body)


@router.post("/explain", response_model=AiChatResponse)
def ai_explain(body: AiExplainRequest, request: Request):
    """Explain layer만 자연어화 (LLM 없이 presets 우선)."""
    check_ai_rate_limit(request)
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
