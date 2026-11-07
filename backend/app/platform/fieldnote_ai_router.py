"""FieldNote AI 프록시 — OpenAI 키 서버 보관 + device quota (short/long/sheet)."""

from __future__ import annotations

import logging
import json
import uuid
from contextlib import nullcontext
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


@router.get("/allowance")
def fieldnote_allowance(db: Session = Depends(get_platform_db),
                        user: CurrentUser | None = Depends(get_optional_user)):
    from app.ai import allowances as quota
    if not settings.ai_subscription_quota_enabled or user is None:
        return {"mode": "legacy", "items": []}
    if user.role == "admin":
        return {"mode": "staff", "items": []}
    grant = quota.grant_for(db, user)
    return quota.snapshot(db.get_bind(), grant) if grant else {"mode": "legacy", "items": []}


def _uses_completion_tokens(model: str) -> bool:
    m = (model or "").strip().lower()
    return m.startswith("gpt-5") or m.startswith("o1") or m.startswith("o3") or m.startswith("o4")


class AiProxyRequest(BaseModel):
    request_id: str | None = None
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


def _check_and_increment_quota(db: Session, device_id: str, kind: str, *, premium: bool = False) -> str:
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
    return month


def _refund_legacy_quota(db: Session, device_id: str, kind: str, month: str):
    col = _column_for_kind(kind)
    db.execute(text(f"""UPDATE device_ai_usage SET
        {col}=CASE WHEN {col}>0 THEN {col}-1 ELSE 0 END,
        call_count=CASE WHEN call_count>0 THEN call_count-1 ELSE 0 END,
        updated_at=now() WHERE device_id=:did AND usage_month=:mon"""),
        {"did": device_id, "mon": month})
    db.commit()


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
    return await _proxy_openai(body, x_device_id, db, kind=kind, user=user, feature="photo_analysis_image")


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
        kind="sheet",
        max_tokens_default=3500,
        user=user,
        feature="address_sheet_job",
    )


@router.post("/write")
async def ai_write(body: AiProxyRequest, db: Session = Depends(get_platform_db),
                   user: CurrentUser | None = Depends(get_optional_user),
                   x_device_id: str | None = Header(default=None, alias="X-Device-Id")):
    return await _proxy_openai(body, x_device_id, db, kind="long", user=user, feature="text_writing")


def validated_input(body, feature):
    """Server counts images; endpoint determines feature, never X-Ai-Kind.
    Restrict image inputs to inline images so the proxy cannot fetch private URLs.
    """
    if len(body.messages) > 40:
        raise HTTPException(413, "AI 입력 메시지는 최대 40개입니다.")
    seen, text_size, size = set(), 0, 0
    for message in body.messages:
        content = message.get("content", "")
        if isinstance(content, str):
            text_size += len(content)
        elif isinstance(content, list):
            deduped = []
            for part in content:
                if part.get("type") == "image_url":
                    url = (part.get("image_url") or {}).get("url", "")
                    if not isinstance(url, str) or not url.startswith(("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")):
                        raise HTTPException(400, "사진은 지원되는 이미지 첨부로 전송해 주세요.")
                    if url in seen:
                        continue
                    seen.add(url)
                    size += len(url)
                elif part.get("type") == "text":
                    text_size += len(str(part.get("text", "")))
                else:
                    raise HTTPException(400, "지원하지 않는 AI 입력 형식입니다.")
                deduped.append(part)
            message["content"] = deduped
        else:
            raise HTTPException(400, "지원하지 않는 AI 입력 형식입니다.")
    if len(seen) > 12 or size > 20_000_000 or text_size > 40_000:
        raise HTTPException(413, "한 작업은 사진 최대 12장, 첨부 20MB, 입력 40,000자까지 처리합니다.")
    if feature == "photo_analysis_image" and not seen:
        raise HTTPException(400, "분석할 사진을 첨부해 주세요.")
    if feature == "text_writing" and seen:
        raise HTTPException(400, "문구 작성은 텍스트 입력을 사용합니다. 사진은 사진 분석에서 이용해 주세요.")
    if not seen and not text_size:
        raise HTTPException(400, "분석할 내용이 없습니다.")
    return len(seen) if feature == "photo_analysis_image" else 1


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
    feature: str = "photo_analysis_image",
):
    if not settings.openai_api_key:
        raise HTTPException(503, "OpenAI API 미설정")
    did = (device_id or "").strip()
    if not did:
        raise HTTPException(401, detail={"code": "device_required", "message": "X-Device-Id 헤더가 필요합니다."})
    if len(did) > 128:
        raise HTTPException(400, detail={"code": "device_invalid", "message": "X-Device-Id가 올바르지 않습니다."})
    from app.ai import allowances as quota
    units = validated_input(body, feature)
    premium = _is_fieldnote_premium(db, user)
    ticket = None
    if settings.ai_subscription_quota_enabled and user is not None and user.role != "admin":
        grant = quota.grant_for(db, user)
        if grant:
            if not premium:
                raise HTTPException(403, "Fieldnote 구독이 필요합니다.")
            ticket = quota.reserve(db.get_bind(), grant, feature, units, body.request_id or f"legacy-{uuid.uuid4()}",
                quota.fingerprint({"messages": body.messages, "feature": feature, "response_format": body.response_format,
                                   "max_tokens": body.max_tokens, "temperature": body.temperature}))
            if ticket.replay is not None:
                return {**ticket.replay, "ch2_usage": quota.snapshot(db.get_bind(), grant)}
    legacy_month = None
    if ticket is None and not (settings.ai_subscription_quota_enabled and user is not None and user.role == "admin"):
        if feature == "text_writing":
            raise HTTPException(403, "문구 작성은 동시 구독 AI 정책 활성화 후 이용할 수 있습니다.")
        legacy_month = _check_and_increment_quota(db, did, kind, premium=premium)
    # VPS OPENAI_MODEL이 우선 — 앱 body.model이 예전 gpt-4o로 고정돼 있어도 서버 업그레이드가 적용됨
    model = (settings.openai_model or body.model or "gpt-5-mini").strip()
    requested_tokens = min(max(1, int(body.max_tokens or max_tokens_default)), settings.ai_max_output_tokens)
    payload: dict = {
        "model": model,
        "messages": body.messages,
    }
    if feature == "text_writing":
        payload["messages"] = [{"role": "system", "content":
            "사용자가 제공한 현장 메모를 이해하기 쉬운 한국어 조사 문구로 정리합니다. "
            "제공되지 않은 사실·수치·가격 판단을 추가하지 않습니다. 정리된 문구만 답하세요."}, *body.messages]
    # gpt-5 / o-series: max_tokens 미지원 → max_completion_tokens (+ reasoning 여유)
    if _uses_completion_tokens(model):
        payload["max_completion_tokens"] = min(max(requested_tokens, 4000), settings.ai_max_output_tokens)
        payload["reasoning_effort"] = "low"
    else:
        payload["temperature"] = body.temperature
        payload["max_tokens"] = requested_tokens
    if body.response_format:
        payload["response_format"] = body.response_format
    provider_recorded = False
    try:
        with quota.tracking(ticket) if ticket else nullcontext():
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
                raise HTTPException(502, "AI 응답을 확인하지 못했습니다. 다시 시도해 주세요.")
            if res.status_code >= 400:
                raise HTTPException(502, "AI 공급자 응답 오류입니다. 잠시 후 다시 시도해 주세요.")
            usage = data.get("usage") or {}
            quota.record_provider(model=str(data.get("model") or model),
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
                cached_tokens=int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0))
            provider_recorded = True
            content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
            if not content or (data.get("choices") or [{}])[0].get("finish_reason") == "length":
                raise HTTPException(502, "AI 답변이 완료되지 않았습니다. 다시 시도해 주세요.")
            if feature == "address_sheet_job" or (body.response_format and body.response_format.get("type") == "json_object"):
                try:
                    parsed = json.loads(content)
                    if not isinstance(parsed, dict):
                        raise ValueError()
                    if feature == "address_sheet_job":
                        rows = parsed.get("rows", parsed.get("addresses", parsed.get("items", [])))
                        fields = ("address", "lot_address", "lotAddress", "지번", "지번주소", "필지")
                        if not isinstance(rows, list) or not any(isinstance(row, dict) and any(
                            isinstance(row.get(k), str) and row[k].strip() for k in fields) for row in rows):
                            raise ValueError()
                except (ValueError, TypeError):
                    raise HTTPException(502, "AI 응답 형식을 확인하지 못했습니다. 다시 시도해 주세요.")
            if ticket:
                quota.finish(ticket, data)
                data["ch2_usage"] = quota.snapshot(db.get_bind(), ticket.grant)
                data["ch2_request_id"] = ticket.id
            return data
    except BaseException:
        if ticket:
            if not provider_recorded:
                with quota.tracking(ticket):
                    quota.record_provider_failure(model)
            quota.finish(ticket, error="fieldnote_failed")
        elif legacy_month:
            _refund_legacy_quota(db, did, kind, legacy_month)
        raise
