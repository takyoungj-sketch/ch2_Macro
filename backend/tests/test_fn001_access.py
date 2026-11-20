"""FN-001 단위 1. 접근 등급, 월 한도, 거절 본문, 관리자 원장."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.ai import allowances as quota
from app.config import settings
from app.platform import fieldnote_ai_router as route
from app.platform.fieldnote_ai_access import (
    FieldnoteAiAccess,
    limit_invariant_problems,
    monthly_limit,
    resolve_fieldnote_ai_access,
)
from app.platform.fieldnote_ai_router import AiProxyRequest


def _app_code(detail):
    if isinstance(detail, dict) and detail.get("code"):
        return detail["code"]
    return None


@pytest.fixture
def platform(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'access.db'}")
    quota.meta.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE subscriptions (id INTEGER, user_id INTEGER, product TEXT, plan_id TEXT, "
            "source TEXT, status TEXT, created_at TEXT, current_period_end TEXT)"
        ))
        conn.execute(text(
            "CREATE TABLE entitlements (user_id INTEGER, product TEXT, active BOOLEAN, expires_at TEXT)"
        ))
    yield engine
    engine.dispose()


def _grant_window():
    start = datetime(2026, 11, 1, tzinfo=timezone.utc)
    return start, start + timedelta(days=31)


def _seed(engine, user_id, *, product, fieldnote):
    start, end = _grant_window()
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO subscriptions VALUES (1,:uid,:product,'monthly','web_toss','active',:start,:end)"
        ), {"uid": user_id, "product": product, "start": start, "end": end})
        conn.execute(text("INSERT INTO entitlements VALUES (:uid,'macro',1,NULL)"), {"uid": user_id})
        if fieldnote:
            conn.execute(text("INSERT INTO entitlements VALUES (:uid,'fieldnote',1,NULL)"), {"uid": user_id})
    return start, end


def test_default_limits_keep_paid_above_trial():
    assert limit_invariant_problems() == []
    assert monthly_limit("photo_analysis_image", "paid") == 500
    assert monthly_limit("photo_analysis_image", "trial") == 125
    assert monthly_limit("address_sheet_job", "none") == 0
    assert monthly_limit("text_writing", "expired") == 0


def test_broken_invariant_is_reported(monkeypatch):
    monkeypatch.setattr(settings, "fieldnote_ai_paid_monthly_photo", 10)
    monkeypatch.setattr(settings, "fieldnote_ai_trial_monthly_photo", 25)
    assert "photo_analysis_image" in limit_invariant_problems()


def test_anon_and_macro_only_are_denied(platform, monkeypatch):
    monkeypatch.setattr(settings, "fieldnote_ai_anon_monthly_quota", 50)
    assert resolve_fieldnote_ai_access(Session(platform), None).deny_code == "login_required"
    _seed(platform, 4, product="macro", fieldnote=False)
    access = resolve_fieldnote_ai_access(Session(platform), SimpleNamespace(id=4, role="member"))
    assert access.tier == "none" and access.deny_code == "subscription_required"
    _seed(platform, 5, product="bundle", fieldnote=True)
    paid = resolve_fieldnote_ai_access(Session(platform), SimpleNamespace(id=5, role="member"))
    assert paid.tier == "paid" and paid.deny_code is None
    assert paid.period_start == _grant_window()[0]


def test_rejection_body_matches_app_parser(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    db = SimpleNamespace(get_bind=lambda: None)
    body = AiProxyRequest(messages=[{"role": "user", "content": "메모"}])
    with pytest.raises(HTTPException) as denied:
        asyncio.run(route._proxy_openai(body, "device-1", db, kind="short", user=None))
    assert denied.value.status_code == 401
    assert _app_code(denied.value.detail) == "login_required"
    assert "결제" not in denied.value.detail["message"]


def test_anon_quota_setting_does_not_reopen_device_path(platform, monkeypatch):
    monkeypatch.setattr(settings, "fieldnote_ai_anon_monthly_quota", 50)
    monkeypatch.setattr(settings, "openai_api_key", "not-a-real-key")
    called = []
    monkeypatch.setattr(route, "_check_and_increment_quota", lambda *args, **kwargs: called.append(args))
    body = AiProxyRequest(messages=[{"role": "user", "content": [ {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,YQ=="}} ]}])
    with pytest.raises(HTTPException) as denied:
        asyncio.run(route._proxy_openai(body, "device-1", Session(platform), kind="short", user=None))
    assert denied.value.status_code == 401
    assert called == []


def test_admin_call_is_written_to_the_ledger(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'admin.db'}")
    quota.meta.create_all(engine)
    monkeypatch.setattr(settings, "openai_api_key", "not-a-real-key")
    monkeypatch.setattr(settings, "fieldnote_ai_admin_monthly_photo", 1)

    class Client:
        def __init__(self, **_kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_args):
            pass
        async def post(self, *_args, **_kwargs):
            return SimpleNamespace(status_code=200, json=lambda: {
                "model": "gpt-5-mini",
                "usage": {"prompt_tokens": 10, "completion_tokens": 4},
                "choices": [{"message": {"content": "{\"primary_name\":\"tree\"}"}, "finish_reason": "stop"}],
            })

    monkeypatch.setattr(route.httpx, "AsyncClient", Client)
    user = SimpleNamespace(id=9, role="admin")
    db = SimpleNamespace(get_bind=lambda: engine)
    image = {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,YQ=="}}
    ok = AiProxyRequest(request_id="admin-photo", messages=[{"role": "user", "content": [image]}])
    data = asyncio.run(route._proxy_openai(ok, None, db, kind="short", user=user))
    assert data["ch2_usage"]["plan"] == "bundle"
    assert data["ch2_usage"]["items"][0]["used"] == 1
    with engine.connect() as conn:
        used = conn.execute(select(quota.balances.c.used).where(quota.balances.c.user_id == 9)).scalar_one()
    assert used == 1
    other = {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,Yg=="}}
    over = AiProxyRequest(request_id="admin-over", messages=[{"role": "user", "content": [image, other]}])
    with pytest.raises(HTTPException) as denied:
        asyncio.run(route._proxy_openai(over, None, db, kind="short", user=user))
    assert denied.value.status_code == 429
    assert _app_code(denied.value.detail) == "quota_exceeded"
    engine.dispose()


def test_allowance_denies_without_access(platform):
    with pytest.raises(HTTPException) as denied:
        route.fieldnote_allowance(Session(platform), None)
    assert _app_code(denied.value.detail) == "login_required"
    _seed(platform, 4, product="macro", fieldnote=False)
    with pytest.raises(HTTPException) as macro_only:
        route.fieldnote_allowance(Session(platform), SimpleNamespace(id=4, role="member"))
    assert macro_only.value.status_code == 403
    access = FieldnoteAiAccess("admin", *_grant_window(), None)
    assert access.tier == "admin"
