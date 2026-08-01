"""FieldNote AI 프록시 — OpenAI 키 서버 보관 + device quota."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.platform.db import get_platform_db

router = APIRouter(prefix="/fieldnote/ai", tags=["fieldnote-ai"])
_log = logging.getLogger(__name__)

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MONTHLY_QUOTA = 50


class AiProxyRequest(BaseModel):
    model: str | None = None
    messages: list[dict]
    temperature: float = 0.15
    max_tokens: int = 900
    response_format: dict | None = None


def _usage_month() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


def _check_and_increment_quota(db: Session, device_id: str, *, premium: bool = False) -> None:
    if premium:
        return
    month = _usage_month()
    row = db.execute(
        text(
            """
            INSERT INTO device_ai_usage (device_id, usage_month, call_count)
            VALUES (:did, :mon, 1)
            ON CONFLICT (device_id, usage_month) DO UPDATE SET
                call_count = device_ai_usage.call_count + 1,
                updated_at = now()
            RETURNING call_count
            """
        ),
        {"did": device_id, "mon": month},
    ).mappings().first()
    db.commit()
    count = int(row["call_count"]) if row else 0
    quota = settings.fieldnote_ai_monthly_quota
    if count > quota:
        raise HTTPException(
            429,
            detail={
                "code": "quota_exceeded",
                "message": "이번 달 AI 분석 한도를 모두 사용했습니다. 구독 시 한도가 확대됩니다.",
            },
        )


@router.post("/vision")
async def ai_vision(
    body: AiProxyRequest,
    db: Session = Depends(get_platform_db),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
):
    return await _proxy_openai(body, x_device_id, db)


@router.post("/sheet")
async def ai_sheet(
    body: AiProxyRequest,
    db: Session = Depends(get_platform_db),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
):
    return await _proxy_openai(body, x_device_id, db, max_tokens_default=3500)


async def _proxy_openai(
    body: AiProxyRequest,
    device_id: str | None,
    db: Session,
    max_tokens_default: int = 900,
):
    if not settings.openai_api_key:
        raise HTTPException(503, "OpenAI API 미설정")
    did = (device_id or "").strip()
    if not did:
        raise HTTPException(401, detail={"code": "device_required", "message": "X-Device-Id 헤더가 필요합니다."})
    _check_and_increment_quota(db, did)
    model = body.model or settings.openai_model
    payload = {
        "model": model,
        "temperature": body.temperature,
        "max_tokens": body.max_tokens or max_tokens_default,
        "messages": body.messages,
    }
    if body.response_format:
        payload["response_format"] = body.response_format
    async with httpx.AsyncClient(timeout=120.0) as client:
        res = await client.post(
            OPENAI_CHAT_URL,
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    try:
        data = res.json()
    except Exception:
        raise HTTPException(502, "OpenAI 응답 파싱 실패")
    if res.status_code >= 400:
        msg = data.get("error", {}).get("message", res.text)
        raise HTTPException(res.status_code, msg)
    return data
