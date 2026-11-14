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
    d = r.json()
    assert isinstance(d["detail"], str) and "여러" not in d["detail"] or "나뉘었습니다" in d["detail"]
    assert "삼일(우암동, 7건)" in d["detail"]
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
    assert "/api/rent/buildings/{building_key}/key-status" in paths      # 임대 C-2 안내용(DB 조회 없음)


def test_rent_sale_key_and_cohort_body():
    app = FastAPI()

    @app.get("/api/rent/sale-join")
    def sj(sale_building_key: str):
        return {"k": sale_building_key}

    @app.post("/api/collective/analysis/cohort/stats/by-year")
    async def cohort(request: Request):
        return await request.json()

    cache = KeyMapCache(loader=lambda name: MAPS.get(name, {}), ttl=0)
    app.add_middleware(KeyRemapMiddleware, cache=cache, details=lambda a, ks: {})
    c = TestClient(app)
    # 임대 → 매매 키는 집합 연결표로 푼다
    assert c.get(f"/api/rent/sale-join?sale_building_key={OLD1}").json() == {"k": NEW1}
    assert c.get(f"/api/rent/sale-join?sale_building_key={OLDS}").status_code == 409
    # 코호트 body: 1:1 은 바꾸고 나머지 칸은 그대로
    r = c.post("/api/collective/analysis/cohort/stats/by-year", json={"building_keys": [OLD1, OTHER], "x": 1})
    assert r.json() == {"building_keys": [NEW1, OTHER], "x": 1}
    assert r.headers["x-ch2-key-remapped"] == f"{OLD1}->{NEW1}"
    r = c.post("/api/collective/analysis/cohort/stats/by-year", json={"building_keys": [OTHER, OLDS]})
    assert r.status_code == 409 and r.json()["old_key"] == OLDS
    # 키 없는 body 는 그대로
    assert c.post("/api/collective/analysis/cohort/stats/by-year", json={"a": [1]}).json() == {"a": [1]}


def test_ai_floor_tool_does_not_pick_a_split_candidate(monkeypatch):
    from app.ai2 import live_floor
    from app.ai2.planner import _fmt_impossible
    from app.collective import key_remap

    monkeypatch.setattr(key_remap, "CACHE", KeyMapCache(loader=lambda name: MAPS.get(name, {}), ttl=0))
    monkeypatch.setattr(key_remap, "_default_details",
                        lambda a, ks: {P1: {"display_name": "삼일", "addr4": "우암동"}, P2: {"display_name": "삼일", "addr4": "내수읍"}})
    monkeypatch.setattr(live_floor, "fetch_counts", lambda region: [("삼일", P1, 50), ("삼일", P2, 40)])
    env = live_floor._index(type("Ctx", (), {"region": "x", "target": "삼일"})(), {"building_key": OLDS})
    assert env.reason_code == "KEY_SPLIT" and env.analysis_possible is False
    text = _fmt_impossible(env)
    assert "여러 단지로 나뉘었습니다" in text and "우암동" in text and "내수읍" in text
    assert "유효표본" not in text


# --- C-2: 가장 큰 그룹이 옛 키를 유지 → 막지 않고 열되 「분리된 단지 있음」을 붙인다 ---------------------

K = "1" * 64        # C-01 1:N 옛 키
K1, K2 = "2" * 64, "3" * 64   # C-01 새 키(동 단위)
K1A = "4" * 64      # K1 의 C-2 조각
H_OLD, H_NEW, H_C2 = "5" * 64, "6" * 64, "7" * 64   # 호남 1:1 → 새 키에 C-2
C2ONLY, C2A, C2B = "8" * 64, "9" * 64, "0" * 64

C2MAPS = {"collective": {
    K: [(K1, 1, 30), (K2, 2, 10)],                       # C-01 분할(409 유지)
    K1: [(K1A, 1, 6, "c2")],                             # C-01 새 키가 C-2 옛 키
    H_OLD: [(H_NEW, 0, 5)], H_NEW: [(H_C2, 1, 4, "c2")],  # 1:1 뒤 C-2
    C2ONLY: [(C2A, 1, 8, "c2"), (C2B, 2, 3, "c2")],
}}


def _c2_app():
    app = FastAPI()

    @app.get("/api/collective/buildings/{key}/stats/rolling")
    def rolling(key: str):
        return {"key": key}

    @app.get("/api/collective/buildings/{key}/list")
    def as_list(key: str):
        return [key]

    @app.get("/api/collective/buildings")
    def lst(request: Request):
        return {"q": dict(request.query_params)}

    cache = KeyMapCache(loader=lambda name: C2MAPS.get(name, {}), ttl=0)
    det = lambda a, ks: {C2A: {"display_name": "가동빌라"}}  # noqa: E731
    app.add_middleware(KeyRemapMiddleware, cache=cache, details=det)
    return TestClient(app)


def test_c2_old_key_opens_largest_group_with_siblings_note():
    c = _c2_app()
    r = c.get(f"/api/collective/buildings/{C2ONLY}/stats/rolling")
    assert r.status_code == 200
    d = r.json()
    assert d["key"] == C2ONLY                                    # 옛 키 그대로(가장 큰 그룹)
    note = d["key_split_c2"]
    assert note["status"] == "has_split_siblings" and note["building_key"] == C2ONLY
    assert note["new_keys"] == [C2A, C2B] and note["candidates"][0]["display_name"] == "가동빌라"
    assert r.headers["x-ch2-key-c2-split"] == f"{C2ONLY}:{C2A}|{C2B}"
    assert "x-ch2-key-remapped" not in r.headers
    assert int(r.headers["content-length"]) == len(r.content)
    # JSON 객체가 아니면 본문은 그대로, 헤더만
    r = c.get(f"/api/collective/buildings/{C2ONLY}/list")
    assert r.json() == [C2ONLY] and r.headers["x-ch2-key-c2-split"].startswith(C2ONLY)
    # query building_key 도 같은 안내
    r = c.get(f"/api/collective/buildings?building_key={C2ONLY}")
    assert r.json()["q"] == {"building_key": C2ONLY} and r.json()["key_split_c2"]["new_keys"] == [C2A, C2B]


def test_c01_and_c2_overlap():
    c = _c2_app()
    # C-01 1:N 옛 키는 그대로 409(C-2 가 있어도)
    r = c.get(f"/api/collective/buildings/{K}/stats/rolling")
    assert r.status_code == 409 and [x["building_key"] for x in r.json()["candidates"]] == [K1, K2]
    # C-01 새 키가 C-2 옛 키 → 그 키로 열고 C-2 안내
    r = c.get(f"/api/collective/buildings/{K1}/stats/rolling")
    assert r.status_code == 200 and r.json()["key"] == K1 and r.json()["key_split_c2"]["new_keys"] == [K1A]
    # 다른 C-01 새 키는 안내 없음
    r = c.get(f"/api/collective/buildings/{K2}/stats/rolling")
    assert r.json() == {"key": K2} and "x-ch2-key-c2-split" not in r.headers
    # 호남 1:1 로 바뀐 키가 C-2 옛 키 → 두 처리 모두
    r = c.get(f"/api/collective/buildings/{H_OLD}/stats/rolling")
    assert r.json()["key"] == H_NEW and r.json()["key_split_c2"]["new_keys"] == [H_C2]
    assert r.headers["x-ch2-key-remapped"] == f"{H_OLD}->{H_NEW}"
    assert r.headers["x-ch2-key-c2-split"] == f"{H_NEW}:{H_C2}"


def test_resolve_key_reports_c2_and_keeps_c01_split():
    from app.collective.key_remap import resolve_key

    cache = KeyMapCache(loader=lambda name: C2MAPS.get(name, {}), ttl=0)
    nod = lambda a, ks: {}  # noqa: E731
    assert resolve_key("collective", K, cache=cache, details=nod)["status"] == "split"
    r = resolve_key("collective", K1, cache=cache, details=nod)
    assert r["status"] == "ok" and r["building_key"] == K1 and r["key_split_c2"]["new_keys"] == [K1A]
    r = resolve_key("collective", H_OLD, cache=cache, details=nod)
    assert r["status"] == "remapped" and r["building_key"] == H_NEW and r["key_split_c2"]["new_keys"] == [H_C2]
    assert "key_split_c2" not in resolve_key("collective", K2, cache=cache, details=nod)


def test_loader_marks_c2_rows_from_reason():
    from app.collective import key_remap as kr

    class _Res(list):
        def scalar(self):
            return True

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, stmt, params=None):
            if "to_regclass" in str(stmt):
                return _Res()
            return _Res([(K, K1, 1, 30, "split"), (K, K2, 2, 10, "split"), (K1, K1A, 1, 6, "c2_split"),
                         (H_OLD, H_NEW, 0, 5, "honam_sido")])

    class _Eng:
        def connect(self):
            return _Conn()

    m = kr._load_from_engine(_Eng(), "collective_building_key_map")
    assert m[K] == [(K1, 1, 30, ""), (K2, 2, 10, "")]
    assert m[K1] == [(K1A, 1, 6, "c2")] and m[H_OLD] == [(H_NEW, 0, 5, "")]
