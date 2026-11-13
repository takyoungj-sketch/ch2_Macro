"""Phase C — 표제부 사본 DB(parcel_master_p2r) 만들기 + title_fill(새 키만) 리허설.

T 결정(2026-11-13): 로컬 원천으로 사본을 3시간 안에 만들 수 있으면 사본 리허설.
1) build: parcel_master_p2r 를 새로 만들고(이미 있으면 --recreate 없이는 멈춤)
   `parcel_master.load_title_pilot` 를 PILOT(30·43)·EXPAND(나머지) 두 번, --skip-ledger 로 돌린다.
   원천 = raw/raw addition/건축물대장 표제부 3판(읽기만). 표제부 스캔 캐시(gitignore)가 있으면 그것을 쓴다.
   PARCEL_MASTER_DATABASE_URL 을 사본으로 고정, 하위 프로세스 시작 전에 이름 확인.
2) fill: c3 실행기로 title_fill_new_keys 만(가드는 실행기). 전후 collective_building_attributes 비교:
   새 조각 키 채움 수·커버리지, 새 키가 아닌 행 변화(0 이어야 함).
출력: logs/collective_p2/c14_title_copy.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "pipeline"))
from collective.migrate_p2_keys import REHEARSAL_RE, server_url_from_env  # noqa: E402

PY = r"D:\ch2\ch2_Macro\backend\.venv\Scripts\python.exe"
OUT = ROOT / "logs" / "collective_p2"
DB = "parcel_master_p2r"
COLL = "collective_stats_p2r"


def _admin():
    return create_engine(make_url(server_url_from_env()).set(database="postgres"), isolation_level="AUTOCOMMIT")


MAIN_RAW = Path(r"D:\ch2\ch2_Macro\raw")


def ensure_raw_link(root: Path = ROOT, main_raw: Path = MAIN_RAW) -> Path:
    """표제부 경로는 저장소 기준(`<repo>/raw/raw addition`)인데 worktree 에는 raw 가 없다(gitignore)
    → 원본 checkout 의 raw 를 디렉터리 정션으로 잇는다(적재기는 읽기만). 이미 있으면 그대로."""
    link = root / "raw"
    if link.exists():
        return link
    if not main_raw.is_dir():
        raise SystemExit(f"원천 raw 없음: {main_raw}")
    r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(main_raw)], capture_output=True, text=True,
                       encoding="cp949", errors="replace")  # cmd 출력은 시스템 코드 페이지
    if r.returncode != 0 or not link.exists():
        raise SystemExit(f"raw 정션 실패: {r.stderr or r.stdout}")
    return link


def build(recreate: bool) -> list[tuple[str, float]]:
    assert REHEARSAL_RE.match(DB)
    ensure_raw_link()
    eng = _admin()
    with eng.connect() as c:
        exists = c.execute(text("SELECT 1 FROM pg_database WHERE datname=:n"), {"n": DB}).scalar()
        if exists and not recreate:
            raise SystemExit(f"{DB} 이미 있음 — --recreate 로만 다시 만든다")
        if exists:
            c.execute(text(f"DROP DATABASE {DB} WITH (FORCE)"))
        c.execute(text(f"CREATE DATABASE {DB}"))
    eng.dispose()
    env = dict(os.environ)
    env["PARCEL_MASTER_DATABASE_URL"] = make_url(server_url_from_env()).set(database=DB).render_as_string(hide_password=False)
    env["PYTHONUTF8"] = "1"
    times = []
    for label, sido_args in (("pilot(30·43)", []),
                             ("expand(나머지)", ["--sido", *__import__("parcel_master.paths", fromlist=["EXPAND_SIDO"]).EXPAND_SIDO])):
        t0 = time.time()
        log = OUT / f"c14_load_{label[:5]}.log"
        with log.open("w", encoding="utf-8") as f:
            r = subprocess.run([PY, "-u", "-m", "parcel_master.load_title_pilot", "--skip-ledger", *sido_args],
                               env=env, cwd=str(ROOT / "pipeline"), stdout=f, stderr=subprocess.STDOUT)
        times.append((f"적재 {label}", round(time.time() - t0, 1)))
        if r.returncode != 0:
            raise SystemExit(f"적재 실패 {label}: {log}")
    return times


def attrs_snapshot() -> dict[tuple, str]:
    e = create_engine(make_url(server_url_from_env()).set(database=COLL),
                      connect_args={"options": "-c default_transaction_read_only=on"})
    with e.connect() as c:
        rows = c.execute(text("SELECT building_key, asset_type, snapshot_ym, md5(a::text) FROM collective_building_attributes a")).all()
    e.dispose()
    return {(r[0], r[1], str(r[2])): r[3] for r in rows}


def fill() -> dict:
    e = create_engine(make_url(server_url_from_env()).set(database=COLL),
                      connect_args={"options": "-c default_transaction_read_only=on"})
    with e.connect() as c:
        new_keys = {r[0] for r in c.execute(text(
            "SELECT DISTINCT new_key FROM collective_building_key_map WHERE reason LIKE '%split%'"))}
    e.dispose()
    before = attrs_snapshot()
    t0 = time.time()
    r = subprocess.run([PY, str(ROOT / "scripts" / "lab" / "collective_p2" / "c3_run_rehearsal.py"), "--only", "title_fill_new_keys"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    secs = round(time.time() - t0, 1)
    if r.returncode != 0:
        raise SystemExit("title_fill 실패:\n" + r.stdout[-2000:] + r.stderr[-2000:])
    after = attrs_snapshot()
    changed = [k for k in before if k in after and before[k] != after[k]]
    added = [k for k in after if k not in before]
    removed = [k for k in before if k not in after]
    old_changed = [k for k in changed if k[0] not in new_keys]
    new_changed = [k for k in changed if k[0] in new_keys] + [k for k in added if k[0] in new_keys]
    have_new = {k[0] for k in after if k[0] in new_keys}
    return {"seconds": secs, "new_split_keys": len(new_keys), "new_keys_with_attr_row_after": len(have_new),
            "rows_changed": len(changed), "rows_added": len(added), "rows_removed": len(removed),
            "non_new_key_rows_changed": len(old_changed) + sum(1 for k in added if k[0] not in new_keys) + len(removed),
            "new_key_rows_filled_or_added": len(new_changed),
            "fill_log_tail": [x[-220:] for x in (OUT / "c3_title_fill_new_keys.log").read_text(encoding="utf-8", errors="replace")
                              .splitlines() if "fill=" in x or "snapshot_ym=" in x][-8:],
            "digest": hashlib.md5(json.dumps(sorted(map(str, changed))).encode()).hexdigest()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recreate", action="store_true")
    ap.add_argument("--skip-build", action="store_true")
    ap.add_argument("--build-only", action="store_true", help="사본만 만든다(c5 가 같은 속성 표를 읽는 동안 fill 은 미룸)")
    a = ap.parse_args()
    t0 = time.time()
    times = [] if a.skip_build else build(a.recreate)
    if a.build_only:
        (OUT / "c14_build_times.json").write_text(json.dumps(times, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"build_seconds": round(time.time() - t0, 1), "steps": times}, ensure_ascii=False))
        return
    if a.skip_build and (OUT / "c14_build_times.json").exists():
        times = [tuple(x) for x in json.loads((OUT / "c14_build_times.json").read_text(encoding="utf-8"))]
    res = fill()
    L = ["# C-14 표제부 사본 리허설", "", f"- 총 소요 {round(time.time() - t0, 1)}초", ""]
    L += [f"| {k} | {v}초 |" for k, v in times]
    L += ["", "```json", json.dumps(res, ensure_ascii=False, indent=1), "```"]
    (OUT / "c14_title_copy.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
