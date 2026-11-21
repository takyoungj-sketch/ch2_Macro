"""FN-011: OAuth app return is an HTML bridge, web login stays a 307."""

import ast
import html
import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from app.config import settings
from app.platform import auth_router, jwt_util
from app.platform.db import get_platform_db

BASE = "c9ce6f720d1f764c4892a4a196fe45ef845d5286"
_CUSTOM_HREF = re.compile(r'href="(ch2fieldnote://oauth-callback\?[^"]*)"')
_INTENT_HREF = re.compile(r'href="(intent://oauth-callback\?[^"]*)"')


def html_from_response(response) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    body = response.body
    if isinstance(body, bytes):
        return body.decode("utf-8")
    return str(body)


def token_from_bridge_html(body: str) -> str:
    match = _CUSTOM_HREF.search(body)
    if match is None:
        raise AssertionError("bridge link missing")
    href = html.unescape(match.group(1))
    token = parse_qs(urlsplit(href).query).get("token") or []
    if not token or not token[-1]:
        raise AssertionError("bridge token missing")
    return token[-1]


def custom_href(body: str) -> str:
    match = _CUSTOM_HREF.search(body)
    if match is None:
        raise AssertionError("bridge link missing")
    return html.unescape(match.group(1))


def intent_href(body: str) -> str:
    match = _INTENT_HREF.search(body)
    if match is None:
        raise AssertionError("intent link missing")
    return html.unescape(match.group(1))


@pytest.fixture(autouse=True)
def config(monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "fn011-unit-test-only-signing-key")
    monkeypatch.setattr(settings, "access_token_expire_minutes", 83)
    monkeypatch.setattr(settings, "fieldnote_app_token_expire_days", 7)
    monkeypatch.setattr(settings, "platform_cookie_domain", ".example.test")
    monkeypatch.setattr(settings, "platform_cookie_secure", True)
    monkeypatch.setattr(settings, "google_client_id", "test-client")
    monkeypatch.setattr(settings, "google_client_secret", "test-secret")
    monkeypatch.setattr(settings, "kakao_client_id", "test-client")
    monkeypatch.setattr(settings, "kakao_client_secret", "test-secret")


class OAuthDB:
    def __init__(self, role):
        self.role = role

    def execute(self, sql, params):
        assert "SELECT id, nickname, role FROM users" in str(sql)
        return SimpleNamespace(mappings=lambda: SimpleNamespace(first=lambda: {
            "id": 42, "nickname": "unit", "role": self.role}))


class OAuthClient:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def post(self, url, **kwargs):
        return httpx.Response(200, json={"access_token": "provider-access"})

    def get(self, url, **kwargs):
        return httpx.Response(200, json={
            "sub": "42", "id": 42, "email": "unit@example.test",
            "kakao_account": {"email": "unit@example.test"},
        })


def baseline_finish():
    root = Path(__file__).resolve().parents[2]
    source = subprocess.check_output(
        ["git", "show", f"{BASE}:backend/app/platform/auth_router.py"], cwd=root
    ).decode("utf-8")
    node = next(
        item for item in ast.parse(source).body
        if isinstance(item, ast.FunctionDef) and item.name == "_finish_web_or_app_login"
    )
    namespace = dict(vars(auth_router))
    exec(compile(ast.Module(body=[node], type_ignores=[]), "baseline-auth", "exec"), namespace)
    return namespace["_finish_web_or_app_login"]


def finish_args(**overrides):
    args = dict(user_id=42, email="unit@example.test", nickname="unit", role="user", state="/board/")
    args.update(overrides)
    return args


@pytest.mark.parametrize("state", ["/board/", ""])
def test_web_headers_match_main(monkeypatch, state):
    fixed = datetime(2030, 1, 2, 3, 4, tzinfo=timezone.utc)

    class Clock:
        @staticmethod
        def now(tz):
            return fixed

    monkeypatch.setattr(jwt_util, "datetime", Clock)
    args = finish_args(state=state)
    before = baseline_finish()(**args)
    after = auth_router._finish_web_or_app_login(**args)
    assert after.status_code == before.status_code == 307
    assert dict(after.headers) == dict(before.headers)


@pytest.mark.parametrize("provider", ["google", "kakao"])
@pytest.mark.parametrize("state", ["/board/", ""])
def test_web_callback_keeps_cookie_redirect(monkeypatch, provider, state):
    fixed = datetime(2030, 1, 2, 3, 4, tzinfo=timezone.utc)

    class Clock:
        @staticmethod
        def now(tz):
            return fixed

    monkeypatch.setattr(jwt_util, "datetime", Clock)
    monkeypatch.setattr(auth_router.httpx, "Client", lambda **kwargs: OAuthClient())
    callback = getattr(auth_router, f"{provider}_callback")
    response = callback(code="unit-code", db=OAuthDB("user"), state=state)
    before = baseline_finish()(**finish_args(state=state or "/"))
    assert response.status_code == 307
    assert dict(response.headers) == dict(before.headers)


@pytest.mark.parametrize("provider", ["google", "kakao"])
@pytest.mark.parametrize("role,minutes", [("user", 7 * 24 * 60), ("admin", 83)])
def test_app_callback_is_bridge(monkeypatch, provider, role, minutes):
    monkeypatch.setattr(auth_router.httpx, "Client", lambda **kwargs: OAuthClient())
    callback = getattr(auth_router, f"{provider}_callback")
    response = callback(
        code="unit-code",
        db=OAuthDB(role),
        state="app:ch2fieldnote://oauth-callback?n=Abcdefghij123456_-Wxyz",
    )
    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    assert response.headers["content-type"].startswith("text/html")
    token = token_from_bridge_html(html_from_response(response))
    claims = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    assert claims["role"] == role
    delta = claims["exp"] - datetime.now(timezone.utc).timestamp()
    assert minutes * 60 - 3 <= delta <= minutes * 60 + 1


def test_android_and_other_links():
    android = auth_router._finish_web_or_app_login(
        **finish_args(
            state="app:ch2fieldnote://oauth-callback?n=Abcdefghij123456_-Wxyz&x=1",
            user_agent="Mozilla/5.0 (Linux; Android 14) AppleWebKit SamsungBrowser/26.0",
        )
    )
    other = auth_router._finish_web_or_app_login(
        **finish_args(
            state="app:ch2fieldnote://oauth-callback?n=Abcdefghij123456_-Wxyz&x=1",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        )
    )
    assert android.status_code == other.status_code == 200
    android_custom = custom_href(html_from_response(android))
    other_custom = custom_href(html_from_response(other))
    android_intent = intent_href(html_from_response(android))
    assert "x=" not in android_custom and "x=" not in android_intent
    assert android_custom.startswith("ch2fieldnote://oauth-callback?n=Abcdefghij123456_-Wxyz&token=")
    assert android_intent.startswith(
        "intent://oauth-callback?n=Abcdefghij123456_-Wxyz&token="
    )
    assert android_intent.endswith("#Intent;scheme=ch2fieldnote;package=com.ch2data.fieldnote;end")
    assert "browser_fallback_url" not in html_from_response(android)
    assert other_custom.startswith("ch2fieldnote://oauth-callback?n=Abcdefghij123456_-Wxyz&token=")
    assert "intent://" not in html_from_response(other)
    assert parse_qs(urlsplit(android_custom).query)["n"] == ["Abcdefghij123456_-Wxyz"]
    assert parse_qs(urlsplit(android_intent).query)["token"] == parse_qs(urlsplit(android_custom).query)["token"]


def test_user_agent_header_selects_android_link(monkeypatch):
    monkeypatch.setattr(auth_router.httpx, "Client", lambda **kwargs: OAuthClient())
    app = FastAPI()
    app.include_router(auth_router.router, prefix="/api")
    app.dependency_overrides[get_platform_db] = lambda: OAuthDB("user")
    response = TestClient(app).get(
        "/api/auth/google/callback",
        params={"code": "unit-code", "state": "app:ch2fieldnote://oauth-callback?n=Abcdefghij123456_-Wxyz"},
        headers={"User-Agent": "Mozilla/5.0 (Linux; Android 14) SamsungBrowser/26.0"},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert intent_href(html_from_response(response)).endswith("#Intent;scheme=ch2fieldnote;package=com.ch2data.fieldnote;end")


@pytest.mark.parametrize("state", [
    "app:ch2fieldnote://other",
    "app:ch2fieldnote://oauth-callback/",
    "app:CH2FIELDNOTE://oauth-callback",
    "app:ch2fieldnote://OAuth-Callback?n=Abcdefghij123456_-Wxyz",
])
def test_rejected_app_target_creates_no_token(monkeypatch, state):
    def banned(**kwargs):
        raise AssertionError("token created")

    monkeypatch.setattr(auth_router, "create_access_token", banned)
    response = auth_router._finish_web_or_app_login(**finish_args(state=state))
    assert response.status_code == 400
    assert "set-cookie" not in response.headers
    assert html_from_response(response).count("로그인을 완료하지 못했습니다.") == 1
    assert "ch2fieldnote" not in html_from_response(response)
    assert state not in html_from_response(response)


def test_extra_query_key_is_dropped_and_token_is_issued():
    response = auth_router._finish_web_or_app_login(
        **finish_args(state="app:ch2fieldnote://oauth-callback?n=Abcdefghij123456_-Wxyz&x=1")
    )
    href = custom_href(html_from_response(response))
    query = parse_qs(urlsplit(href).query)
    assert list(query) == ["n", "token"]
    assert query["n"] == ["Abcdefghij123456_-Wxyz"]
    assert query["token"][0]


def test_query_escapes_markup_and_line_separators(monkeypatch):
    def banned(**kwargs):
        raise AssertionError("token created")

    monkeypatch.setattr(auth_router, "create_access_token", banned)
    raw = "\"<'" + "</script>" + "\u2028"
    response = auth_router._finish_web_or_app_login(
        **finish_args(state="app:ch2fieldnote://oauth-callback?n=" + raw)
    )
    body = html_from_response(response)
    assert response.status_code == 400
    assert "set-cookie" not in response.headers
    assert "</script>" not in body
    assert "\u2028" not in body
    assert raw not in body
    assert "token=" not in body


def test_bridge_headers_and_no_external_url():
    response = auth_router._finish_web_or_app_login(
        **finish_args(state="app:ch2fieldnote://oauth-callback?n=Abcdefghij123456_-Wxyz")
    )
    headers = response.headers
    assert headers["cache-control"] == "no-store"
    assert headers["pragma"] == "no-cache"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["x-content-type-options"] == "nosniff"
    policy = headers["content-security-policy"]
    assert policy.startswith("default-src 'none'; script-src 'nonce-")
    assert "style-src 'unsafe-inline'" in policy
    assert "base-uri 'none'" in policy
    assert "form-action 'none'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "set-cookie" not in headers
    assert "location" not in headers
    nonce = policy.split("nonce-", 1)[1].split("'", 1)[0]
    assert f'nonce="{nonce}"' in html_from_response(response)
    assert "http://" not in html_from_response(response) and "https://" not in html_from_response(response)


def test_bridge_log_omits_token():
    records = []

    class Grab(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    handler = Grab()
    auth_router._log.addHandler(handler)
    try:
        response = auth_router._finish_web_or_app_login(
            **finish_args(state="app:ch2fieldnote://oauth-callback?n=Abcdefghij123456_-Wxyz")
        )
    finally:
        auth_router._log.removeHandler(handler)
    token = token_from_bridge_html(html_from_response(response))
    assert records == [] or all(token not in message for message in records)


N22 = "Abcdefghij123456_-Wxyz"
BAD_APP_STATES = [
    "app:CH2FIELDNOTE://oauth-callback",
    "app:ch2fieldnote:oauth-callback",
    "APP:ch2fieldnote://oauth-callback",
    "app:ch2fieldnote://other",
    "app:https://evil",
]
BAD_NONCE_QUERIES = [
    "",
    "?n=" + ("a" * 15),
    "?n=" + ("a" * 129),
    "?n=" + ("a" * 10) + " " + ("b" * 10),
    "?n=" + ("a" * 10) + "\n" + ("b" * 10),
    "?n=" + ("a" * 10) + "%" + ("b" * 10),
    f"?n={N22}&n={N22}",
]


def _route_app() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router.router, prefix="/api")
    app.dependency_overrides[get_platform_db] = lambda: OAuthDB("user")
    return TestClient(app)


@pytest.mark.parametrize("provider", ["google", "kakao"])
@pytest.mark.parametrize("state", BAD_APP_STATES)
def test_bad_app_login_is_not_web(monkeypatch, provider, state):
    def banned(**kwargs):
        raise AssertionError("token created")

    monkeypatch.setattr(auth_router, "create_access_token", banned)
    response = _route_app().get(
        f"/api/auth/{provider}/login",
        params={"state": state},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "set-cookie" not in response.headers
    assert "location" not in response.headers
    assert response.text.count("로그인을 완료하지 못했습니다.") == 1
    assert state not in response.text


@pytest.mark.parametrize("provider", ["google", "kakao"])
@pytest.mark.parametrize("state", BAD_APP_STATES)
def test_bad_app_callback_is_not_web(monkeypatch, provider, state):
    def banned(**kwargs):
        raise AssertionError("token created")

    monkeypatch.setattr(auth_router, "create_access_token", banned)

    class Boom:
        def __init__(self, **kwargs):
            raise AssertionError("provider called")

    monkeypatch.setattr(auth_router.httpx, "Client", Boom)
    response = _route_app().get(
        f"/api/auth/{provider}/callback",
        params={"code": "unit-code", "state": state},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "set-cookie" not in response.headers
    assert "location" not in response.headers
    assert response.text.count("로그인을 완료하지 못했습니다.") == 1


@pytest.mark.parametrize("provider", ["google", "kakao"])
@pytest.mark.parametrize("kind", ["login", "callback"])
@pytest.mark.parametrize("query", BAD_NONCE_QUERIES)
def test_bad_nonce_is_rejected_before_token(monkeypatch, provider, kind, query):
    def banned(**kwargs):
        raise AssertionError("token created")

    monkeypatch.setattr(auth_router, "create_access_token", banned)
    state = "app:ch2fieldnote://oauth-callback" + query
    params = {"state": state}
    if kind == "callback":
        params["code"] = "unit-code"
    response = _route_app().get(
        f"/api/auth/{provider}/{kind}",
        params=params,
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "set-cookie" not in response.headers
    assert "location" not in response.headers


@pytest.mark.parametrize("provider", ["google", "kakao"])
@pytest.mark.parametrize("state", ["/", "/board/"])
def test_web_login_state_unchanged(provider, state):
    response = _route_app().get(
        f"/api/auth/{provider}/login",
        params={"state": state},
        follow_redirects=False,
    )
    assert response.status_code == 307
    assert parse_qs(urlsplit(response.headers["location"]).query)["state"] == [state]
    assert "set-cookie" not in response.headers


def test_valid_nonce_login_keeps_app_state():
    state = f"app:ch2fieldnote://oauth-callback?n={N22}"
    response = _route_app().get(
        "/api/auth/google/login",
        params={"state": state},
        follow_redirects=False,
    )
    assert response.status_code == 307
    assert parse_qs(urlsplit(response.headers["location"]).query)["state"] == [state]
    assert "set-cookie" not in response.headers


def test_google_login_log_omits_nonce(caplog):
    state = f"app:ch2fieldnote://oauth-callback?n={N22}"
    with caplog.at_level(logging.INFO, logger="app.platform.auth_router"):
        response = _route_app().get(
            "/api/auth/google/login",
            params={"state": state},
            follow_redirects=False,
        )
    assert response.status_code == 307
    assert N22 not in caplog.text
    assert "state=<redacted>" in caplog.text
    assert "test-client" in caplog.text
    assert N22 in response.headers["location"]
