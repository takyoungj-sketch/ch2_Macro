"""집합 2단계 — 밤 점검 창의 「가벼운 비교」(읽기 전용, prod_sync_check 와 별도). 런북 3·6.1.

낮 무거운 동기화 확인(prod_sync_check --allow-heavy) 때 세 DB 의 쓰기 카운터를 기록해 두고, 밤 점검 모드 ON 뒤 다시 읽어
「낮 이후 운영 전용 표 밖에서 쓰기가 있었는가」를 본다. 행을 읽지 않고 통계 뷰만 읽으므로 몇 초면 끝난다.

  snapshot : DB 마다 pg_stat_user_tables(n_tup_ins·n_tup_upd·n_tup_del) 전 표 + pg_stat_database.stats_reset → JSON.
             --confirmed-at(동결을 확인한 시각, 이 명령을 실행하는 기계의 UTC)부터 90초가 안 됐으면 DB 를 읽지 않고 종료 1.
             읽기마다 트랜잭션을 새로 열고 pg_stat_clear_snapshot() 을 친 뒤 10초 간격으로 두 번 읽는다.
             종료 코드 1: 90초 미만, 시간 초과·DB 누락, track_counts 가 on 이 아님, 두 번 읽기가 다름(stable 아님),
             카운터 조회 실패·누락(tables 가 비거나 stats_reset 을 못 읽음).
  compare  : 낮 JSON(--baseline) ↔ 지금 다시 읽은 값. --confirmed-at(요청 0 을 확인한 시각)부터 90초가
             안 됐으면 DB 를 읽지 않고 종료 1. 그 외 실패(종료 코드 1) 조건 — 하나라도:
             · 운영 전용 표(EXCLUDE: 집합 3 + 임대 1 + 복합 qa_audit_run 1) 밖 표의 세 값 중 하나라도 다름
             · stats_reset 이 바뀜(카운터가 초기화돼 비교할 수 없음)
             · 표가 빠짐(낮에 있던 표가 지금 없음) 또는 새 표가 생김
             · 필요한 DB(collective_stats·rent_stats·built_stats) 가 낮 또는 지금 기록에 없음
             · 전체가 --deadline(기본 60초) 안에 끝나지 않음 — 쿼리 statement_timeout 과 별도로, 접속이 멈춰도 전체를 그 시각에 끊는다
             · track_counts 가 on 이 아님
             · 한 DB 를 10초 간격으로 두 번 읽었는데 값이 다름(통계가 아직 반영 중) — 같을 때만 비교한다
             통과만 종료 코드 0. (이 도구는 「검증 못 함」(2)을 두지 않는다 — 밤에는 못 본 것도 실패로 멈춘다)
             순서 판정에 쓰는 measured_at·compared_at 은 로컬 PC 시계 UTC 이고 출처는 local 이다.
             DB now() 는 server_now(출처 server)로만 남기고 순서 판정에 쓰지 않는다.
             서버에서 실행할 때는 --order-clock defer 로 비워 두고, 로컬 PC 에서 stamp-local 로 찍는다.

  python prod_stat_compare.py snapshot --confirmed-at 2026-11-17T01:00:00+00:00 \\
      --db-env COLLECTIVE_DATABASE_URL --db-env RENT_DATABASE_URL --db-env BUILT_DATABASE_URL \\
      --env-file /opt/ch2_Macro/backend/.env --out /var/backups/ch2/p2/stat_day.json
  python prod_stat_compare.py compare --confirmed-at 2026-11-17T17:10:00+00:00 \\
      --baseline /var/backups/ch2/p2/stat_day.json --db-env … (같은 셋) --env-file … \\
      --result-out /var/backups/ch2/p2/stat_night_result.json

출력은 표 이름·숫자만(행 값 없음). 접속 정보는 출력하지 않는다. pipeline 을 쓰지 않는다(서버 backend venv 로 실행).
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _common import (  # noqa: E402
    StampError, Timed, _parse_utc, db_name, db_url, now_iso, read_json, ro_conn, stamp_local, write_json,
)

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
TRACK_SQL = "SHOW track_counts"
SETTLE_S = 10.0
QUIET_S = 90.0


def _call_with_deadline(fn, timeout_s: float):
    """fn 을 데몬 스레드에서 돌리고 timeout_s 안에 안 끝나면 (False, None). 접속·DNS 정지도 여기서 끊는다."""
    box: dict = {}
    err: dict = {}

    def run():
        try:
            box["v"] = fn()
        except BaseException as ex:  # noqa: BLE001  — SystemExit(접속 정보 없음)도 호출한 쪽으로
            err["e"] = ex

    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(max(0.0, timeout_s))
    if th.is_alive():
        return False, None
    if "e" in err:
        raise err["e"]
    return True, box.get("v")


def _new_stat_txn(conn) -> None:
    """통계 뷰는 트랜잭션 안의 첫 조회로 고정된다. 읽기 전에 트랜잭션을 끝내고 스냅샷을 비운다."""
    from sqlalchemy import text

    if conn.in_transaction():
        conn.commit()
    conn.execute(text("SELECT pg_stat_clear_snapshot()"))
    conn.commit()


def read_db(conn, t: Timed, timeout_ms: int) -> dict:
    """한 DB 의 카운터. 쿼리가 실패·시간 초과면 tables/stats_reset 이 None(→ 비교에서 실패).
    server_now 는 DB now() 참고값이다. 순서 판정에는 쓰지 않는다.
    호출마다 새 트랜잭션에서 읽고, 그 전에 pg_stat_clear_snapshot() 을 친다."""
    from sqlalchemy import text

    _new_stat_txn(conn)
    rows = t.run(conn, "pg_stat_user_tables", STAT_SQL, timeout_ms=timeout_ms, fetch="all")
    reset = t.run(conn, "pg_stat_database.stats_reset", RESET_SQL, timeout_ms=timeout_ms, fetch="one")
    track = t.run(conn, "track_counts", TRACK_SQL, timeout_ms=timeout_ms, fetch="scalar")
    try:
        server_now = conn.execute(text("SELECT now()::text")).scalar()
    except Exception:  # noqa: BLE001
        conn.rollback()
        server_now = None
    return {"db": db_name(conn), "measured_at": None, "measured_at_source": None,
            "server_now": None if server_now is None else str(server_now), "server_now_source": "server",
            "track_counts": None if track is None else str(track),
            "stats_reset": None if reset is None else str(reset[0]),
            "stats_reset_ok": reset is not None,
            "tables": None if rows is None else {r[0]: [int(r[1]), int(r[2]), int(r[3])] for r in rows}}


def judge_stable(first: dict, second: dict) -> dict:
    """두 번 읽은 값이 같을 때만 stable. track_counts 는 두 번째 읽기 값으로 남긴다."""
    out = dict(second)
    out["stable"] = bool(first.get("tables") is not None and first.get("tables") == second.get("tables")
                         and first.get("stats_reset") == second.get("stats_reset"))
    out["track_counts_ok"] = str(out.get("track_counts")).lower() == "on"
    return out


def read_stable(conn, t: Timed, timeout_ms: int, sleeper=time.sleep, settle_s: float = SETTLE_S) -> dict:
    """요청이 끝난 뒤 settle_s 초 간격으로 한 DB 를 두 번 읽는다. 표마다 반복하지 않는다.
    각 read_db 가 트랜잭션을 새로 열고 pg_stat_clear_snapshot() 을 친다. 같은 트랜잭션에 두면 두 번째도 첫 스냅샷이다."""
    first = read_db(conn, t, timeout_ms)
    sleeper(settle_s)
    second = read_db(conn, t, timeout_ms)
    return judge_stable(first, second)


def _finish_clock(snap: dict, order_clock: str) -> dict:
    if order_clock == "local":
        snap["measured_at"] = now_iso()
        snap["measured_at_source"] = "local"
    return snap


def take(db_envs: list[str], env_file: Path | None, *, deadline_s: float, clock=time.monotonic, reader=None,
         opener=None, sleeper=time.sleep, settle_s: float = SETTLE_S, order_clock: str = "local") -> dict:
    """여러 DB 를 차례로 읽는다. 전체 deadline 을 넘기면 남은 DB 는 읽지 않고 timed_out=True.
    실제 접속은 스레드 제한으로 끊는다(statement_timeout 은 쿼리에만 걸린다). reader 를 주면 테스트용으로 그 경로를 쓴다."""
    t0 = clock()
    out = {"kind": KIND, "measured_at": None, "measured_at_source": None, "deadline_s": deadline_s, "dbs": {},
           "timed_out": False, "errors": []}
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
                def work(env=env, left=left):
                    if opener is not None:
                        return opener(env, left)
                    t = Timed()
                    with ro_conn(db_url(env, env_file)) as conn:
                        snap = read_stable(conn, t, int(max(1, left) * 1000), sleeper, settle_s)
                        snap["_timings"] = t.log
                        return snap

                ok, snap = _call_with_deadline(work, left)
                if not ok:
                    out["timed_out"] = True
                    out["errors"].append(f"{env}: 시간 초과로 끊음")
                    continue
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
    _attach_file_server_now(out)
    return _finish_clock(out, order_clock)


def _attach_file_server_now(out: dict) -> None:
    """파일 단위 server_now = 이번 읽기 중 가장 이른 DB now(). 하나라도 없으면 비워 둔다(stamp-local 이 거절)."""
    stamps = []
    for v in (out.get("dbs") or {}).values():
        if not isinstance(v, dict) or v.get("server_now_source") != "server" or not v.get("server_now"):
            return
        if _parse_utc(v.get("server_now")) is None:
            return
        stamps.append(str(v["server_now"]))
    if not stamps:
        return
    out["server_now"] = min(stamps, key=_parse_utc)
    out["server_now_source"] = "server"


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
        if str(a.get("track_counts")).lower() != "on" or str(b.get("track_counts")).lower() != "on":
            prob.append([db, "track_counts 가 on 이 아님", str(a.get("track_counts")), str(b.get("track_counts"))])
        if a.get("stable") is False or b.get("stable") is False:
            prob.append([db, "카운터가 두 번 읽기에서 다름", "", ""])
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


class QuietError(RuntimeError):
    pass


def utc_now():
    import datetime as _dt

    return _dt.datetime.now(_dt.timezone.utc)


def quiet_gap_s(confirmed_at: str, now) -> float:
    """확인 시각부터 now 까지 초. 시간대가 없거나 형식이 아니면 QuietError."""
    stamped = _parse_utc(confirmed_at)
    if stamped is None:
        raise QuietError("확인 시각을 UTC(시간대 포함)로 읽지 못함")
    return (now - stamped).total_seconds()


def snapshot_incomplete(snap: dict) -> bool:
    """스냅샷을 기준으로 쓸 수 없으면 True. track_counts off, 두 번 읽기 불일치, 카운터 실패·누락을 포함한다."""
    if snap.get("timed_out") or snap.get("errors"):
        return True
    if set(REQUIRED_DBS) - {role(x) for x in (snap.get("dbs") or {})}:
        return True
    for db in (snap.get("dbs") or {}).values():
        if not isinstance(db, dict):
            return True
        if str(db.get("track_counts")).lower() != "on":
            return True
        if db.get("stable") is False:
            return True
        if db.get("tables") is None or not db.get("stats_reset_ok", True):
            return True
    return False


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("snapshot", "compare"):
        s = sub.add_parser(name)
        s.add_argument("--db-env", action="append", required=True, help="접속 URL 환경변수 이름(DB 마다 한 번, 값은 출력 안 함)")
        s.add_argument("--env-file", type=Path, default=None)
        s.add_argument("--deadline", type=float, default=60.0, help="전체 시간 제한(초, 기본 60). 쿼리 제한과 별도로 접속까지 끊는다")
        s.add_argument("--confirmed-at", required=True,
                       help="요청 0 또는 동결을 확인한 시각(이 명령을 실행하는 기계의 UTC, 시간대 포함). 90초 미만이면 종료 1")
        s.add_argument("--order-clock", choices=["local", "defer"], default="local",
                       help="local=끝난 시각을 로컬 PC UTC 로 기록. defer=비워 두고 stamp-local(서버에서 실행할 때)")
        if name == "snapshot":
            s.add_argument("--out", type=Path, required=True)
        else:
            s.add_argument("--baseline", type=Path, required=True)
            s.add_argument("--result-out", type=Path, default=None)
            s.add_argument("--night-out", type=Path, default=None, help="밤에 읽은 값도 남길 때")
    st = sub.add_parser("stamp-local", help="서버에서 만든 JSON 에 로컬 PC UTC 시각을 찍는다(순서 판정용)")
    st.add_argument("--file", type=Path, required=True)
    st.add_argument("--field", action="append", required=True)
    a = p.parse_args(argv)
    if a.cmd == "stamp-local":
        try:
            write_json(a.file, stamp_local(read_json(a.file), *a.field))
        except (OSError, ValueError, StampError) as ex:
            print(f"중단: {ex}", file=sys.stderr)
            return 2
        print(f"local 시각 기록: {', '.join(a.field)} → {a.file}")
        return 0
    try:
        gap = quiet_gap_s(a.confirmed_at, utc_now())
    except QuietError as ex:
        print(f"중단: {ex}", file=sys.stderr)
        return 1
    if gap < QUIET_S:
        print(f"중단: 확인 시각부터 {gap:.1f}초. 90초 미만", file=sys.stderr)
        return 1
    snap = take(a.db_env, a.env_file, deadline_s=a.deadline, order_clock=a.order_clock)
    if a.cmd == "snapshot":
        write_json(a.out, snap)
        bad = snapshot_incomplete(snap)
        print(f"스냅샷: DB {sorted(snap['dbs'])} · {snap['elapsed_s']}초 → {a.out}" + (" · 불완전(종료 코드 1)" if bad else ""))
        return 1 if bad else 0
    try:
        day = read_json(a.baseline)
    except (OSError, ValueError):
        day = None
    if a.night_out:
        write_json(a.night_out, snap)
    status, prob = compare_snaps(day, snap)
    res = {"kind": KIND + "_result", "status": status,
           "compared_at": now_iso() if a.order_clock == "local" else None,
           "compared_at_source": "local" if a.order_clock == "local" else None,
           "baseline_measured_at": (day or {}).get("measured_at"),
           "baseline_measured_at_source": (day or {}).get("measured_at_source"),
           "night_measured_at": snap.get("measured_at"),
           "night_measured_at_source": snap.get("measured_at_source"),
           "server_now": snap.get("server_now"), "server_now_source": snap.get("server_now_source"),
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
