"""임대 무거운 조회 시간 제한(504 → 503 안내)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.rent import query_guard
from app.rent.query_guard import (
    REGRESSION_TIMEOUT_MESSAGE,
    TRANSACTIONS_TIMEOUT_MESSAGE,
    heavy_query,
    heavy_timeout_ms,
)


class _Canceled(Exception):
    pgcode = "57014"


class _Other(Exception):
    pgcode = "42P01"


class _Result:
    def __init__(self, value=None, rows=None):
        self._value = value
        self._rows = rows or []

    def scalar(self):
        return self._value

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class FakeDB:
    """statement_timeout 설정 SQL 은 기록하고, 원장 조회는 지정한 방식으로 응답."""

    def __init__(self, *, heavy_error: Exception | None = None, rows=None, count: int = 0):
        self.heavy_error = heavy_error
        self.rows = rows or []
        self.count = count
        self.settings: list[str] = []
        self.rolled_back = False

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if "current_setting('statement_timeout')" in sql:
            return _Result("0")
        if "set_config('statement_timeout'" in sql:
            self.settings.append(params["v"])
            return _Result("ok")
        if "rent_building_stats" in sql:
            return _Result(rows=[])
        if "SELECT COUNT(*) FROM rent_transactions" in sql and "sha256" not in sql:
            return _Result(0)
        if "sha256" in sql and self.heavy_error is not None:
            raise OperationalError(sql[:40], params, self.heavy_error)
        if "COUNT(*)" in sql:
            return _Result(self.count)
        return _Result(rows=self.rows)

    def rollback(self):
        self.rolled_back = True


def test_default_timeout_below_nginx(monkeypatch):
    monkeypatch.delenv("RENT_HEAVY_STATEMENT_TIMEOUT_MS", raising=False)
    assert heavy_timeout_ms() == 90_000 < 120_000
    monkeypatch.setenv("RENT_HEAVY_STATEMENT_TIMEOUT_MS", "abc")
    assert heavy_timeout_ms() == 90_000
    monkeypatch.setenv("RENT_HEAVY_STATEMENT_TIMEOUT_MS", "5000")
    assert heavy_timeout_ms() == 5000


def test_guard_sets_and_restores_timeout():
    db = FakeDB()
    with heavy_query(db, message="x", timeout_ms=1234):
        db.execute("SELECT 1")
    assert db.settings == ["1234ms", "0"]


def test_guard_turns_statement_timeout_into_503():
    db = FakeDB()
    with pytest.raises(HTTPException) as ei:
        with heavy_query(db, message="안내", timeout_ms=10):
            raise OperationalError("SELECT", {}, _Canceled())
    assert ei.value.status_code == 503
    assert ei.value.detail == "안내"
    assert db.rolled_back
    assert db.settings == ["10ms"]  # 중단된 트랜잭션에는 되돌리기를 보내지 않는다


def test_guard_passes_other_db_errors_through():
    db = FakeDB()
    with pytest.raises(OperationalError):
        with heavy_query(db, message="안내", timeout_ms=10):
            raise OperationalError("SELECT", {}, _Other())


def _client(db: FakeDB) -> TestClient:
    from app.main import app
    from app.rent.db import get_rent_db

    def _override():
        yield db

    app.dependency_overrides[get_rent_db] = _override
    return TestClient(app)


@pytest.fixture
def _cleanup_overrides(monkeypatch):
    # 토큰·구독 게이트는 이 테스트 범위 밖 — 통과시킨다.
    from app import product_gate
    from app.config import settings

    async def _open(_request):
        return None

    monkeypatch.setattr(settings, "api_token", "")
    monkeypatch.setattr(product_gate, "product_gate_response", _open)
    yield
    from app.main import app

    app.dependency_overrides.clear()


def test_building_regression_timeout_is_503_with_message(_cleanup_overrides):
    db = FakeDB(heavy_error=_Canceled())
    c = _client(db)
    r = c.post(
        "/api/rent/buildings/abc123/regression/run",
        params={"asset_type": "apartment", "lease_kind": "jeonse"},
        json={"asset_type": "apartment"},
    )
    assert r.status_code == 503
    assert r.json()["detail"] == REGRESSION_TIMEOUT_MESSAGE
    assert db.settings and db.settings[0] == f"{heavy_timeout_ms()}ms"


def test_cohort_regression_timeout_is_503(_cleanup_overrides):
    db = FakeDB(heavy_error=_Canceled())
    c = _client(db)
    r = c.post(
        "/api/rent/regression/run",
        params=[("asset_type", "apartment"), ("building_key", "a1"), ("building_key", "b2")],
        json={"asset_type": "apartment"},
    )
    assert r.status_code == 503
    assert r.json()["detail"] == REGRESSION_TIMEOUT_MESSAGE


def test_transactions_hash_fallback_timeout_is_503(_cleanup_overrides):
    db = FakeDB(heavy_error=_Canceled())
    c = _client(db)
    r = c.get("/api/rent/buildings/nokey/transactions", params={"asset_type": "apartment"})
    assert r.status_code == 503
    assert r.json()["detail"] == TRANSACTIONS_TIMEOUT_MESSAGE


def test_real_postgres_statement_timeout_maps_to_503():
    """실제 PostgreSQL: pg_sleep 이 짧은 제한에 걸려 57014 → 503 (원장은 읽지 않는다)."""
    from app.rent.db import get_rent_engine

    eng = get_rent_engine()
    if eng is None:
        pytest.skip("RENT_DATABASE_URL 없음")
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    with Session(eng) as s:
        before = s.execute(text("SELECT current_setting('statement_timeout')")).scalar()
        s.rollback()
        with pytest.raises(HTTPException) as ei:
            with heavy_query(s, message="m", timeout_ms=200):
                s.execute(text("SELECT pg_sleep(2)"))
        assert ei.value.status_code == 503
        # 되돌린 뒤 같은 세션으로 다시 조회할 수 있고, 제한은 남지 않는다.
        assert s.execute(text("SELECT 1")).scalar() == 1
        assert s.execute(text("SELECT current_setting('statement_timeout')")).scalar() == before
    assert query_guard.QUERY_CANCELED == "57014"
