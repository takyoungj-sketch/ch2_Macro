"""집합 2단계 — 밤 점검 창의 「가벼운 비교」(읽기 전용, prod_sync_check 와 별도). 런북 3·6.1.

낮 무거운 동기화 확인(prod_sync_check --allow-heavy) 때 세 DB 의 쓰기 카운터를 기록해 두고, 밤 점검 모드 ON 뒤 다시 읽어
「낮 이후 운영 전용 표 밖에서 쓰기가 있었는가」를 본다. 행을 읽지 않고 통계 뷰만 읽으므로 몇 초면 끝난다.

  snapshot : DB 마다 pg_stat_user_tables(n_tup_ins·n_tup_upd·n_tup_del) 전 표 + pg_stat_database.stats_reset → JSON
  compare  : 낮 JSON(--baseline) ↔ 지금 다시 읽은 값. 실패(종료 코드 1) 조건 — 하나라도:
             · 운영 전용 표(EXCLUDE: 집합 3 + 임대 1 + 복합 qa_audit_run 1) 밖 표의 세 값 중 하나라도 다름
             · stats_reset 이 바뀜(카운터가 초기화돼 비교할 수 없음)
             · 표가 빠짐(낮에 있던 표가 지금 없음) 또는 새 표가 생김
             · 필요한 DB(collective_stats·rent_stats·built_stats) 가 낮 또는 지금 기록에 없음
             · 전체가 --deadline(기본 60초) 안에 끝나지 않음(쿼리 시간 초과 포함) — 시간 초과·누락은 통과로 세지 않는다
             통과만 종료 코드 0. (이 도구는 「검증 못 함」(2)을 두지 않는다 — 밤에는 못 본 것도 실패로 멈춘다)

  python prod_stat_compare.py snapshot --db-env COLLECTIVE_DATABASE_URL --db-env RENT_DATABASE_URL --db-env BUILT_DATABASE_URL \\
      --env-file /opt/ch2_Macro/backend/.env --out /var/backups/ch2/p2/stat_day.json
  python prod_stat_compare.py compare --baseline /var/backups/ch2/p2/stat_day.json --db-env … (같은 셋) --env-file … \\
      --result-out /var/backups/ch2/p2/stat_night_result.json

출력은 표 이름·숫자만(행 값 없음). 접속 정보는 출력하지 않는다. pipeline 을 쓰지 않는다(서버 backend venv 로 실행).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _common import Timed, db_name, db_url, now_iso, read_json, ro_conn, write_json  # noqa: E402

KIND = "stat_compare"
REQUIRED_DBS = ("collective_stats", "rent_stats", "built_stats")
# 운영 서버가 직접 쓰는 표(런북 2.5) — 밤 비교에서 뺀다(이 표의 변화는 병합·built QA 확인이 따로 다룬다)
EXCLUDE: dict[str, frozenset[str]] = {
    "collective_stats": frozenset({"public.collective_building_geocodes", "public.collective_commercial_map_geocodes",
                                   "public.qa_audit_run"}),
    "rent_stats": frozenset({"public.rent_building_geocodes"}),
    "built_stats": frozenset({"public.qa_audit_run"}),
}
def role(dbname: str) -> str:
    """DB 이름 → 역할(collective_stats·rent_stats·built_stats). 리허설 이름(…_p2r)도 같은 역할로 본다."""
    import re

    return re.sub(r"_p2r(_[a-z0-9]+)?$", "", str(dbname or ""))


def _by_role(snap: dict) -> dict:
    out: dict = {}
    for name, v in (snap.get("dbs") or {}).items():
        out.setdefault(role(name), v)
    return out


STAT_SQL = ("SELECT schemaname || '.' || relname, n_tup_ins, n_tup_upd, n_tup_del FROM pg_stat_user_tables "
            "ORDER BY 1")
RESET_SQL = "SELECT stats_reset FROM pg_stat_database WHERE datname = current_database()"


def read_db(conn, t: Timed, timeout_ms: int) -> dict:
    """한 DB 의 카운터. 쿼리가 실패·시간 초과면 tables/stats_reset 이 None(→ 비교에서 실패)."""
    rows = t.run(conn, "pg_stat_user_tables", STAT_SQL, timeout_ms=timeout_ms, fetch="all")
    reset = t.run(conn, "pg_stat_database.stats_reset", RESET_SQL, timeout_ms=timeout_ms, fetch="one")
    return {"db": db_name(conn), "measured_at": now_iso(),
            "stats_reset": None if reset is None else str(reset[0]),
            "stats_reset_ok": reset is not None,
            "tables": None if rows is None else {r[0]: [int(r[1]), int(r[2]), int(r[3])] for r in rows}}


def take(db_envs: list[str], env_file: Path | None, *, deadline_s: float, clock=time.monotonic, reader=None) -> dict:
    """여러 DB 를 차례로 읽는다. 전체 deadline 을 넘기면 남은 DB 는 읽지 않고 timed_out=True."""
    t0 = clock()
    out = {"kind": KIND, "measured_at": now_iso(), "deadline_s": deadline_s, "dbs": {}, "timed_out": False, "errors": []}
    for env in db_envs:
        left = deadline_s - (clock() - t0)
        if left <= 0:
            out["timed_out"] = True
            out["errors"].append(f"{env}: 시간 초과로 읽지 못함")
            continue
        try:
            if reader is not None:
                snap = reader(env, left)
            else:
                t = Timed()
                with ro_conn(db_url(env, env_file)) as conn:
                    snap = read_db(conn, t, int(max(1, left) * 1000))
                    snap["_timings"] = t.log
        except SystemExit as ex:                       # 접속 정보 없음 등
            out["errors"].append(f"{env}: {ex}")
            continue
        except Exception as ex:  # noqa: BLE001      # 접속 실패·시간 초과
            out["errors"].append(f"{env}: {type(ex).__name__}")
            continue
        out["dbs"][snap["db"]] = snap
    out["elapsed_s"] = round(clock() - t0, 2)
    if out["elapsed_s"] > deadline_s:
        out["timed_out"] = True
    return out


def compare_snaps(day: dict, night: dict) -> tuple[str, list[list[str]]]:
    """(pass|fail, 문제 목록[표/DB, 무엇, 낮, 밤]). 못 본 것·시간 초과도 fail."""
    prob: list[list[str]] = []
    for side, s in (("낮", day), ("밤", night)):
        if not isinstance(s, dict) or s.get("kind") != KIND:
            prob.append(["(기록)", f"{side} 기록이 이 도구의 스냅샷이 아님", "", ""])
            return "fail", prob
        if s.get("timed_out"):
            prob.append(["(기록)", f"{side} 기록이 시간 안에 끝나지 않음(deadline {s.get('deadline_s')}초)", "", ""])
        for e in s.get("errors") or []:
            prob.append(["(기록)", f"{side} 읽기 실패: {e}", "", ""])
    dr, nr = _by_role(day), _by_role(night)
    for db in REQUIRED_DBS:
        a, b = dr.get(db), nr.get(db)
        if a is not None and b is not None and a.get("db") != b.get("db"):
            prob.append([db, "낮·밤 DB 이름이 다름", str(a.get("db")), str(b.get("db"))])
            continue
        if a is None or b is None:
            prob.append([db, "DB 기록 없음", "있음" if a else "없음", "있음" if b else "없음"])
            continue
        if not a.get("stats_reset_ok", True) or not b.get("stats_reset_ok", True):
            prob.append([db, "stats_reset 을 읽지 못함", str(a.get("stats_reset")), str(b.get("stats_reset"))])
        elif a.get("stats_reset") != b.get("stats_reset"):
            prob.append([db, "stats_reset 바뀜(카운터 초기화)", str(a.get("stats_reset")), str(b.get("stats_reset"))])
        ta, tb = a.get("tables"), b.get("tables")
        if ta is None or tb is None:
            prob.append([db, "표 카운터를 읽지 못함(시간 초과·오류)", "" if ta is not None else "없음", "" if tb is not None else "없음"])
            continue
        skip = EXCLUDE.get(db, frozenset())
        for t in sorted(set(ta) | set(tb)):
            if t in skip:
                continue
            if t not in tb:
                prob.append([f"{db}.{t}", "표가 빠짐", "있음", "없음"])
            elif t not in ta:
                prob.append([f"{db}.{t}", "새 표", "없음", "있음"])
            elif ta[t] != tb[t]:
                prob.append([f"{db}.{t}", "쓰기 카운터 다름(ins·upd·del)", ",".join(map(str, ta[t])), ",".join(map(str, tb[t]))])
    return ("pass" if not prob else "fail"), prob


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("snapshot", "compare"):
        s = sub.add_parser(name)
        s.add_argument("--db-env", action="append", required=True, help="접속 URL 환경변수 이름(DB 마다 한 번, 값은 출력 안 함)")
        s.add_argument("--env-file", type=Path, default=None)
        s.add_argument("--deadline", type=float, default=60.0, help="전체 시간 제한(초, 기본 60)")
        if name == "snapshot":
            s.add_argument("--out", type=Path, required=True)
        else:
            s.add_argument("--baseline", type=Path, required=True)
            s.add_argument("--result-out", type=Path, default=None)
            s.add_argument("--night-out", type=Path, default=None, help="밤에 읽은 값도 남길 때")
    a = p.parse_args(argv)
    snap = take(a.db_env, a.env_file, deadline_s=a.deadline)
    if a.cmd == "snapshot":
        write_json(a.out, snap)
        bad = snap["timed_out"] or snap["errors"] or set(REQUIRED_DBS) - {role(x) for x in snap["dbs"]}
        print(f"스냅샷: DB {sorted(snap['dbs'])} · {snap['elapsed_s']}초 → {a.out}" + (" · 불완전(종료 코드 1)" if bad else ""))
        return 1 if bad else 0
    try:
        day = read_json(a.baseline)
    except (OSError, ValueError):
        day = None
    if a.night_out:
        write_json(a.night_out, snap)
    status, prob = compare_snaps(day, snap)
    res = {"kind": KIND + "_result", "status": status, "compared_at": now_iso(),
           "baseline_measured_at": (day or {}).get("measured_at"), "night_measured_at": snap.get("measured_at"),
           "elapsed_s": snap.get("elapsed_s"), "dbs": sorted(snap.get("dbs") or {}), "problems": prob,
           "excluded": {k: sorted(v) for k, v in EXCLUDE.items()}}
    if a.result_out:
        write_json(a.result_out, res)
    print(f"가벼운 비교: {'통과' if status == 'pass' else '실패'} · 문제 {len(prob)} · {snap.get('elapsed_s')}초")
    for row in prob[:30]:
        print("  " + " | ".join(row))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
