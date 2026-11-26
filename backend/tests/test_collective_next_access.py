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


def test_viewport_lines_are_closed_without_access(monkeypatch):
    from app.main import app

    monkeypatch.setattr(settings, "api_token", "")
    monkeypatch.setattr("app.collective2.access.collective_next_allowed", lambda _request: False)
    client = TestClient(app)
    denied = client.post(
        "/api/collective/commercial/roads/viewport-lines",
        json={"cluster_keys": ["abc"], "bounds": [127.0, 37.4, 127.05, 37.45]},
    )
    assert denied.status_code == 403


def test_viewport_lines_query_only_shop_and_factory(monkeypatch):
    from app.collective_commercial.router import roads_in_viewport
    from app.collective_commercial.schemas import CommercialViewportRoadRequest

    stored = [
        {"cluster_key": "shop-key", "road_name": "시험로", "emd": "1168010100", "sigungu": "11680", "asset_type": "collective_shop"},
        {"cluster_key": "factory-key", "road_name": "시험로", "emd": "1168010100", "sigungu": "11680", "asset_type": "collective_factory"},
        {"cluster_key": "apt-key", "road_name": "시험로", "emd": "1168010100", "sigungu": "11680", "asset_type": "apartment"},
    ]
    passed: dict[str, list] = {}

    class Rows:
        def __init__(self, rows):
            self._rows = rows

        def mappings(self):
            return self

        def all(self):
            return self._rows

    class FakeDB:
        def execute(self, sql, params=None):
            text = str(sql)
            rows = list(stored)
            if "asset_type IN" in text:
                allowed = [name for name in ("collective_shop", "collective_factory", "apartment") if name in text]
                rows = [row for row in rows if row["asset_type"] in allowed]
            keys = set((params or {}).get("keys") or [])
            if keys:
                rows = [row for row in rows if row["cluster_key"] in keys]
            return Rows(rows)

    def fake_lines(*, api_key, domain, bounds, rows):
        passed["rows"] = list(rows)
        return {
            "lines": [
                {"cluster_key": row["cluster_key"], "geometry": {"type": "FeatureCollection", "features": []}, "label_point": None}
                for row in rows
            ],
            "truncated": False,
            "unavailable": 0,
        }

    monkeypatch.setattr(settings, "vworld_api_key", "test-key")
    monkeypatch.setattr("app.collective_commercial.router.fetch_viewport_road_lines", fake_lines)
    body = CommercialViewportRoadRequest(
        cluster_keys=["shop-key", "factory-key", "apt-key"],
        bounds=(127.0, 37.4, 127.05, 37.45),
    )
    result = roads_in_viewport(body, FakeDB())
    kinds = {row["asset_type"] for row in passed["rows"]}
    assert kinds == {"collective_shop", "collective_factory"}
    assert {line["cluster_key"] for line in result["lines"]} == {"shop-key", "factory-key"}


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
