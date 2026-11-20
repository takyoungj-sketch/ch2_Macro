"""FN-001 단위 4. 스위치와 Macro AI 회귀."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.ai import allowances as quota
from app.ai.rate_limit import check_ai_rate_limit
from app.config import settings
from app.platform import fieldnote_ai_router as route
from app.platform.fieldnote_ai_router import AiProxyRequest


def _image():
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,YQ=="}}


@pytest.mark.parametrize("quota_on", [False, True])
@pytest.mark.parametrize("legacy_on", [False, True])
@pytest.mark.parametrize("body", [
    AiProxyRequest(messages=[{"role": "user", "content": [_image()]}]),
    AiProxyRequest(format=2, mode="short", photos=[{"image": "data:image/jpeg;base64,YQ==", "order": 1}]),
])
def test_anon_and_unentitled_never_reach_openai(monkeypatch, quota_on, legacy_on, body):
    monkeypatch.setattr(settings, "ai_subscription_quota_enabled", quota_on)
    monkeypatch.setattr(settings, "fieldnote_ai_accept_legacy_format", legacy_on)
    monkeypatch.setattr(settings, "fieldnote_ai_anon_monthly_quota", 0)
    monkeypatch.setattr(settings, "openai_api_key", "not-a-real-key")
    posts = []
    monkeypatch.setattr(route.httpx, "AsyncClient", lambda **_kwargs: posts.append("open"))
    device_path = []
    monkeypatch.setattr(route, "_check_and_increment_quota", lambda *args, **kwargs: device_path.append(args))
    monkeypatch.setattr(quota, "grant_for", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.platform.entitlements.list_entitlements", lambda *_args, **_kwargs: {"fieldnote": False})

    db = SimpleNamespace(get_bind=lambda: None)

    def call(user):
        return route._proxy_openai(body, "device-1", db, kind="short", user=user)

    with pytest.raises(HTTPException) as anon:
        asyncio.run(call(None))
    assert anon.value.status_code == 401
    assert anon.value.detail["code"] == "login_required"
    with pytest.raises(HTTPException) as member:
        asyncio.run(call(SimpleNamespace(id=4, role="member")))
    assert member.value.status_code == 403
    assert member.value.detail["code"] == "subscription_required"
    assert posts == [] and device_path == []


def test_macro_rate_limit_and_limits_stay_on_the_old_contract():
    request = Request({"type": "http", "client": ("203.0.113.8", 1), "headers": []})
    from app.ai import rate_limit
    rate_limit.set_rate_store(rate_limit.MemoryRateStore())
    original = settings.ai_rate_limit_per_minute
    settings.ai_rate_limit_per_minute = 1
    try:
        check_ai_rate_limit(request)
        with pytest.raises(HTTPException) as denied:
            check_ai_rate_limit(request)
    finally:
        settings.ai_rate_limit_per_minute = original
        rate_limit.set_rate_store(rate_limit.MemoryRateStore())
    assert isinstance(denied.value.detail, str)
    assert "분당" in denied.value.detail
    assert quota.LIMITS["bundle"]["photo_analysis_image"] == 500
    assert quota.LIMITS["macro"] == {"macro_question": 200}
    assert "limit" in quota.reserve.__code__.co_varnames
