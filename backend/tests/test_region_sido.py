"""region_sido — 시도 목록 SSOT."""

from __future__ import annotations

import pytest

from app.collective.meta_cache import clear_meta_cache
from app.region_sido import list_sido_names


def test_list_sido_names_from_region_codes():
    from app.collective.db import get_collective_engine

    eng = get_collective_engine()
    if eng is None:
        pytest.skip("COLLECTIVE_DATABASE_URL not configured")
    clear_meta_cache()
    with eng.connect() as conn:
        names = list_sido_names(conn)
        assert len(names) == 16
        assert names[0] == "서울특별시"
        assert "세종특별자치시" in names
        assert list_sido_names(conn) == names


def test_collective_addr1_api_uses_region_codes_ssot():
    from fastapi.testclient import TestClient
    from app.collective.db import get_collective_engine
    from app.main import app

    if get_collective_engine() is None:
        pytest.skip("COLLECTIVE_DATABASE_URL not configured")

    client = TestClient(app)
    r = client.get("/api/collective/regions/addr1")
    assert r.status_code == 200
    assert len(r.json()) == 16

    meta = client.get("/api/collective/meta/filters")
    assert meta.status_code == 200
    assert meta.json()["addr1_list"] == r.json()

    comm = client.get("/api/collective/commercial/regions/addr1")
    assert comm.status_code == 200
    assert comm.json() == r.json()
