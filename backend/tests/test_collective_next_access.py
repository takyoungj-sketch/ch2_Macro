"""집합2 접근은 화면용 API에서 서버가 거절한다."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.collective2.access import collective_next_allowed
from app.config import settings


def test_admin_is_allowed(monkeypatch):
    monkeypatch.setattr("app.collective2.access.is_admin", lambda _request: True)
    assert collective_next_allowed(MagicMock()) is True


def test_other_account_is_denied(monkeypatch):
    monkeypatch.delenv("COLLECTIVE_NEXT_ALLOW", raising=False)
    monkeypatch.setattr("app.collective2.access.is_admin", lambda _request: False)
    monkeypatch.setattr("app.collective2.access.caller_user_id", lambda _request: "15")
    assert collective_next_allowed(MagicMock()) is False


def test_allowlist_account_is_allowed(monkeypatch):
    monkeypatch.setenv("COLLECTIVE_NEXT_ALLOW", "15, 20")
    monkeypatch.setattr("app.collective2.access.is_admin", lambda _request: False)
    monkeypatch.setattr("app.collective2.access.caller_user_id", lambda _request: "15")
    assert collective_next_allowed(MagicMock()) is True


def test_off_blocks_admin(monkeypatch):
    monkeypatch.setenv("FEATURE_COLLECTIVE_NEXT", "off")
    monkeypatch.setattr("app.collective2.access.is_admin", lambda _request: True)
    assert collective_next_allowed(MagicMock()) is False


def test_access_route_is_403_then_200(monkeypatch):
    from app.main import app

    monkeypatch.setattr(settings, "api_token", "")
    client = TestClient(app)
    monkeypatch.setattr("app.collective2.access.collective_next_allowed", lambda _request: False)
    denied = client.get("/api/collective2/access")
    assert denied.status_code == 403
    monkeypatch.setattr("app.collective2.access.collective_next_allowed", lambda _request: True)
    allowed = client.get("/api/collective2/access")
    assert allowed.status_code == 200
    assert allowed.json() == {"ok": True}
