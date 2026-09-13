"""운영 이벤트 수집 + 관리자 대시보드."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.platform.board_policy import ticket_no
from app.platform.db import get_platform_db
from app.platform.deps import CurrentUser, get_optional_user, require_admin
from app.platform.ops_events import (
    PIXEL_GIF,
    VID_COOKIE,
    VID_MAX_AGE,
    insert_event,
    kst_day_windows,
    new_visitor_id,
    normalize_visitor_id,
    parse_event,
    record_hit,
    too_many_events,
)

router = APIRouter(prefix="/ops", tags=["platform-ops"])


class EventIn(BaseModel):
    product: str = Field(min_length=1, max_length=32)
    event_name: str = Field(min_length=1, max_length=64)
    path: str | None = Field(default=None, max_length=200)
    visitor_id: str | None = Field(default=None, max_length=64)


def _cookie_domain() -> str | None:
    d = (settings.platform_cookie_domain or "").strip()
    return d or None


def _set_vid_cookie(response: Response, visitor_id: str) -> None:
    response.set_cookie(
        key=VID_COOKIE,
        value=visitor_id,
        httponly=True,
        secure=settings.platform_cookie_secure,
        samesite="lax",
        domain=_cookie_domain(),
        max_age=VID_MAX_AGE,
        path="/",
    )


def _resolve_visitor(request: Request, hinted: str | None) -> tuple[str, bool]:
    existing = normalize_visitor_id(request.cookies.get(VID_COOKIE)) or normalize_visitor_id(
        hinted
    )
    if existing:
        return existing, False
    return new_visitor_id(), True


def _ingest(
    *,
    request: Request,
    db: Session,
    user: CurrentUser | None,
    product: str,
    event_name: str,
    path: str | None,
    hinted_vid: str | None,
) -> tuple[str, bool]:
    parsed = parse_event(product, event_name, path)
    if not parsed:
        raise HTTPException(400, "invalid_event")
    visitor_id, is_new = _resolve_visitor(request, hinted_vid)
    if too_many_events(visitor_id):
        raise HTTPException(429, "rate_limited")
    record_hit(visitor_id)
    insert_event(
        db,
        product=parsed["product"],
        event_name=parsed["event_name"],
        visitor_id=visitor_id,
        user_id=user.id if user else None,
        path=parsed["path"],
    )
    return visitor_id, is_new


@router.post("/event")
def post_event(
    body: EventIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_platform_db),
    user: Annotated[CurrentUser | None, Depends(get_optional_user)] = None,
):
    visitor_id, is_new = _ingest(
        request=request,
        db=db,
        user=user,
        product=body.product,
        event_name=body.event_name,
        path=body.path,
        hinted_vid=body.visitor_id,
    )
    if is_new:
        _set_vid_cookie(response, visitor_id)
    return {"ok": True}


@router.get("/pixel.gif")
def pixel_event(
    request: Request,
    db: Session = Depends(get_platform_db),
    user: Annotated[CurrentUser | None, Depends(get_optional_user)] = None,
    e: str = Query(default="", max_length=64),
    p: str = Query(default="", max_length=32),
    path: str | None = Query(default=None, max_length=200),
):
    response = Response(content=PIXEL_GIF, media_type="image/gif")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    try:
        visitor_id, is_new = _ingest(
            request=request,
            db=db,
            user=user,
            product=p,
            event_name=e,
            path=path,
            hinted_vid=None,
        )
        if is_new:
            _set_vid_cookie(response, visitor_id)
    except HTTPException:
        pass
    return response


def _event_bucket(
    db: Session,
    event_name: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, int]:
    clauses = ["event_name = :name"]
    params: dict = {"name": event_name}
    if start is not None:
        clauses.append("occurred_at >= :start")
        params["start"] = start
    if end is not None:
        clauses.append("occurred_at < :end")
        params["end"] = end
    row = db.execute(
        text(
            f"""
            SELECT COUNT(*) AS events,
                   COUNT(DISTINCT visitor_id) AS visitors
            FROM ops_events
            WHERE {" AND ".join(clauses)}
            """
        ),
        params,
    ).mappings().first()
    return {
        "events": int(row["events"] or 0) if row else 0,
        "visitors": int(row["visitors"] or 0) if row else 0,
    }


def _ticket_count(
    db: Session,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> int:
    clauses = ["TRUE"]
    params: dict = {}
    if start is not None:
        clauses.append("created_at >= :start")
        params["start"] = start
    if end is not None:
        clauses.append("created_at < :end")
        params["end"] = end
    n = db.execute(
        text(f"SELECT COUNT(*) FROM posts WHERE {' AND '.join(clauses)}"),
        params,
    ).scalar() or 0
    return int(n)


def _traffic_slice(
    db: Session,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, int]:
    views = _event_bucket(db, "page_view", start=start, end=end)
    downloads = _event_bucket(db, "download", start=start, end=end)
    return {
        "visitors": views["visitors"],
        "page_views": views["events"],
        "downloads": downloads["events"],
        "tickets": _ticket_count(db, start=start, end=end),
    }


@router.get("/dashboard")
def ops_dashboard(
    db: Session = Depends(get_platform_db),
    _admin: CurrentUser = Depends(require_admin),
):
    today, yesterday = kst_day_windows()
    open_n = db.execute(
        text("SELECT COUNT(*) FROM posts WHERE status = 'open' AND is_pinned = FALSE")
    ).scalar() or 0
    checking_n = db.execute(
        text("SELECT COUNT(*) FROM posts WHERE status = 'checking' AND is_pinned = FALSE")
    ).scalar() or 0
    today_n = _ticket_count(db, start=today)
    recent = db.execute(
        text(
            """
            SELECT p.id, p.product, p.category, p.title, p.status, p.created_at, u.nickname
            FROM posts p
            JOIN users u ON u.id = p.user_id
            WHERE p.is_pinned = FALSE
            ORDER BY p.created_at DESC
            LIMIT 8
            """
        )
    ).mappings().all()
    items = [
        {
            "id": int(row["id"]),
            "ticket_no": ticket_no(int(row["id"])),
            "product": row["product"],
            "category": row["category"],
            "title": row["title"],
            "status": row["status"],
            "author_name": row["nickname"],
            "created_at": row["created_at"].isoformat().replace("+00:00", "Z"),
        }
        for row in recent
    ]
    return {
        "tickets": {
            "open": int(open_n),
            "checking": int(checking_n),
            "today": int(today_n),
            "recent": items,
        },
        "traffic": {
            "today": _traffic_slice(db, start=today),
            "yesterday": _traffic_slice(db, start=yesterday, end=today),
            "total": _traffic_slice(db),
        },
    }
