"""Phase C-9 — 화면 재현(로컬 API 인프로세스) + 분할 옛 키 처리 확인.

  python c9_screens.py --side before   # 로컬 원본 DB(GET·회귀 계산만)
  python c9_screens.py --side after    # 리허설 *_p2r
  python c9_screens.py --compare       # 두 결과 표(logs/collective_p2/c9_screens.md)

side 마다 COLLECTIVE/BUILT/RENT_DATABASE_URL 을 바꿔 app 을 import 한다(앱 설정은 환경변수 우선).
AI 는 HTTP(사용 기록 쓰기) 대신 층 효용 도구 함수를 직접 부른다.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "logs" / "collective_p2"
PY = r"D:\ch2\ch2_Macro\backend\.venv\Scripts\python.exe"


def _env(side: str) -> dict:
    sys.path.insert(0, str(ROOT / "pipeline"))
    from sqlalchemy.engine import make_url

    from collective.migrate_p2_keys import server_url_from_env

    base = make_url(server_url_from_env())
    sfx = "_p2r" if side == "after" else ""
    env = dict(os.environ)
    for k, db in (("COLLECTIVE_DATABASE_URL", "collective_stats"), ("BUILT_DATABASE_URL", "built_stats"),
                  ("RENT_DATABASE_URL", "rent_stats")):
        env[k] = base.set(database=db + sfx).render_as_string(hide_password=False)
    env["PYTHONUTF8"] = "1"
    env["API_PARAM_WARN_ENABLED"] = "false"
    return env


def run_side(side: str) -> dict:
    os.chdir(ROOT / "backend")
    sys.path.insert(0, str(ROOT / "backend"))
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from app.collective.db import get_collective_engine
    from app.main import app

    c = TestClient(app)
    eng = get_collective_engine()
    out: dict = {"db": None}
    with eng.connect() as conn:
        out["db"] = conn.execute(text("select current_database()")).scalar()
        as_of = conn.execute(text("select max(as_of_month) from collective_building_stats")).scalar()

        def lst(addr1, addr2, addr3, addr4, w=5, asset="apartment"):
            items, page = [], 1
            while True:
                r = c.get("/api/collective/buildings", params={"asset_type": asset, "addr1": addr1, "addr2": addr2,
                                                               "addr3_list": [addr3], "addr4_list": [addr4], "window_years": w,
                                                               "page": page, "page_size": 500})
                r.raise_for_status()
                d = r.json()
                items += d.get("items") or []
                if len(items) >= int(d.get("total") or 0) or not d.get("items"):
                    return d, items
                page += 1

        for label, args in {"우암동": ("충청북도", "청주시", "청원구", "우암동"),
                            "내수읍": ("충청북도", "청주시", "청원구", "내수읍"),
                            "춘의동": ("경기도", "부천시", "원미구", "춘의동")}.items():
            d, items = lst(*args)
            other = [i for i in items if (i.get("addr4") or "") != args[3]]
            out[f"list_{label}"] = {"n": len(items), "tx": sum(int(i.get("count") or 0) for i in items),
                                    "other_dong_rows": len(other),
                                    "other_names": sorted({str(i.get("display_name")) for i in other})[:8]}
        # 광산구 7년 롤링(거래 가장 많은 아파트)
        k = conn.execute(text("""select building_key from collective_building_stats where as_of_month=:a and window_years=7
                                 and asset_type='apartment' and addr1='전남광주통합특별시' and addr2='광산구' order by count desc limit 1"""),
                         {"a": as_of}).scalar()
        r = c.get(f"/api/collective/buildings/{k}/stats/rolling", params={"window_years": 7})
        pts = r.json().get("points") or r.json().get("items") or [] if r.status_code == 200 else []
        out["gwangsan_top_7y"] = {"status": r.status_code, "buckets": len(pts), "name": conn.execute(text(
            "select display_name from collective_building_stats where building_key=:k limit 1"), {"k": k}).scalar()}
        # 가경자이 회귀
        k = conn.execute(text("""select building_key from collective_building_stats where as_of_month=:a and window_years=5
                                 and display_name='가경자이' and addr2='청주시' order by count desc limit 1"""), {"a": as_of}).scalar()
        r = c.post(f"/api/collective/buildings/{k}/regression/run", json={"asset_type": "apartment"})
        j = r.json() if r.status_code == 200 else {}
        out["gagyeong_xi"] = {"status": r.status_code, "n": j.get("n"), "r_squared": j.get("r_squared"),
                              "excluded": [e.get("variable") for e in (j.get("excluded_variables") or [])]}
        # 대농로(비주거)
        ck = conn.execute(text("""select cluster_key from collective_commercial_transactions where road_name='대농로'
                                  and addr3='흥덕구' group by 1 order by count(*) desc limit 1""")).scalar()
        r = c.get(f"/api/collective/commercial/clusters/{ck}/addresses",
                  params={"contract_date_from": "2021-11-01", "contract_date_to": "2026-10-31"})
        items = r.json().get("items") or [] if r.status_code == 200 else []
        out["daenong_ro"] = {"status": r.status_code, "n": sum(int(i.get("count") or i.get("n") or 0) for i in items)}
        # 분할 옛 키·호남 옛 키 처리(이전 뒤에만 의미)
        has_map = conn.execute(text("select to_regclass('public.collective_building_key_map') is not null")).scalar()
        if has_map:
            old_s = conn.execute(text("""select old_key from collective_building_key_map where reason='split'
                                         group by 1 order by sum(n_tx) desc limit 1""")).scalar()
            old_h, new_h = conn.execute(text("""select old_key, new_key from collective_building_key_map where reason='honam_sido'
                                                order by n_tx desc limit 1""")).one()
            res = {}
            r = c.get(f"/api/collective/buildings/{old_s}/stats/rolling", params={"window_years": 5})
            res["modal_rolling_split"] = (r.status_code, r.json().get("key_status"), len(r.json().get("candidates") or []),
                                          isinstance(r.json().get("detail"), str))
            r = c.get(f"/api/collective/buildings/{old_s}/key-status")
            res["key_status_split"] = (r.status_code, r.json().get("key_status"))
            r = c.post("/api/collective/analysis/cohort/stats/by-year", json={"building_keys": [old_s], "asset_type": "apartment"})
            res["cohort_split"] = (r.status_code, r.json().get("key_status"))
            r = c.get("/api/rent/sale-join", params={"sale_building_key": old_s, "asset_type": "apartment"})
            res["rent_join_split"] = (r.status_code, r.json().get("key_status"))
            r = c.get(f"/api/collective/buildings/{old_h}/stats/rolling", params={"window_years": 7})
            res["modal_rolling_honam_old"] = (r.status_code, (r.headers.get("x-ch2-key-remapped") or "")[-12:] == new_h[-12:])
            r = c.post("/api/collective/analysis/cohort/stats/by-year", json={"building_keys": [old_h], "asset_type": "apartment"})
            res["cohort_honam_old"] = (r.status_code, r.json().get("building_keys") == [new_h] if r.status_code == 200 else None)
            from app.ai2 import live_floor
            from app.ai2.planner import _fmt_impossible

            cands = conn.execute(text("select new_key from collective_building_key_map where old_key=:k"), {"k": old_s}).scalars().all()
            live_floor.fetch_counts = lambda region: [("단지", k_, 200) for k_ in cands]
            env = live_floor._index(type("Ctx", (), {"region": "x", "target": ""})(), {"building_key": old_s})
            txt = _fmt_impossible(env) if env.reason_code else ""
            res["ai_floor_split"] = (env.reason_code, "여러 단지로 나뉘었습니다" in txt, env.analysis_possible)
            out["split_handling"] = res
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", choices=["before", "after"])
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--inner", action="store_true")
    a = ap.parse_args()
    if a.inner:
        print("C9JSON" + json.dumps(run_side(a.side), ensure_ascii=False, default=str))
        return
    if a.compare:
        res = {}
        for side in ("before", "after"):
            r = subprocess.run([PY, __file__, "--side", side, "--inner"], env=_env(side), capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            line = [x for x in r.stdout.splitlines() if x.startswith("C9JSON")]
            if not line:
                raise SystemExit(r.stderr[-3000:])
            res[side] = json.loads(line[-1][6:])
        (OUT / "c9_screens.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        keys = [k for k in res["after"] if k != "split_handling"]
        L = ["# C-9 화면 재현(전 = 로컬 원본 / 후 = *_p2r)", "", "| 항목 | 전 | 후 |", "|---|---|---|"]
        for k in keys:
            L.append(f"| {k} | {json.dumps(res['before'].get(k), ensure_ascii=False)} | {json.dumps(res['after'].get(k), ensure_ascii=False)} |")
        L += ["", "## 분할·호남 옛 키 처리(후)", "", "| 경로 | 결과 |", "|---|---|"]
        for k, v in (res["after"].get("split_handling") or {}).items():
            L.append(f"| {k} | {json.dumps(v, ensure_ascii=False)} |")
        (OUT / "c9_screens.md").write_text("\n".join(L), encoding="utf-8")
        print("\n".join(L))


if __name__ == "__main__":
    main()
