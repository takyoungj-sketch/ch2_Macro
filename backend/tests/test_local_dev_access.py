import pytest
import asyncio
from starlette.requests import Request

from app.config import settings
from app.local_dev_access import local_dev_access_enabled


def request(host="localhost:8000", client="127.0.0.1", scheme="http", extra=()):
    return Request({"type": "http", "method": "GET", "path": "/api/built/regions/addr2", "scheme": scheme,
                    "server": ("127.0.0.1", 8000), "client": (client, 1234), "query_string": b"",
                    "headers": [(b"host", host.encode()), *extra]})


@pytest.mark.parametrize("enabled,token,allowed", [(False, "", False), (True, "", True), (True, "production-token", False)])
def test_local_access_requires_opt_in_and_no_production_token(monkeypatch, enabled, token, allowed):
    monkeypatch.setattr(settings, "local_dev_access", enabled)
    monkeypatch.setattr(settings, "api_token", token)
    assert local_dev_access_enabled(request()) is allowed


@pytest.mark.parametrize("kwargs", [
    {"host": "macro.example.com"}, {"client": "192.168.0.2"}, {"scheme": "https"},
    {"extra": [(b"x-forwarded-for", b"127.0.0.1")]},
    {"extra": [(b"origin", b"https://macro.example.com")]},
    {"extra": [(b"origin", b"null")]},
])
def test_nonlocal_and_proxied_requests_remain_restricted(monkeypatch, kwargs):
    monkeypatch.setattr(settings, "local_dev_access", True)
    monkeypatch.setattr(settings, "api_token", "")
    assert not local_dev_access_enabled(request(**kwargs))


@pytest.mark.parametrize("kwargs,enabled,token,allowed", [
    ({}, True, "", True),
    ({}, False, "", False),
    ({}, True, "production-token", False),
    ({"host": "macro.example.com"}, True, "", False),
    ({"client": "192.168.0.2"}, True, "", False),
    ({"extra": [(b"x-forwarded-for", b"127.0.0.1")]}, True, "", False),
])
def test_product_gate_honors_only_local_development_access(monkeypatch, kwargs, enabled, token, allowed):
    from app import product_gate

    monkeypatch.setattr(settings, "local_dev_access", enabled)
    monkeypatch.setattr(settings, "api_token", token)
    monkeypatch.setattr(product_gate, "caller_access", lambda _: "anonymous")
    response = asyncio.run(product_gate.product_gate_response(request(**kwargs)))
    if allowed:
        assert response is None
    else:
        assert response.status_code == 401
