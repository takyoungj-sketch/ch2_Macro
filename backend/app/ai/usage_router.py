"""관리자 AI 사용량 장부. 질문 문장 없음."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.admin_auth import require_admin_access

from app.config import settings
from app.ai.usage_log import month_snapshot

router = APIRouter(prefix="/admin/ai-usage", tags=["admin-ai-usage"], include_in_schema=False)


@router.get("/accounts")
def account_usage(request: Request):
    from app.ai import allowances as q
    from app.platform.db import get_platform_engine
    from sqlalchemy import select, func
    # 관리자 세션 또는 설정된 QA 토큰(랩 화면). 다른 관리자 API와 같은 기준.
    require_admin_access(request)
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


@router.get("/")
@router.get("")
def get_usage(request: Request, month: str | None = None) -> dict[str, Any]:
    # 관리자 세션 또는 설정된 QA 토큰만. 토큰 미설정 시 토큰 경로는 거부한다.
    require_admin_access(request)
    if month and (len(month) != 7 or month[4] != "-"):
        raise HTTPException(status_code=400, detail="month는 YYYY-MM")
    snap = month_snapshot(month)
    return snap
