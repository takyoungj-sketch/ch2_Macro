"""FN-008: OAuth role authority, web compatibility, public app config."""

import ast
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from app.config import Settings, settings
from app.platform import auth_router, fieldnote_app_router, jwt_util
from app.platform.db import get_platform_db
from tests.test_fn011_app_bridge import html_from_response, token_from_bridge_html

BASE = "e264476a977520e4ee82b91466cc2a0fc9589fe2"


@pytest.fixture(autouse=True)
def config(monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "fn008-unit-test-only-signing-key")
    monkeypatch.setattr(settings, "access_token_expire_minutes", 83)
    monkeypatch.setattr(settings, "fieldnote_app_token_expire_days", 7)
    monkeypatch.setattr(settings, "platform_cookie_domain", ".example.test")
    monkeypatch.setattr(settings, "platform_cookie_secure", True)


def payload(response):
    if response.status_code == 200:
        token = token_from_bridge_html(html_from_response(response))
    elif response.headers.get("location", "").startswith("ch2fieldnote://"):
        token = parse_qs(urlsplit(response.headers["location"]).query)["token"][-1]
    else:
        from http.cookies import SimpleCookie
        cookie = SimpleCookie()
        cookie.load(response.headers["set-cookie"])
        token = cookie[jwt_util.COOKIE_NAME].value
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def assert_lifetime(response, minutes):
    delta = payload(response)["exp"] - datetime.now(timezone.utc).timestamp()
    assert minutes * 60 - 3 <= delta <= minutes * 60 + 1


@pytest.mark.parametrize("role,minutes", [("user", 7 * 24 * 60), ("admin", 83)])
def test_app_lifetime_by_role(role, minutes):
    result = auth_router._finish_web_or_app_login(
        user_id=42, email="unit@example.test", nickname="unit", role=role,
        state="app:ch2fieldnote://oauth-callback")
    assert_lifetime(result, minutes)
    assert "set-cookie" not in result.headers


def test_app_lifetime_setting(monkeypatch):
    monkeypatch.setattr(settings, "fieldnote_app_token_expire_days", 2)
    result = auth_router._finish_web_or_app_login(
        user_id=42, email="unit@example.test", nickname="unit", role="user",
        state="app:ch2fieldnote://oauth-callback")
    assert_lifetime(result, 2 * 24 * 60)


def baseline_function(name):
    root = Path(__file__).resolve().parents[2]
    source = subprocess.check_output(
        ["git", "show", f"{BASE}:backend/app/platform/auth_router.py"], cwd=root
    ).decode("utf-8")
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = dict(vars(auth_router))
    exec(compile(ast.Module(body=[node], type_ignores=[]), "baseline-auth", "exec"), namespace)
    return namespace[name]


@pytest.mark.parametrize("role", ["user", "admin"])
@pytest.mark.parametrize("state", ["/board/", ""])
def test_web_token_and_cookie_match_baseline(monkeypatch, role, state):
    # Fix time so the signed JWT and complete Set-Cookie can be compared exactly.
    fixed = datetime(2030, 1, 2, 3, 4, tzinfo=timezone.utc)
    class Clock:
        @staticmethod
        def now(tz): return fixed
    monkeypatch.setattr(jwt_util, "datetime", Clock)
    args = dict(user_id=42, email="unit@example.test", nickname="unit", role=role, state=state)
    before = baseline_function("_finish_web_or_app_login")(**args)
    after = auth_router._finish_web_or_app_login(**args)
    assert dict(after.headers) == dict(before.headers)
    assert after.status_code == before.status_code == 307
    claims = jwt.get_unverified_claims(after.headers["set-cookie"].split('ch2_session=')[1].split(';')[0])
    assert claims["exp"] == int(fixed.timestamp()) + 83 * 60
    assert "HttpOnly" in after.headers["set-cookie"]
    assert "Max-Age=4980" in after.headers["set-cookie"]


class OAuthDB:
    def __init__(self, role): self.role = role
    def execute(self, sql, params):
        assert "SELECT id, nickname, role FROM users" in str(sql)
        assert params["p"] in {"google", "kakao"}
        return SimpleNamespace(mappings=lambda: SimpleNamespace(first=lambda: {
            "id": 42, "nickname": "unit", "role": self.role}))


@pytest.mark.parametrize("provider", ["google", "kakao"])
@pytest.mark.parametrize("db_role", ["user", "admin"])
@pytest.mark.parametrize("injected_role", ["user", "admin"])
def test_callback_role_comes_from_database(monkeypatch, provider, db_role, injected_role):
    monkeypatch.setattr(settings, "google_client_id", "test-client")
    monkeypatch.setattr(settings, "google_client_secret", "test-secret")
    monkeypatch.setattr(settings, "kakao_client_id", "test-client")
    monkeypatch.setattr(settings, "kakao_client_secret", "test-secret")
    class OAuthClient:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs):
            return httpx.Response(200, json={"access_token": "test-oauth-access"})
        def get(self, url, **kwargs):
            # Even a provider profile role cannot override the users row.
            return httpx.Response(200, json={"sub": "42", "id": 42, "email": "unit@example.test",
                "role": injected_role, "kakao_account": {"email": "unit@example.test"}})
    monkeypatch.setattr(auth_router.httpx, "Client", lambda **kwargs: OAuthClient())
    app = FastAPI()
    app.include_router(auth_router.router, prefix="/api")
    app.dependency_overrides[get_platform_db] = lambda: OAuthDB(db_role)
    # Exercise the actual callback and users-row lookup without a thread/event loop.
    # Extra role/lifetime query values cannot be bound by these callback routes.
    route = next(r for r in app.routes if r.path == f"/api/auth/{provider}/callback")
    assert not {"role", "expire_minutes"} & {p.name for p in route.dependant.query_params}
    callback = getattr(auth_router, f"{provider}_callback")
    response = callback(code="unit-code", db=OAuthDB(db_role),
        state=f"app:ch2fieldnote://oauth-callback?role={injected_role}")
    assert response.status_code == 200
    assert payload(response)["role"] == db_role
    assert_lifetime(response, 83 if db_role == "admin" else 7 * 24 * 60)


@pytest.mark.parametrize("provider", ["google", "kakao"])
@pytest.mark.parametrize("state", ["app:https://evil.example", "app:other://oauth-callback", "https://evil.example", "//evil.example"])
def test_login_keeps_redirect_rejection(monkeypatch, provider, state):
    monkeypatch.setattr(settings, "google_client_id", "test-client")
    monkeypatch.setattr(settings, "kakao_client_id", "test-client")
    monkeypatch.setattr(settings, "kakao_client_secret", "test-secret")
    app = FastAPI()
    app.include_router(auth_router.router, prefix="/api")
    result = TestClient(app).get(f"/api/auth/{provider}/login", params={"state":state}, follow_redirects=False)
    assert result.status_code == 307
    assert parse_qs(urlsplit(result.headers["location"]).query)["state"] == ["/"]


def test_auth_response_functions_unchanged(monkeypatch):
    user = SimpleNamespace(id=42, nickname="unit", role="user")
    monkeypatch.setattr(auth_router, "resolve_access", lambda db, u: SimpleNamespace(products={"macro":True,"fieldnote":True}))
    assert auth_router.auth_me(user) == baseline_function("auth_me")(user)
    assert auth_router.auth_entitlements(user, object()) == baseline_function("auth_entitlements")(user, object())


def test_app_config_defaults(monkeypatch):
    defaults = {"fieldnote_app_min_version_code":0, "fieldnote_app_latest_version_code":0,
        "fieldnote_app_update_message":"", "fieldnote_app_blocked_features":""}
    for name, value in defaults.items():
        assert Settings.model_fields[name].default == value
        monkeypatch.setattr(settings, name, value)
    assert Settings.model_fields["fieldnote_app_token_expire_days"].default == 7
    app = FastAPI()
    app.include_router(fieldnote_app_router.router, prefix="/api/platform")
    assert TestClient(app).get("/api/platform/fieldnote/app-config").json() == {
        "min_version_code":0, "latest_version_code":0, "message":"", "blocked_features":[]}


@pytest.mark.parametrize("csv,expected", [("",[]), (" ,  , ",[]),
    (" backup_restore, ai ,backup_restore, unknown ",["backup_restore","ai","unknown"])])
def test_app_config_settings_and_parsing(monkeypatch, csv, expected):
    monkeypatch.setenv("FIELDNOTE_APP_MIN_VERSION_CODE", "4")
    monkeypatch.setenv("FIELDNOTE_APP_LATEST_VERSION_CODE", "5")
    monkeypatch.setenv("FIELDNOTE_APP_UPDATE_MESSAGE", "업데이트 안내")
    monkeypatch.setenv("FIELDNOTE_APP_BLOCKED_FEATURES", csv)
    monkeypatch.setenv("FIELDNOTE_APP_TOKEN_EXPIRE_DAYS", "2")
    configured = Settings(_env_file=None)
    assert configured.fieldnote_app_token_expire_days == 2
    monkeypatch.setattr(fieldnote_app_router, "settings", configured)
    app = FastAPI()
    app.include_router(fieldnote_app_router.router, prefix="/api/platform")
    response = TestClient(app).get("/api/platform/fieldnote/app-config")
    assert response.status_code == 200
    assert response.json() == {"min_version_code":4, "latest_version_code":5,
        "message":"업데이트 안내", "blocked_features":expected}


def test_app_config_registered_and_public_with_api_token_guard(monkeypatch):
    import sqlalchemy.engine
    from app.main import app
    def no_database(*args, **kwargs):
        raise AssertionError("Public app-config must not connect to a database")
    monkeypatch.setattr(sqlalchemy.engine.Engine, "connect", no_database)
    monkeypatch.setattr(settings, "api_token", "fn008-test-proxy-token")
    # No lifespan startup is needed for a settings-only request.
    result = TestClient(app).get("/api/platform/fieldnote/app-config")
    assert result.status_code == 200
    assert set(result.json()) == {"min_version_code", "latest_version_code", "message", "blocked_features"}
