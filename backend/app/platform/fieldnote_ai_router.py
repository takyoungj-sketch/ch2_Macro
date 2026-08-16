"""FieldNote AI 프록시 — OpenAI 키 서버 보관 + device quota (short/long/sheet)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.platform.db import get_platform_db
from app.platform.deps import CurrentUser, get_optional_user
from app.platform.entitlements import list_entitlements

router = APIRouter(prefix="/fieldnote/ai", tags=["fieldnote-ai"])
_log = logging.getLogger(__name__)

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
_kind_columns_ready = False


def _uses_completion_tokens(model: str) -> bool:
    m = (model or "").strip().lower()
    return m.startswith("gpt-5") or m.startswith("o1") or m.startswith("o3") or m.startswith("o4")


class AiProxyRequest(BaseModel):
    model: str | None = None
    messages: list[dict]
    temperature: float = 0.15
    max_tokens: int = 900
    response_format: dict | None = None


def _usage_month() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


def _normalize_kind(kind: str | None, *, endpoint_default: str) -> str:
    raw = (kind or endpoint_default).strip().lower()
    if raw in ("short", "long", "sheet"):
        return raw
    return endpoint_default


def _quota_for_kind(kind: str, *, premium: bool = False) -> int:
    if premium:
        if kind == "long":
            return int(settings.fieldnote_ai_long_pro_monthly_quota)
        if kind == "sheet":
            return int(settings.fieldnote_ai_sheet_pro_monthly_quota)
        return int(settings.fieldnote_ai_short_pro_monthly_quota)
    if kind == "long":
        return int(settings.fieldnote_ai_long_monthly_quota)
    if kind == "sheet":
        return int(settings.fieldnote_ai_sheet_monthly_quota)
    return int(settings.fieldnote_ai_short_monthly_quota)


def _column_for_kind(kind: str) -> str:
    if kind == "long":
        return "long_count"
    if kind == "sheet":
        return "sheet_count"
    return "short_count"


def _ensure_kind_columns(db: Session) -> None:
    """구 스키마에 short/long/sheet 컬럼이 없으면 추가 (idempotent)."""
    global _kind_columns_ready
    if _kind_columns_ready:
        return
    for col in ("short_count", "long_count", "sheet_count"):
        db.execute(
            text(
                f"""
                ALTER TABLE device_ai_usage
                ADD COLUMN IF NOT EXISTS {col} INTEGER NOT NULL DEFAULT 0
                """
            )
        )
    db.commit()
    _kind_columns_ready = True


def _check_and_increment_quota(db: Session, device_id: str, kind: str, *, premium: bool = False) -> None:
    _ensure_kind_columns(db)
    month = _usage_month()
    col = _column_for_kind(kind)
    quota = _quota_for_kind(kind, premium=premium)

    # 한도 초과면 증가시키지 않음
    db.execute(
        text(
            f"""
            INSERT INTO device_ai_usage (device_id, usage_month, call_count, {col})
            VALUES (:did, :mon, 0, 0)
            ON CONFLICT (device_id, usage_month) DO NOTHING
            """
        ),
        {"did": device_id, "mon": month},
    )
    db.commit()

    updated = db.execute(
        text(
            f"""
            UPDATE device_ai_usage
            SET {col} = {col} + 1,
                call_count = call_count + 1,
                updated_at = now()
            WHERE device_id = :did
              AND usage_month = :mon
              AND {col} < :quota
            RETURNING {col} AS used
            """
        ),
        {"did": device_id, "mon": month, "quota": quota},
    ).mappings().first()
    db.commit()

    if not updated:
        raise HTTPException(
            429,
            detail={
                "code": "quota_exceeded",
                "kind": kind,
                "message": (
                    (
                        "이번 달 AI 분석 한도를 모두 사용했습니다."
                        if kind != "sheet"
                        else "이번 달 주소표 AI 한도를 모두 사용했습니다."
                    )
                    + (" FieldNote Pro 구독 시 한도가 확대됩니다." if not premium else "")
                ),
            },
        )


@router.post("/vision")
async def ai_vision(
    body: AiProxyRequest,
    db: Session = Depends(get_platform_db),
    user: CurrentUser | None = Depends(get_optional_user),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    x_ai_kind: str | None = Header(default=None, alias="X-Ai-Kind"),
):
    kind = _normalize_kind(x_ai_kind, endpoint_default="short")
    if kind == "sheet":
        kind = "short"
    return await _proxy_openai(body, x_device_id, db, kind=kind, user=user)


@router.post("/sheet")
async def ai_sheet(
    body: AiProxyRequest,
    db: Session = Depends(get_platform_db),
    user: CurrentUser | None = Depends(get_optional_user),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    x_ai_kind: str | None = Header(default=None, alias="X-Ai-Kind"),
):
    return await _proxy_openai(
        body,
        x_device_id,
        db,
        kind=_normalize_kind(x_ai_kind, endpoint_default="sheet"),
        max_tokens_default=3500,
        user=user,
    )


def _is_fieldnote_premium(db: Session, user: CurrentUser | None) -> bool:
    if user is None:
        return False
    try:
        ent = list_entitlements(db, user.id)
        return bool(ent.get("fieldnote"))
    except Exception:
        _log.exception("entitlement check failed user_id=%s", getattr(user, "id", None))
        return False


async def _proxy_openai(
    body: AiProxyRequest,
    device_id: str | None,
    db: Session,
    *,
    kind: str,
    max_tokens_default: int = 900,
    user: CurrentUser | None = None,
):
    if not settings.openai_api_key:
        raise HTTPException(503, "OpenAI API 미설정")
    did = (device_id or "").strip()
    if not did:
        raise HTTPException(401, detail={"code": "device_required", "message": "X-Device-Id 헤더가 필요합니다."})
    if len(did) > 128:
        raise HTTPException(400, detail={"code": "device_invalid", "message": "X-Device-Id가 올바르지 않습니다."})
    premium = _is_fieldnote_premium(db, user)
    _check_and_increment_quota(db, did, kind, premium=premium)
    # VPS OPENAI_MODEL이 우선 — 앱 body.model이 예전 gpt-4o로 고정돼 있어도 서버 업그레이드가 적용됨
    model = (settings.openai_model or body.model or "gpt-5-mini").strip()
    requested_tokens = int(body.max_tokens or max_tokens_default)
    payload: dict = {
        "model": model,
        "messages": body.messages,
    }
    # gpt-5 / o-series: max_tokens 미지원 → max_completion_tokens (+ reasoning 여유)
    if _uses_completion_tokens(model):
        payload["max_completion_tokens"] = max(requested_tokens, 4000)
        payload["reasoning_effort"] = "low"
    else:
        payload["temperature"] = body.temperature
        payload["max_tokens"] = requested_tokens
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
