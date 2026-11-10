"""QA 이력 요청은 앱 계정으로 SELECT만 실행한다."""

from contextlib import nullcontext
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.qa_audit import router as qa_router


@pytest.mark.parametrize("domain", ["collective_apt", "built_enriched"])
def test_get_runs_selects_history_without_schema_changes(monkeypatch, domain):
    conn = Mock(spec=["execute"])
    conn.execute.return_value.mappings.return_value.all.return_value = [{"id": 42, "domain": domain}]
    engine = Mock(spec=["connect"])
    engine.connect.return_value = nullcontext(conn)
    resolve = Mock(return_value=(engine, domain))
    monkeypatch.setattr(qa_router, "_engine_for", resolve)
    monkeypatch.setattr(qa_router.settings, "qa_audit_token", "test-qa-token")
    app = FastAPI()
    app.include_router(qa_router.router, prefix="/api")

    with TestClient(app) as client:
        response = client.get(
            "/api/admin/qa/runs",
            params={"domain": domain, "limit": 200},
            headers={"X-Qa-Audit-Token": "test-qa-token"},
        )

    assert response.status_code == 200
    assert response.json() == {"items": [{"id": 42, "domain": domain}]}
    resolve.assert_called_once_with(domain)
    engine.connect.assert_called_once_with()
    conn.execute.assert_called_once()
    statement, params = conn.execute.call_args.args
    assert str(statement).strip().startswith("SELECT ")
    assert "FROM public.qa_audit_run" in str(statement)
    assert params == {"lim": 50, "domain": domain}


def test_get_runs_hides_database_error(monkeypatch):
    engine = Mock(spec=["connect"])
    engine.connect.side_effect = OperationalError(None, None, RuntimeError("private DB details"))
    monkeypatch.setattr(qa_router, "_engine_for", lambda _: (engine, "collective_apt"))
    monkeypatch.setattr(qa_router.settings, "qa_audit_token", "test-qa-token")
    app = FastAPI()
    app.include_router(qa_router.router, prefix="/api")

    with TestClient(app) as client:
        response = client.get("/api/admin/qa/runs", headers={"X-Qa-Audit-Token": "test-qa-token"})

    assert response.status_code == 503
    assert "private DB details" not in response.text
