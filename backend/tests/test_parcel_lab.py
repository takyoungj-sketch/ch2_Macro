"""대장DB 관리자 조회 — 분류·연결 실패 (DB 없음)."""

from fastapi.testclient import TestClient

from app.parcel_lab.queries import classify_query
from app.parcel_lab.sido import sido_label


def test_classify_pnu_and_bjd():
    assert classify_query("3011010100101230001")[0] == "pnu"
    assert classify_query(" 3011010100101230001 ")[1] == "3011010100101230001"
    assert classify_query("3011010100") == ("bjd", "3011010100")
    assert classify_query("푸르지오")[0] == "name"
    assert classify_query("아")[0] == "empty"
    assert classify_query("")[0] == "empty"
    assert classify_query(None)[0] == "empty"


def test_sido_label_12_is_merged():
    assert "광주" in sido_label("12")
    assert sido_label("30") == "대전광역시"


def test_status_unavailable_without_db(monkeypatch):
    from app.parcel_lab import db as pdb
    from app.parcel_lab import router as rmod

    monkeypatch.setattr(pdb, "parcel_db_available", lambda: False)
    monkeypatch.setattr(rmod, "parcel_db_available", lambda: False)

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(rmod.router, prefix="/api")
    client = TestClient(app)
    res = client.get("/api/admin/parcel/status")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is False
    assert "parcel_master" in body["detail"]

    search = client.get("/api/admin/parcel/search", params={"sido": "30"})
    assert search.status_code == 503
