"""운영 이벤트 검증·기록. IP는 저장하지 않는다."""

from __future__ import annotations

import json
import logging
import re
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

_KST = timezone(timedelta(hours=9))

logger = logging.getLogger(__name__)

PRODUCTS = frozenset({"hub", "macro", "viewer", "fieldnote", "board", "admin"})
EVENT_NAMES = frozenset({"page_view", "download", "ticket_create", "login"})
VID_COOKIE = "ch2_vid"
VID_MAX_AGE = 365 * 24 * 3600
VID_RE = re.compile(r"^[A-Za-z0-9]{8,64}$")
PATH_MAX = 200
_MAX_PER_WINDOW = 60
_WINDOW_SEC = 60

_hits: dict[str, list[float]] = defaultdict(list)

PIXEL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00"
    b"\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00"
    b"\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def normalize_visitor_id(raw: str | None) -> str | None:
    value = (raw or "").strip()
    if not VID_RE.match(value):
        return None
    return value


def new_visitor_id() -> str:
    return secrets.token_hex(16)


def normalize_path(raw: str | None) -> str | None:
    value = (raw or "").strip()
    if not value:
        return None
    if value.startswith("http://") or value.startswith("https://"):
        return None
    return value[:PATH_MAX]


def parse_event(product: str | None, event_name: str | None, path: str | None) -> dict | None:
    prod = (product or "").strip()
    name = (event_name or "").strip()
    if prod not in PRODUCTS or name not in EVENT_NAMES:
        return None
    return {
        "product": prod,
        "event_name": name,
        "path": normalize_path(path),
    }


def too_many_events(visitor_id: str) -> bool:
    now = time.monotonic()
    kept = [t for t in _hits[visitor_id] if now - t < _WINDOW_SEC]
    _hits[visitor_id] = kept
    return len(kept) >= _MAX_PER_WINDOW


def record_hit(visitor_id: str) -> None:
    _hits[visitor_id].append(time.monotonic())


def kst_day_windows(now: datetime | None = None) -> tuple[datetime, datetime]:
    """KST 오늘 0시·어제 0시를 UTC로 반환."""
    current = datetime.now(_KST) if now is None else now
    if current.tzinfo is None:
        current = current.replace(tzinfo=_KST)
    else:
        current = current.astimezone(_KST)
    today = current.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    return today.astimezone(timezone.utc), yesterday.astimezone(timezone.utc)


def insert_event(
    db: Session,
    *,
    product: str,
    event_name: str,
    visitor_id: str,
    user_id: int | None,
    path: str | None,
    meta: dict | None = None,
) -> bool:
    try:
        db.execute(
            text(
                """
                INSERT INTO ops_events (product, event_name, visitor_id, user_id, path, meta)
                VALUES (:product, :event_name, :vid, :uid, :path, CAST(:meta AS jsonb))
                """
            ),
            {
                "product": product,
                "event_name": event_name,
                "vid": visitor_id,
                "uid": user_id,
                "path": path,
                "meta": None if not meta else json.dumps(meta, ensure_ascii=False),
            },
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        logger.warning("ops_events insert failed", exc_info=True)
        return False
