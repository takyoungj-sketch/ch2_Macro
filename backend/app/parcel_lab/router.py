"""관리자 대장DB 조회 API. 공개 앱에 링크하지 않음. 읽기 전용."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from app.parcel_lab.db import UNAVAILABLE, get_parcel_engine, parcel_db_available
from app.parcel_lab.queries import PAGE_MAX, fetch_parcel_detail, fetch_status, search_parcels
from app.qa_audit.router import _require_token

router = APIRouter(prefix="/admin/parcel", tags=["admin-parcel"], include_in_schema=False)


@router.get("/status")
def get_status(
    x_qa_audit_token: str | None = Header(default=None, alias="X-Qa-Audit-Token"),
) -> dict[str, Any]:
    _require_token(x_qa_audit_token)
    if not parcel_db_available():
        return {"available": False, "detail": UNAVAILABLE}
    eng = get_parcel_engine()
    assert eng is not None
    with eng.connect() as conn:
        return fetch_status(conn)


@router.get("/search")
def get_search(
    q: str | None = Query(default=None),
    sido: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0, le=50_000),
    limit: int = Query(default=50, ge=1, le=PAGE_MAX),
    x_qa_audit_token: str | None = Header(default=None, alias="X-Qa-Audit-Token"),
) -> dict[str, Any]:
    _require_token(x_qa_audit_token)
    if not parcel_db_available():
        raise HTTPException(status_code=503, detail=UNAVAILABLE)
    eng = get_parcel_engine()
    assert eng is not None
    with eng.connect() as conn:
        return search_parcels(conn, q=q, sido=sido, offset=offset, limit=limit)


@router.get("/parcels/{pnu}")
def get_parcel(
    pnu: str,
    x_qa_audit_token: str | None = Header(default=None, alias="X-Qa-Audit-Token"),
) -> dict[str, Any]:
    _require_token(x_qa_audit_token)
    if not parcel_db_available():
        raise HTTPException(status_code=503, detail=UNAVAILABLE)
    eng = get_parcel_engine()
    assert eng is not None
    with eng.connect() as conn:
        detail = fetch_parcel_detail(conn, pnu)
    if not detail:
        raise HTTPException(status_code=404, detail="그 PNU 필지가 대장DB에 없습니다.")
    return detail
