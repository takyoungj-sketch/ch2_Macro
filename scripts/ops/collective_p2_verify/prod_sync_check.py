"""집합 2단계 운영 확인 — 시작 전 동기화(로컬 = 운영) 확인(읽기 전용).

promote 는 DB 를 통째로 바꾸므로, 로컬에 반영하기 **전에** 로컬과 운영이 같은 상태여야 차이가 이번 변경분뿐이다.
  snapshot : 한 DB 의 public 표마다 행 수 · 최신 as_of_month(있으면) · 원장 표의 최근 4개월 계약월별 거래 수를 JSON 으로.
  compare  : 두 JSON 비교. 다르면 종료 코드 1.

10초 규칙(T 지시): 큰 표(통계상 행 수 > --heavy-rows, 기본 200만)의 정확한 행 수·as_of·월별 거래 수는 10초를 넘을 수 있다.
  기본은 실행하지 않고 「승인 필요」로 표시하며 통계 추정 행 수(reltuples)만 남긴다(비교 대상 아님).
  T 승인 뒤 --allow-heavy 로 실행한다(쿼리마다 --heavy-timeout, 기본 300초). 가벼운 쿼리는 10초 제한.
예상 소요: 기본(가벼운 것만) DB 마다 1분 안 · --allow-heavy collective 약 3~6분 · rent 약 5~10분 · built 1분(로컬 추정, 운영은 최대 2배).

사용:
  python prod_sync_check.py snapshot --db-env COLLECTIVE_DATABASE_URL --env-file backend/.env --out local_sync_collective.json
  python prod_sync_check.py snapshot --db-env COLLECTIVE_DATABASE_URL --env-file /opt/ch2_Macro/backend/.env --out prod_sync_collective.json
  python prod_sync_check.py compare local_sync_collective.json prod_sync_collective.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _common import (  # noqa: E402
    EXIT, LIGHT_MS, PASS, DIFF, STATUS_KO, UNVERIFIED, Timed, db_name, db_url, md_table, read_json, ro_conn,
    finalize_result, make_result, now_iso, snapshot_failures, table_columns, write_json,
)

LEDGERS = ("collective_transactions", "collective_commercial_transactions", "rent_transactions", "built_transactions")
HEAVY_ROWS = 2_000_000
# 이 표가 양쪽 모두 없으면 「검증 못 함」(한쪽만 없으면 「차이」)
REQUIRED = {
    "collective_stats": ["collective_transactions", "collective_commercial_transactions", "collective_building_stats",
                         "collective_building_rolling_stats", "collective_building_annual_stats",
                         "collective_building_attributes", "market_stats"],
    "rent_stats": ["rent_transactions", "rent_building_stats", "rent_building_rolling_stats", "rent_sale_building_map"],
    "built_stats": ["built_transactions", "built_scope_stats"],
}
# 운영 API 가 직접 쓰는 표(런북 2.5) — 차이가 나도 멈춤 사유가 아니라 promote 전 합칠 대상
PROD_WRITTEN = ("collective_building_geocodes", "collective_commercial_map_geocodes", "qa_audit_run", "rent_building_geocodes")


def snapshot(conn, *, allow_heavy: bool, heavy_ms: int = 300_000, heavy_rows: int = HEAVY_ROWS) -> dict:
    t = Timed()
    out: dict = {"db": db_name(conn), "measured_at": now_iso(), "tables": {}}
    stats = t.run(conn, "표 목록·추정 행 수", """
        SELECT c.relname, greatest(c.reltuples, 0)::bigint
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') ORDER BY 1""") or []
    for tb, est in stats:
        heavy = int(est) > heavy_rows
        rec: dict = {"est_rows": int(est), "heavy": heavy}
        if heavy and not allow_heavy:
            rec["status"] = "승인 필요(10초 초과 예상) — 추정 행 수만"
            out["tables"][tb] = rec
            continue
        ms = heavy_ms if heavy else LIGHT_MS
        rec["rows"] = t.run(conn, f"{tb} 행 수", f'SELECT count(*) FROM "{tb}"', fetch="scalar", timeout_ms=ms)
        cols = table_columns(conn, tb)
        if "as_of_month" in cols:
            v = t.run(conn, f"{tb} 최신 as_of", f'SELECT max(as_of_month) FROM "{tb}"', fetch="scalar", timeout_ms=ms)
            rec["max_as_of_month"] = None if v is None else str(v)
        if tb in LEDGERS and "contract_date" in cols:
            rows = t.run(conn, f"{tb} 최근 계약월", f"""
                SELECT to_char(date_trunc('month', contract_date), 'YYYY-MM'), count(*) FROM "{tb}"
                WHERE contract_date >= (SELECT date_trunc('month', max(contract_date)) - interval '3 months' FROM "{tb}")
                GROUP BY 1 ORDER BY 1""", timeout_ms=ms)
            rec["recent_months"] = None if rows is None else {m: int(n) for m, n in rows}
        if rec["rows"] is None or ("recent_months" in rec and rec["recent_months"] is None):
            rec["status"] = "시간 초과(승인 필요)"
        out["tables"][tb] = rec
    out["_timings"] = t.log
    return out


def compare(a: dict, b: dict, *, allowed: tuple[str, ...] = PROD_WRITTEN) -> dict:
    """{status, diff, allowed_diff, unverified}. 큰 표를 건너뛰었거나(승인 필요·시간 초과) 필수 표가 양쪽에 없으면 검증 못 함."""
    diff, allowed_diff, unv = [], [], []
    for tb in sorted(set(a["tables"]) | set(b["tables"])):
        x, y = a["tables"].get(tb), b["tables"].get(tb)
        if x is None or y is None:
            (allowed_diff if tb in allowed else diff).append((tb, "표", "있음" if x else "없음", "있음" if y else "없음"))
            continue
        if "status" in x or "status" in y:
            unv.append((tb, x.get("status") or y.get("status")))
        for k in ("rows", "max_as_of_month", "recent_months"):
            if k in x and k in y and x[k] is not None and y[k] is not None and x[k] != y[k]:
                (allowed_diff if tb in allowed else diff).append((tb, k, x[k], y[k]))
    for tb in REQUIRED.get(a.get("db"), []) + REQUIRED.get(b.get("db"), []):
        if tb not in a["tables"] and tb not in b["tables"] and (tb, "필수 표 없음") not in unv:
            unv.append((tb, "필수 표 없음"))
    status = DIFF if diff else UNVERIFIED if unv else PASS
    return {"status": status, "diff": diff, "allowed_diff": allowed_diff, "unverified": unv}


def result_of(left: dict, right: dict, r: dict) -> dict:
    """compare 결과 → 결과 파일 객체. 스냅샷 쿼리 실패·빈 스냅샷도 기록하고 validate_result 를 거친다."""
    unv = [t for t, _ in r["unverified"]]
    for s in (left, right):
        if not s.get("tables"):
            unv.append(f"{s.get('db')}: 스냅샷에 표가 없음")
    obj = make_result(kind="prod_sync_check", status=r["status"], left_db=left.get("db"), right_db=right.get("db"),
                      diff=len(r["diff"]), unverified=unv, failures=snapshot_failures(left, right),
                      detail={"allowed_diff": len(r["allowed_diff"])}, snapshots=(left, right))
    return finalize_result(obj, [left.get("db")])


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("--db-env", required=True)
    s.add_argument("--env-file", type=Path, default=None)
    s.add_argument("--allow-heavy", action="store_true", help="T 승인 뒤에만: 큰 표 정확한 행 수·월별 거래 수")
    s.add_argument("--heavy-timeout", type=int, default=300)
    s.add_argument("--heavy-rows", type=int, default=HEAVY_ROWS)
    s.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("compare")
    c.add_argument("left", type=Path)
    c.add_argument("right", type=Path)
    c.add_argument("--result-out", type=Path, default=None,
                   help="결과 파일(실제 적용 모드 --sync-result 로 넘김). 통과일 때만 실제 적용이 허용된다")
    a = p.parse_args(argv)
    if a.cmd == "snapshot":
        with ro_conn(db_url(a.db_env, a.env_file)) as conn:
            snap = snapshot(conn, allow_heavy=a.allow_heavy, heavy_ms=a.heavy_timeout * 1000, heavy_rows=a.heavy_rows)
        write_json(a.out, snap)
        need = [k for k, v in snap["tables"].items() if "status" in v]
        print(f"{snap['db']}: 표 {len(snap['tables'])} · 승인 필요/시간 초과 {len(need)} · "
              f"{sum(x['sec'] for x in snap['_timings']):,.0f}초 → {a.out}")
        if need:
            print("승인 필요: " + ", ".join(need))
        return 0
    left, right = read_json(a.left), read_json(a.right)
    r = compare(left, right)
    res = result_of(left, right, r)
    r["status"] = res["status"]
    print(f"{left['db']} vs {right['db']}: {STATUS_KO[r['status']]} — 차이 {len(r['diff'])} · "
          f"운영 전용 표 차이(허용) {len(r['allowed_diff'])} · 검증 못 함 {len(r['unverified'])}")
    if r["diff"]:
        print(md_table(r["diff"], ["표", "항목", "왼쪽", "오른쪽"]))
    if r["allowed_diff"]:
        print("운영 전용 표(promote 전 합칠 대상, 런북 6.1):")
        print(md_table(r["allowed_diff"], ["표", "항목", "왼쪽", "오른쪽"]))
    if r["unverified"]:
        print("검증 못 함(--allow-heavy 필요·필수 표 없음):")
        print(md_table(r["unverified"], ["표", "사유"]))
    if res.get("validation"):
        print("결과 검증(ops_guards.validate_result): " + "; ".join(res["validation"]))
    if a.result_out:
        write_json(a.result_out, res)
    print(f"종료 코드 {EXIT[r['status']]} (0 통과 · 1 차이 · 2 검증 못 함)")
    return EXIT[r["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
