"""집합 2단계 — 옛 단지 키 요청 처리 미들웨어 (DB 없이 연결표 주입)."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.collective.key_remap import KeyMapCache, KeyRemapMiddleware

OLD1 = "a" * 64   # 1:1 (호남)
NEW1 = "b" * 64
OLDS = "c" * 64   # 1:N (분할)
P1, P2 = "d" * 64, "e" * 64
OTHER = "f" * 64


def _app(maps: dict, details=None):
    app = FastAPI()

    @app.get("/api/collective/buildings/{key}/stats/rolling")
    def rolling(key: str, request: Request):
        return {"key": key, "q": dict(request.query_params)}

    @app.get("/api/collective/analysis/hedonic/buildings/{key}/quality")
    def quality(key: str):
        return {"key": key}

    @app.get("/api/rent/buildings/{key}/rolling")
    def rent(key: str):
        return {"key": key}

    @app.get("/api/collective/buildings")
    def lst(request: Request):
        return {"q": dict(request.query_params)}

    @app.get("/api/free/v2/stats/{code}")
    def land(code: str):
        return {"code": code}

    cache = KeyMapCache(loader=lambda name: maps.get(name, {}), ttl=0)
    app.add_middleware(KeyRemapMiddleware, cache=cache, details=details or (lambda a, ks: {}))
    return TestClient(app)


MAPS = {
    "collective": {OLD1: [(NEW1, 0, 10)], OLDS: [(P1, 1, 7), (P2, 2, 3)]},
    "rent": {OLDS: [(P1, 1, 2), (P2, 2, 1)], OLD1: [(NEW1, 0, 1)]},
}


def test_one_to_one_path_is_remapped_with_header():
    c = _app(MAPS)
    r = c.get(f"/api/collective/buildings/{OLD1}/stats/rolling?window_years=5")
    assert r.status_code == 200
    assert r.json() == {"key": NEW1, "q": {"window_years": "5"}}
    assert r.headers["x-ch2-key-remapped"] == f"{OLD1}->{NEW1}"
    assert c.get(f"/api/collective/analysis/hedonic/buildings/{OLD1}/quality").json() == {"key": NEW1}
    assert c.get(f"/api/rent/buildings/{OLD1}/rolling").json() == {"key": NEW1}


def test_split_returns_409_with_candidates():
    det = lambda app, keys: {P1: {"display_name": "삼일", "addr4": "우암동"}}  # noqa: E731
    c = _app(MAPS, details=det)
    r = c.get(f"/api/collective/buildings/{OLDS}/stats/rolling")
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["key_status"] == "split" and d["old_key"] == OLDS
    assert [x["building_key"] for x in d["candidates"]] == [P1, P2]
    assert d["candidates"][0]["addr4"] == "우암동" and d["candidates"][1]["n_tx"] == 3
    assert c.get(f"/api/rent/buildings/{OLDS}/rolling").status_code == 409


def test_query_building_key_remap_and_split():
    c = _app(MAPS)
    r = c.get(f"/api/collective/buildings?building_key={OLD1}&page=2")
    assert r.json()["q"] == {"building_key": NEW1, "page": "2"}
    assert c.get(f"/api/collective/buildings?building_key={OLDS}").status_code == 409


def test_passthrough_unknown_key_other_apps_and_disabled(monkeypatch):
    c = _app(MAPS)
    assert c.get(f"/api/collective/buildings/{OTHER}/stats/rolling").json()["key"] == OTHER
    assert "x-ch2-key-remapped" not in c.get(f"/api/collective/buildings/{OTHER}/stats/rolling").headers
    assert c.get("/api/free/v2/stats/4311425036").json() == {"code": "4311425036"}
    c2 = _app({})  # 연결표 없음(이전 전)
    assert c2.get(f"/api/collective/buildings/{OLD1}/stats/rolling").json()["key"] == OLD1
    monkeypatch.setenv("CH2_KEY_REMAP_ENABLED", "0")
    assert c.get(f"/api/collective/buildings/{OLD1}/stats/rolling").json()["key"] == OLD1


def test_loader_failure_does_not_block():
    def boom(_name):
        raise RuntimeError("db down")

    app = FastAPI()

    @app.get("/api/collective/buildings/{key}/stats/rolling")
    def rolling(key: str):
        return {"key": key}

    app.add_middleware(KeyRemapMiddleware, cache=KeyMapCache(loader=boom, ttl=0))
    assert TestClient(app).get(f"/api/collective/buildings/{OLD1}/stats/rolling").json()["key"] == OLD1


def test_main_app_registers_middleware_and_key_status_route():
    from app.main import app

    assert any(m.cls is KeyRemapMiddleware for m in app.user_middleware)
    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/collective/buildings/{building_key}/key-status" in paths
