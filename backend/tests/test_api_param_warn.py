"""집합 1단계 C-05 — 미지원 파라미터 경고·집계 모드.

요청은 200으로 통과하고, 받지 않는 파라미터 이름만 집계된다. 값은 기록되지 않는다.
"""

from __future__ import annotations

import json
from typing import Optional

import pytest
from fastapi import Depends, FastAPI, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app import api_param_warn as apw


class Inner(BaseModel):
    a: bool = True


class Body(BaseModel):
    x: int = 0
    variables: Inner = Inner()


def _common(page: int = 1):
    return page


def _make_app(agg):
    app = FastAPI()
    app.add_middleware(apw.ApiParamWarnMiddleware, aggregator=agg)

    @app.get("/items/{item_key}/stats")
    def stats(item_key: str, year: Optional[int] = None, tags: list[str] = Query(default=[]), page: int = Depends(_common)):
        return {"ok": True, "year": year}

    @app.post("/items/{item_key}/run")
    def run(item_key: str, body: Body):
        return {"x": body.x}

    return app


@pytest.fixture()
def agg(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "api_param_warn_path", str(tmp_path / "warn.jsonl"))
    monkeypatch.setattr(settings, "api_param_warn_enabled", True)
    return apw.ParamWarnAggregator()


SECRET = "secret-value-9137"


def test_unknown_query_param_passes_and_counts_name_only(agg, tmp_path):
    c = TestClient(_make_app(agg))
    r = c.get(f"/items/abc123/stats?year=2024&contract_date_from={SECRET}&page=2&tags=a&tags=b",
              headers={"X-CH2-Screen": "collective/commercial-detail"})
    assert r.status_code == 200
    snap = agg.snapshot()
    assert snap == {("/items/{item_key}/stats", "GET", "collective/commercial-detail", "query", "contract_date_from"): 1}
    c.get(f"/items/zzz/stats?contract_date_from={SECRET}", headers={"X-CH2-Screen": "collective/commercial-detail"})
    assert agg.snapshot()[("/items/{item_key}/stats", "GET", "collective/commercial-detail", "query", "contract_date_from")] == 2
    agg.flush()
    text = (tmp_path / "warn.jsonl").read_text(encoding="utf-8")
    assert SECRET not in text and "abc123" not in text and "zzz" not in text
    row = json.loads(text.strip().splitlines()[0])
    assert row["param"] == "contract_date_from" and row["count"] == 2
    assert row["route"] == "/items/{item_key}/stats"
    assert set(row) == {"window_start", "window_end", "method", "route", "screen", "location", "param", "count"}


def test_known_params_and_dependency_params_not_counted(agg):
    c = TestClient(_make_app(agg))
    assert c.get("/items/k/stats?year=2024&page=3&tags=x").status_code == 200
    assert agg.snapshot() == {}


def test_unknown_body_keys_including_nested(agg, tmp_path):
    c = TestClient(_make_app(agg))
    r = c.post("/items/k/run", json={"x": 3, "asset_type": SECRET, "variables": {"a": False, "zz": 1}},
               headers={"Referer": f"https://example.test/collective/?q={SECRET}#frag"})
    assert r.status_code == 200 and r.json() == {"x": 3}
    snap = agg.snapshot()
    assert snap == {
        ("/items/{item_key}/run", "POST", "referer:/collective/", "body", "asset_type"): 1,
        ("/items/{item_key}/run", "POST", "referer:/collective/", "body", "variables.zz"): 1,
    }
    agg.flush()
    assert SECRET not in (tmp_path / "warn.jsonl").read_text(encoding="utf-8")


def test_disabled_records_nothing(agg, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "api_param_warn_enabled", False)
    c = TestClient(_make_app(agg))
    assert c.get("/items/k/stats?bogus=1").status_code == 200
    assert agg.snapshot() == {}


def test_main_app_has_middleware_and_no_reject_mode():
    from app.main import app

    assert any(m.cls is apw.ApiParamWarnMiddleware for m in app.user_middleware)
    assert not hasattr(apw, "reject") and "reject" not in apw.ApiParamWarnMiddleware.__dict__


def test_real_route_counts_commercial_date_params(agg, monkeypatch):
    """실제 라우트 템플릿으로 기록되는지 — DB 없이 라우팅만 확인(404/500이어도 경로 템플릿은 기록)."""
    from app.main import app

    monkeypatch.setattr(apw, "AGGREGATOR", agg)
    mw = apw.ApiParamWarnMiddleware(app.router, aggregator=agg)
    scope_route = None
    for r in app.routes:
        if getattr(r, "path", "") == "/api/collective/commercial/clusters/{cluster_key}/addresses":
            scope_route = r
    assert scope_route is not None
    mw._inspect({"route": scope_route, "method": "GET", "headers": [],
                 "query_string": b"contract_date_from=2021-11-01&not_a_param=1"}, None)
    assert agg.snapshot() == {
        ("/api/collective/commercial/clusters/{cluster_key}/addresses", "GET", "", "query", "not_a_param"): 1
    }
