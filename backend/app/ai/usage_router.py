"""관리자 AI 사용량 장부. 질문 문장 없음."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.config import settings
from app.ai.usage_log import month_snapshot

router = APIRouter(prefix="/admin/ai-usage", tags=["admin-ai-usage"], include_in_schema=False)


@router.get("/accounts")
def account_usage(request: Request):
    from app.ai import allowances as q
    from app.platform.db import get_platform_engine
    from sqlalchemy import select, func
    user = q.request_user(request)
    if user is None or user.role != "admin":
        raise HTTPException(403, "관리자만 이용할 수 있습니다.")
    if not settings.ai_subscription_quota_enabled:
        return {"enabled": False, "balances": [], "costs": []}
    engine = get_platform_engine()
    with engine.connect() as c:
        balance_rows = c.execute(select(q.balances).order_by(q.balances.c.period_start.desc()).limit(500)).mappings().all()
        costs = c.execute(select(q.calls.c.stage, q.calls.c.status,
            func.count().label("calls"), func.sum(q.calls.c.usd).label("estimated_usd")).group_by(
                q.calls.c.stage, q.calls.c.status)).mappings().all()
        pending = c.execute(select(q.jobs.c.id, q.jobs.c.user_id, q.jobs.c.feature,
            q.jobs.c.created_at).where(q.jobs.c.status == "reserved").limit(100)).mappings().all()
    return {"enabled": True, "balances": [dict(r) for r in balance_rows],
            "costs": [dict(r) for r in costs], "pending": [dict(r) for r in pending]}


def _require_admin(x_qa_audit_token: str | None) -> None:
    expected = (settings.qa_audit_token or "").strip()
    if not expected:
        return
    if (x_qa_audit_token or "").strip() != expected:
        raise HTTPException(status_code=401, detail="X-Qa-Audit-Token 이 없거나 잘못되었습니다.")


@router.get("/")
@router.get("")
def get_usage(
    month: str | None = None,
    x_qa_audit_token: str | None = Header(default=None, alias="X-Qa-Audit-Token"),
) -> dict[str, Any]:
    _require_admin(x_qa_audit_token)
    if month and (len(month) != 7 or month[4] != "-"):
        raise HTTPException(status_code=400, detail="month는 YYYY-MM")
    snap = month_snapshot(month)
    return snap
