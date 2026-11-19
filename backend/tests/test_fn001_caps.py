"""FN-001 단위 2. 하루 호출 상한, 금액 상한, 분·시간 속도 제한."""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, update
from starlette.requests import Request

from app.ai import allowances as quota
from app.ai.rate_limit import (
    MemoryRateStore,
    check_fieldnote_ai_rate_limit,
    set_rate_store,
)
from app.config import settings
from app.platform import fieldnote_ai_access as access
from app.platform import fieldnote_ai_router as route
from app.platform.fieldnote_ai_access import FieldnoteAiAccess, reserve_daily_call
from app.platform.fieldnote_ai_router import AiProxyRequest


def _engine(tmp_path, name="cap.db"):
    engine = create_engine(
        f"sqlite:///{tmp_path / name}",
        connect_args={"timeout": 30},
    )
    quota.meta.create_all(engine)
    return engine


def _grant():
    start = datetime(2026, 11, 1, tzinfo=timezone.utc)
    return quota.Grant(7, "bundle", start, start + timedelta(days=31))


def _request(peer, forwarded="9.9.9.9", real=None):
    headers = [(b"x-forwarded-for", forwarded.encode())]
    if real:
        headers.append((b"x-real-ip", real.encode()))
    return Request({"type": "http", "client": (peer, 9), "headers": headers})


def _image(url="data:image/jpeg;base64,YQ=="):
    return {"type": "image_url", "image_url": {"url": url}}


class _Client:
    posts = 0

    def __init__(self, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        pass

    async def post(self, *_args, **_kwargs):
        type(self).posts += 1
        reply = getattr(self, "reply", None) or {
            "model": "gpt-5-mini",
            "usage": {"prompt_tokens": 100, "completion_tokens": 30},
            "choices": [{"message": {"content": "{\"primary_name\":\"tree\"}"}, "finish_reason": "stop"}],
        }
        return SimpleNamespace(status_code=200, json=lambda: reply)


def _arm(monkeypatch, engine, grant):
    _Client.posts = 0
    _Client.reply = None
    monkeypatch.setattr(settings, "openai_api_key", "not-a-real-key")
    monkeypatch.setattr(route.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(
        route,
        "resolve_fieldnote_ai_access",
        lambda *_args, **_kwargs: FieldnoteAiAccess("paid", grant.start, grant.end, None),
    )
    monkeypatch.setattr(quota, "grant_for", lambda *_args, **_kwargs: grant)
    return SimpleNamespace(get_bind=lambda: engine)


def _call(db, grant, request_id, request=None):
    body = AiProxyRequest(request_id=request_id, messages=[{"role": "user", "content": [_image()]}])
    return asyncio.run(route._proxy_openai(body, None, db, kind="short", user=SimpleNamespace(id=grant.user_id, role="member"), request=request))


def _daily_used(engine):
    with engine.connect() as conn:
        row = conn.execute(
            select(quota.balances.c.used, quota.balances.c.reserved).where(
                quota.balances.c.user_id == 0,
                quota.balances.c.feature == access.DAILY,
            )
        ).first()
    return (0, 0) if row is None else (int(row[0]), int(row[1]))


def test_concurrent_requests_stop_at_the_call_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "fieldnote_ai_daily_cap_calls", 5)
    engine = _engine(tmp_path)

    def once(number):
        try:
            reserve_daily_call(engine, f"parent-{number}")
            return True
        except HTTPException as exc:
            assert exc.detail["code"] == "quota_exceeded"
            return False

    with ThreadPoolExecutor(12) as pool:
        results = list(pool.map(once, range(12)))
    assert sum(results) == 5
    assert _daily_used(engine) == (0, 5)
    engine.dispose()


def test_postgres_call_cap_when_a_dedicated_url_is_set(monkeypatch):
    url = os.environ.get("FN001_TEST_DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("전용 Postgres 시험 주소가 없다. 운영 DB와 .env는 쓰지 않는다.")
    monkeypatch.setattr(settings, "fieldnote_ai_daily_cap_calls", 3)
    engine = create_engine(url, connect_args={"connect_timeout": 3})
    quota.meta.create_all(engine)
    try:
        with ThreadPoolExecutor(6) as pool:
            results = list(pool.map(lambda n: _reserve_or_deny(engine, n), range(6)))
        assert sum(results) == 3
    finally:
        quota.meta.drop_all(engine)
        engine.dispose()


def _reserve_or_deny(engine, number):
    try:
        reserve_daily_call(engine, f"pg-{number}-{datetime.now().timestamp()}")
        return True
    except HTTPException:
        return False


def test_settlement_moves_user_and_global_together(tmp_path, monkeypatch):
    engine = _engine(tmp_path)
    grant = _grant()
    db = _arm(monkeypatch, engine, grant)
    _call(db, grant, "settle")
    photo = quota.snapshot(engine, grant)["items"][1]
    assert photo["used"] == 1
    assert _daily_used(engine) == (1, 0)
    with engine.connect() as conn:
        usd = conn.execute(select(quota.calls.c.usd)).scalar_one()
    assert usd is not None and usd > 0
    engine.dispose()


def test_failure_and_abandoned_release_the_global_row(tmp_path, monkeypatch):
    engine = _engine(tmp_path)
    grant = _grant()
    db = _arm(monkeypatch, engine, grant)
    _Client.reply = {"model": "gpt-5-mini", "choices": [], "usage": {}}
    with pytest.raises(HTTPException):
        _call(db, grant, "fail")
    assert _daily_used(engine) == (0, 0)
    assert quota.snapshot(engine, grant)["items"][1]["used"] == 0
    hung = reserve_daily_call(engine, "hung")
    with engine.begin() as conn:
        conn.execute(
            update(quota.jobs).where(quota.jobs.c.id == hung.id).values(
                created_at=datetime.now(timezone.utc) - timedelta(minutes=31)
            )
        )
    quota.release_abandoned(engine, hung.id, "operator", "worker stopped")
    assert _daily_used(engine) == (0, 0)
    engine.dispose()


def test_inflight_calls_use_the_worst_price_and_block_openai(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "fieldnote_ai_worst_call_usd", 3)
    monkeypatch.setattr(settings, "fieldnote_ai_daily_cap_usd", 5)
    engine = _engine(tmp_path)
    reserve_daily_call(engine, "already-running")
    grant = _grant()
    db = _arm(monkeypatch, engine, grant)
    with pytest.raises(HTTPException) as denied:
        _call(db, grant, "blocked")
    assert denied.value.status_code == 503
    assert denied.value.detail["code"] == "daily_cap"
    assert _Client.posts == 0
    assert quota.snapshot(engine, grant)["items"][1]["used"] == 0
    engine.dispose()


def test_call_cap_does_not_reach_openai(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "fieldnote_ai_daily_cap_calls", 1)
    engine = _engine(tmp_path)
    grant = _grant()
    db = _arm(monkeypatch, engine, grant)
    _call(db, grant, "first")
    with pytest.raises(HTTPException) as denied:
        _call(db, grant, "second")
    assert denied.value.detail["code"] == "daily_cap"
    assert _Client.posts == 1
    engine.dispose()


def test_minute_and_hour_windows_and_forged_forwarded_for(monkeypatch):
    set_rate_store(MemoryRateStore())
    monkeypatch.setattr(settings, "fieldnote_ai_account_per_minute", 10)
    monkeypatch.setattr(settings, "fieldnote_ai_account_per_hour", 120)
    monkeypatch.setattr(settings, "fieldnote_ai_ip_per_minute", 20)
    monkeypatch.setattr(settings, "fieldnote_ai_ip_per_hour", 1000)
    peer = _request("10.1.1.1")
    for _ in range(10):
        check_fieldnote_ai_rate_limit(peer, 7, now=1_000.0)
    with pytest.raises(HTTPException) as held:
        check_fieldnote_ai_rate_limit(peer, 7, now=1_060.0)
    assert held.value.detail["code"] == "rate_limited"
    check_fieldnote_ai_rate_limit(peer, 7, now=1_060.001)
    set_rate_store(MemoryRateStore())
    monkeypatch.setattr(settings, "fieldnote_ai_account_per_minute", 1000)
    monkeypatch.setattr(settings, "fieldnote_ai_ip_per_minute", 1000)
    hour = _request("10.4.4.4")
    for _ in range(120):
        check_fieldnote_ai_rate_limit(hour, 8, now=0.0)
    with pytest.raises(HTTPException):
        check_fieldnote_ai_rate_limit(hour, 8, now=3_600.0)
    check_fieldnote_ai_rate_limit(hour, 8, now=3_600.001)
    set_rate_store(MemoryRateStore())
    monkeypatch.setattr(settings, "fieldnote_ai_account_per_minute", 1000)
    monkeypatch.setattr(settings, "fieldnote_ai_ip_per_minute", 20)
    for _ in range(20):
        check_fieldnote_ai_rate_limit(_request("10.1.1.1", forwarded="9.9.9.9"), 7, now=5.0)
    with pytest.raises(HTTPException):
        check_fieldnote_ai_rate_limit(_request("10.1.1.1", forwarded="8.8.8.8"), 7, now=5.0)
    check_fieldnote_ai_rate_limit(_request("10.1.1.2", forwarded="9.9.9.9"), 7, now=5.0)
    set_rate_store(MemoryRateStore())
    for _ in range(20):
        check_fieldnote_ai_rate_limit(_request("127.0.0.1", real="203.0.113.9"), 7, now=5.0)
    with pytest.raises(HTTPException):
        check_fieldnote_ai_rate_limit(_request("127.0.0.1", forwarded="1.1.1.1", real="203.0.113.9"), 7, now=5.0)
    check_fieldnote_ai_rate_limit(_request("127.0.0.1", forwarded="1.1.1.1", real="203.0.113.10"), 7, now=5.0)


def test_rate_limit_releases_the_account_reservation(tmp_path, monkeypatch):
    set_rate_store(MemoryRateStore())
    monkeypatch.setattr(settings, "fieldnote_ai_account_per_minute", 1)
    monkeypatch.setattr(settings, "fieldnote_ai_account_per_hour", 10)
    monkeypatch.setattr(settings, "fieldnote_ai_ip_per_minute", 100)
    monkeypatch.setattr(settings, "fieldnote_ai_ip_per_hour", 100)
    engine = _engine(tmp_path)
    grant = _grant()
    db = _arm(monkeypatch, engine, grant)
    request = _request("10.8.8.8")
    _call(db, grant, "kept", request)
    with pytest.raises(HTTPException) as denied:
        _call(db, grant, "limited", request)
    assert denied.value.status_code == 429
    assert denied.value.detail["code"] == "rate_limited"
    assert _Client.posts == 1
    photo = quota.snapshot(engine, grant)["items"][1]
    assert (photo["used"], photo["reserved"]) == (1, 0)
    engine.dispose()
