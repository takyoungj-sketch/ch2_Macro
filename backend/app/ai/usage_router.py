"""관리자 AI 사용량 장부. 질문 문장 없음."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from app.ai.usage_log import month_snapshot

router = APIRouter(prefix="/admin/ai-usage", tags=["admin-ai-usage"], include_in_schema=False)


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
