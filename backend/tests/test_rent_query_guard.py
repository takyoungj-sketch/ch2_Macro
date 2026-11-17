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
    with heavy_query(db, message="x", timeout_ms=1234) as guarded:
        guarded.execute("SELECT 1")
    assert 1 <= int(db.settings[0][:-2]) <= 1234
    assert db.settings[-1] == "0"


def test_guard_turns_statement_timeout_into_503():
    db = FakeDB()
    with pytest.raises(HTTPException) as ei:
        with heavy_query(db, message="안내", timeout_ms=10):
            raise OperationalError("SELECT", {}, _Canceled())
    assert ei.value.status_code == 503
    assert ei.value.detail == "안내"
    assert db.rolled_back
    assert db.settings == []  # 중단된 트랜잭션에는 되돌리기를 보내지 않는다


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
    # D-085 임대 회귀는 기본 관리자 전용 — 이 테스트는 시간 제한만 본다.
    monkeypatch.setenv("FEATURE_RENT_REGRESSION", "public")
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
    assert db.settings and 1 <= int(db.settings[0][:-2]) <= heavy_timeout_ms()


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


@pytest.fixture
def postgres_engine():
    """접속 불가 환경은 skip; 접속 후 검증 실패는 실패로 남긴다."""
    from app.rent.db import get_rent_engine
    from sqlalchemy import create_engine
    from sqlalchemy.exc import OperationalError

    configured = get_rent_engine()
    if configured is None:
        pytest.skip("PostgreSQL 미설정")
    eng = create_engine(configured.url, pool_size=1, max_overflow=0,
                        connect_args={"connect_timeout": 3})
    try:
        try:
            with eng.connect():
                pass
        except OperationalError:
            pytest.skip("PostgreSQL 접속 불가")
        yield eng
    finally:
        eng.dispose()


def test_real_postgres_statement_timeout_maps_to_503_and_pool_reuse(postgres_engine):
    from sqlalchemy import text

    eng = postgres_engine
    with eng.connect() as conn:
        before = conn.execute(text("SELECT current_setting('statement_timeout')")).scalar()
        pid = conn.execute(text("SELECT pg_backend_pid()")).scalar()
        conn.rollback()
        with pytest.raises(HTTPException) as ei:
            with heavy_query(conn, message="m", timeout_ms=200) as guarded:
                guarded.execute(text("SELECT pg_sleep(2)"))
        assert ei.value.status_code == 503
        assert query_guard.is_statement_timeout(ei.value.__cause__)
    # 풀에 반환한 뒤 같은 물리 연결을 다시 빌린다.
    with eng.connect() as conn:
        assert conn.execute(text("SELECT pg_backend_pid()")).scalar() == pid
        assert conn.execute(text("SELECT current_setting('statement_timeout')")).scalar() == before
        with heavy_query(conn, message="m", timeout_ms=200) as guarded:
            assert guarded.execute(text("SELECT 1")).scalar() == 1
        assert conn.execute(text("SELECT current_setting('statement_timeout')")).scalar() == before
    with eng.connect() as conn:
        assert conn.execute(text("SELECT current_setting('statement_timeout')")).scalar() == before


def test_real_postgres_multiple_statements_share_deadline(postgres_engine):
    import time
    from sqlalchemy import text

    with postgres_engine.connect() as conn:
        started = time.monotonic()
        with pytest.raises(HTTPException) as ei:
            with heavy_query(conn, message="m", timeout_ms=250) as guarded:
                guarded.execute(text("SELECT pg_sleep(0.15)"))
                guarded.execute(text("SELECT pg_sleep(0.15)"))
        assert ei.value.status_code == 503
        assert time.monotonic() - started < 2


def test_timeout_is_capped_and_warns(monkeypatch, caplog):
    monkeypatch.setenv("RENT_HEAVY_STATEMENT_TIMEOUT_MS", "999999")
    assert heavy_timeout_ms() == 100_000
    assert "100초" in caplog.text


def test_normal_regression_is_200(_cleanup_overrides):
    import random
    rng = random.Random(42)
    rows = []
    for _ in range(40):
        area = 40 + rng.random() * 70
        floor, age = rng.randrange(1, 20), rng.randrange(30)
        price = 10000 + area * 400 + floor * 80 - age * 120 + rng.random() * 1000
        rows.append(dict(building_key="abc123", display_name="test", exclusive_area=area,
                         floor=floor, building_age=age, price=price,
                         unit_price=price / area, housing_subtype="apartment"))
    db = FakeDB(rows=rows)
    r = _client(db).post("/api/rent/buildings/abc123/regression/run",
                        params={"asset_type": "apartment"}, json={"asset_type": "apartment"})
    assert r.status_code == 200
    assert r.json()["n"] > 8
    assert db.settings[-1] == "0"


def test_transactions_total_deadline_returns_503(_cleanup_overrides, monkeypatch):
    # COUNT 60ms + 목록 60ms: 각 문장은 예산보다 짧지만 합계는 100ms를 넘는다.
    clock = [0.0]
    monkeypatch.setattr(query_guard.time, "monotonic", lambda: clock[0])
    monkeypatch.setenv("RENT_HEAVY_STATEMENT_TIMEOUT_MS", "100")

    class SlowDB(FakeDB):
        def execute(self, stmt, params=None):
            result = super().execute(stmt, params)
            if "rent_transactions" in str(stmt):
                clock[0] += 0.060
            return result

    db = SlowDB()
    r = _client(db).get("/api/rent/buildings/key/transactions")
    assert r.status_code == 503
    assert r.json()["detail"] == TRANSACTIONS_TIMEOUT_MESSAGE
    limits = [int(v[:-2]) for v in db.settings if v.endswith("ms")]
    assert limits[0] == 100
    assert 39 <= limits[1] <= 40
    assert db.rolled_back


def test_expired_request_does_not_execute_sql(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(query_guard.time, "monotonic", lambda: clock[0])
    deadline = query_guard.QueryDeadline(10)
    clock[0] = 0.020
    db = FakeDB()
    with pytest.raises(HTTPException) as ei:
        with heavy_query(db, message="m", deadline=deadline):
            pytest.fail("expired request executed")
    assert ei.value.status_code == 503
    assert db.settings == []
