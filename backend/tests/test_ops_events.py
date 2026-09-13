"""운영 이벤트 검증."""

from app.platform.ops_events import (
    new_visitor_id,
    normalize_path,
    normalize_visitor_id,
    parse_event,
)


def test_parse_event_allows_known_pairs():
    parsed = parse_event("hub", "page_view", "/board/")
    assert parsed == {"product": "hub", "event_name": "page_view", "path": "/board/"}
    assert parse_event("viewer", "download", "/download")["event_name"] == "download"


def test_parse_event_rejects_unknown_or_absolute_path():
    assert parse_event("hub", "hack", "/") is None
    assert parse_event("unknown", "page_view", "/") is None
    parsed = parse_event("hub", "page_view", "https://evil.example/")
    assert parsed is not None
    assert parsed["path"] is None


def test_kst_day_windows_are_utc_midnight_kst():
    from datetime import datetime, timezone

    from app.platform.ops_events import kst_day_windows

    now = datetime(2026, 9, 13, 22, 0, tzinfo=timezone.utc)
    today, yesterday = kst_day_windows(now)
    assert today.tzinfo is not None
    assert (today - yesterday).total_seconds() == 24 * 3600
    assert today.hour == 15
    assert today.minute == 0


def test_visitor_id_shape():
    vid = new_visitor_id()
    assert normalize_visitor_id(vid) == vid
    assert normalize_visitor_id("short") is None
    assert normalize_path("") is None
    assert normalize_path("/download") == "/download"
