"""asset_type=all 지역 API 정규화."""

from fastapi.testclient import TestClient

from app.main import app


def test_gyeongbuk_addr2_with_all():
    c = TestClient(app)
    rows = c.get("/api/built/regions/addr2", params={"addr1": "경상북도", "asset_type": "all"}).json()
    assert len(rows) >= 20


def test_gyeongbuk_pohang_structure_with_all():
    c = TestClient(app)
    info = c.get(
        "/api/built/regions/structure",
        params={"addr1": "경상북도", "addr2": "포항시", "asset_type": "all"},
    ).json()
    assert info["has_intermediate"] is True
    assert info["leaf_level"] == "addr4"


def test_gyeongbuk_leaf_with_all():
    c = TestClient(app)
    leaves = c.get(
        "/api/built/regions/leaf",
        params={
            "addr1": "경상북도",
            "addr2": "포항시",
            "asset_type": "all",
            "addr3_list": "남구",
        },
    ).json()
    assert len(leaves) >= 5
