"""Phase C-3·4 — 리허설 DB에서 이전 → 거래유형 보정 → mart 재생성(단계별 시간).

모든 하위 프로세스에 COLLECTIVE/BUILT/RENT_DATABASE_URL 을 *_p2r 로 넣는다(빌더는 환경변수 우선).
각 단계 전에 같은 환경으로 「엔진 탐침」을 돌려 세 엔진이 모두 *_p2r 에 붙는지 확인하고, 아니면 멈춘다.
결과: logs/collective_p2/c3_steps.jsonl (단계·초·종료코드), 단계 출력은 logs/collective_p2/c3_<step>.log
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "pipeline"))
from collective.migrate_p2_keys import REHEARSAL_RE, server_url_from_env  # noqa: E402

PY = r"D:\ch2\ch2_Macro\backend\.venv\Scripts\python.exe"
MAIN = Path(r"D:\ch2\ch2_Macro")
OUT = ROOT / "logs" / "collective_p2"
AS_OF = "2026-10-01"
KAPT = MAIN / "raw" / "raw addition" / "K-apt공동주택관리정보시스템" / "20261002_단지_기본정보.xlsx"
DBS = {"collective": "collective_stats_p2r", "built": "built_stats_p2r", "rent": "rent_stats_p2r"}

PROBE = r"""
import sys, json
sys.path.insert(0, r'{pipe}'); sys.path.insert(0, r'{pipe}\collective')
from sqlalchemy import text
from collective.db_utils import get_collective_engine
from rent.db_utils import get_rent_engine
from built.db_utils import get_built_engine
from parcel_master.db_utils import get_collective_engine as pm_coll
import importlib.util
spec = importlib.util.spec_from_file_location('bca', r'{pipe}\build_collective_building_attributes.py')
out = {{}}
for name, fn in [('collective', get_collective_engine), ('rent', get_rent_engine), ('built', get_built_engine), ('parcel_master.collective', pm_coll)]:
    with fn().connect() as c:
        out[name] = c.execute(text('select current_database()')).scalar()
print(json.dumps(out))
"""


def step_list():
    P = lambda *a: [PY, *[str(x) for x in a]]  # noqa: E731
    pipe = ROOT / "pipeline"
    m = pipe / "collective" / "migrate_p2_keys.py"
    dbargs = ["--collective-db", DBS["collective"], "--built-db", DBS["built"], "--rent-db", DBS["rent"]]
    w = ["--as-of", AS_OF, "--windows", "3,5,7"]
    return [
        ("migrate_apply", P(m, *dbargs, "--apply")),
        ("migrate_verify", P(m, *dbargs, "--verify")),
        ("dealtype_apply", P(pipe / "collective" / "fix_p2_deal_types.py", "--collective-db", DBS["collective"],
                             "--raw-root", MAIN / "raw", "--logs-dir", MAIN / "logs", "--apply")),
        ("building_stats", P(pipe / "build_collective_building_stats.py", *w, "--replace-as-of", "--prune-annual")),
        ("building_rolling", P(pipe / "build_collective_building_rolling_stats.py", *w, "--replace-as-of")),
        ("presale_lifetime", P(pipe / "build_collective_presale_lifetime_stats.py", "--as-of", AS_OF, "--replace")),
        ("market_stats", P(pipe / "build_collective_market_stats.py", *w)),
        ("commercial_cluster", P(pipe / "build_collective_commercial_cluster_stats.py", *w, "--replace-as-of", "--prune-annual")),
        ("commercial_cluster_rolling", P(pipe / "build_collective_commercial_cluster_rolling_stats.py", *w, "--replace-as-of")),
        ("rent_building_stats", P(pipe / "rent" / "build_building_stats.py", *w, "--replace-as-of")),
        ("kapt_new_keys_apartment", P(pipe / "build_collective_building_attributes.py", "--kapt-file", KAPT,
                                      "--asset-type", "apartment", "--new-keys-only")),
        ("title_fill_new_keys", P("-c", f"import sys; sys.path.insert(0, r'{pipe}'); "
                                        "from parcel_master.apply_title_fill import run; run(dry_run=False, new_keys_only=True)")),
        ("rent_sale_map", P(pipe / "rent" / "build_sale_building_map.py")),
        ("built_scope_stats", P(pipe / "built" / "build_scope_stats.py", "--as-of", AS_OF[:7], "--windows", "3,5,7")),
        # 복합 scope mart 는 addr1 칸으로 UPSERT → 이번 as_of 의 옛 시도명 행은 남는다 → 그 as_of 만 지운다(과거 as_of 유지)
        ("built_scope_legacy_cleanup", P("-c", "import os; from sqlalchemy import create_engine, text; "
                                              "e = create_engine(os.environ['BUILT_DATABASE_URL']); "
                                              "c = e.begin().__enter__(); "
                                              "assert c.execute(text('select current_database()')).scalar().endswith('_p2r'); "
                                              f"n = c.execute(text(\"DELETE FROM built_scope_stats WHERE as_of_month = '{AS_OF}' "
                                              "AND addr1 IN ('광주광역시','전라남도')\")).rowcount; c.commit(); print('deleted', n)")),
    ]


def env_for() -> dict:
    base = make_url(server_url_from_env())
    env = dict(os.environ)
    for k, db in (("COLLECTIVE_DATABASE_URL", DBS["collective"]), ("BUILT_DATABASE_URL", DBS["built"]),
                  ("RENT_DATABASE_URL", DBS["rent"])):
        assert REHEARSAL_RE.match(db)
        env[k] = base.set(database=db).render_as_string(hide_password=False)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def probe(env) -> dict:
    code = PROBE.format(pipe=str(ROOT / "pipeline"))
    r = subprocess.run([PY, "-c", code], env=env, capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT / "pipeline"))
    if r.returncode != 0:
        raise SystemExit("엔진 탐침 실패:\n" + r.stderr[-2000:])
    got = json.loads(r.stdout.strip().splitlines()[-1])
    bad = {k: v for k, v in got.items() if not REHEARSAL_RE.match(v or "")}
    if bad:
        raise SystemExit(f"리허설 DB가 아닌 접속 감지 — 중단: {bad}")
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="쉼표 구분 단계 이름")
    ap.add_argument("--from-step", default="")
    a = ap.parse_args()
    env = env_for()
    steps = step_list()
    names = [s[0] for s in steps]
    if a.from_step:
        steps = steps[names.index(a.from_step):]
    if a.only:
        steps = [s for s in steps if s[0] in a.only.split(",")]
    log = OUT / "c3_steps.jsonl"
    for name, cmd in steps:
        got = probe(env)
        t0 = time.time()
        with (OUT / f"c3_{name}.log").open("w", encoding="utf-8") as f:
            r = subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.STDOUT, cwd=str(ROOT / "pipeline"))
        rec = {"step": name, "seconds": round(time.time() - t0, 1), "rc": r.returncode, "dbs": got}
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(json.dumps(rec, ensure_ascii=False), flush=True)
        if r.returncode != 0:
            raise SystemExit(f"단계 실패: {name} (logs/collective_p2/c3_{name}.log)")


if __name__ == "__main__":
    main()
