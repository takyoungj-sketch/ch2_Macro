"""집합 2단계 운영 확인 — 반영(promote) 뒤 로컬과 운영의 대상 표가 행 단위로 같은지(읽기 전용).

두 단계로 쓴다(운영 서버는 로컬 DB 에 닿지 않으므로 각자 스냅샷을 만들고 파일로 비교):
  snapshot  : 한 DB 의 대상 표마다 조각별 (행 수, 행 해시)를 JSON 으로 쓴다.
  compare   : 두 JSON 을 비교해 다른 표·조각을 낸다. 다르면 종료 코드 1.

행 해시 = md5(정렬한 행 md5 이어붙이기), 행 md5 = md5((to_jsonb(행) - 제외 열)::text).
큰 표는 조각으로 나눈다: building_key 가 있으면 키 첫 글자(16진 16조각), 없고 정수 id 가 있으면 id 범위 N조각, 둘 다 없으면 통째.
조각마다 쿼리 하나·시간 제한 하나(--timeout, 기본 600초). 출력에는 표 이름·조각 이름·건수·해시만 있다(행 값 없음).

두 가지 방식(--mode):
  hash (기본): 위 행 해시. 로컬 PG18·운영 PG16 이 같은 행에 같은 해시를 내는지는 미검증이므로, 런북 3절에서 먼저
               「이미 같다고 알려진 작은 표」(region_codes·region_code_history)로 snapshot·compare 해 본다.
               같으면 hash 를 그대로 쓰고, 다르면 sums 로 바꾼다(아래 pgcheck 가 둘 다 재서 판정).
  sums       : 조각마다 행 수 + 열마다 값 있는 행 수 + 숫자 열 합계(numeric 로 바꿔 더함) + 글자 열 길이 합.
               해시보다 약하지만 PG 버전·정렬 규칙·jsonb 표기에 영향받지 않는다.
  pgcheck    : 같은 작은 표로 hash·sums 를 한 번에 떠 JSON 하나로 쓴다. 두 쪽 pgcheck JSON 을 compare 하면
               「hash 같음 → hash 사용 / hash 만 다름 → sums 사용 / sums 도 다름 → 표가 실제로 다름(동기화 문제)」을 출력.

예상 소요(로컬 c8 실측: 전 표 해시 collective 24분 · rent 32분 · built 1분, 운영은 최대 2배):
  기본 대상 표(아래 TARGETS) 기준 collective 약 25~50분 · rent 약 30~65분 · built 1~2분.

사용:
  python prod_hash_compare.py snapshot --db-env COLLECTIVE_DATABASE_URL --env-file backend/.env --out local_collective.json
  python prod_hash_compare.py snapshot --db-env COLLECTIVE_DATABASE_URL --env-file /opt/ch2_Macro/backend/.env --out prod_collective.json
  python prod_hash_compare.py compare local_collective.json prod_collective.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _common import (  # noqa: E402
    EXIT, PASS, DIFF, STATUS_KO, UNVERIFIED, Timed, db_name, db_url, md_table, read_json, ro_conn, table_columns,
    finalize_result, make_result, now_iso, snapshot_failures, table_exists, write_json,
)

# 이번 반영이 바꾸는 표(원장·부속·통계·연결표·보존 표). 보존 표(_p2_before)는 promote 로 같이 올라가므로 함께 비교한다.
TARGETS = {
    "collective_stats": [
        "collective_transactions", "collective_commercial_transactions", "commercial_clusters",
        "collective_building_stats", "collective_building_rolling_stats", "collective_building_annual_stats",
        "collective_presale_lifetime_stats", "market_stats", "market_annual_stats",
        "collective_commercial_cluster_stats", "collective_commercial_cluster_rolling_stats",
        "collective_commercial_cluster_annual_stats", "collective_building_attributes", "builder_master",
        "collective_building_assessed_land_price", "collective_building_geocodes", "new_apartment_complex_year",
        "collective_building_key_map", "collective_cluster_key_map", "p2_migration_log",
        "collective_building_key_c2_units",            # C-2 판정 표
    ],
    "rent_stats": ["rent_transactions", "rent_building_stats", "rent_building_rolling_stats", "rent_sale_building_map",
                   "rent_building_geocodes", "rent_building_key_map"],
    "built_stats": ["built_transactions", "built_scope_stats"],
}
HEX = "0123456789abcdef"
# 보존 표(키 이전 전 행·annual 정리 전 행·연결표 사본)도 기본 대상 — 이름 꼴로 찾아 더한다
PRESERVE_LIKE = r"%\_p2\_before"
PG_CHECK_TABLES = ["region_codes", "region_code_history"]   # 세 DB 모두 있고 작으며 토지에서 복사해 오는 표
NUMERIC_TYPES = {"smallint", "integer", "bigint", "numeric", "real", "double precision"}


def _chunks(conn, t: Timed, table: str, cols: list[str], id_chunks: int, timeout_ms: int):
    if "building_key" in cols:
        # 정렬 규칙을 "C" 로 고정(로컬 PG18·운영 PG16 의 기본 정렬 규칙이 달라도 같은 조각이 되게)
        out = [(f"bk<{HEX[0]}", "(building_key IS NULL OR building_key COLLATE \"C\" < '0')")]
        for i, h in enumerate(HEX):
            hi = HEX[i + 1] if i + 1 < len(HEX) else None
            cond = f"building_key COLLATE \"C\" >= '{h}'" + (f" AND building_key COLLATE \"C\" < '{hi}'" if hi else "")
            out.append((f"bk={h}", cond))
        return out
    if "id" in cols:
        r = t.run(conn, f"{table} id 범위", f'SELECT min(id), max(id) FROM "{table}"', fetch="one", timeout_ms=timeout_ms)
        if r is None or r[0] is None:
            return [("all", "true")]
        lo, hi = int(r[0]), int(r[1])
        step = max((hi - lo + 1) // id_chunks + 1, 1)
        return [(f"id{a}", f"id >= {a} AND id < {a + step}") for a in range(lo, hi + 1, step)] + [("id null", "id IS NULL")]
    return [("all", "true")]


def _col_types(conn, table: str) -> dict[str, str]:
    from sqlalchemy import text

    return {r[0]: r[1] for r in conn.execute(text(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='public' AND table_name=:t "
        "ORDER BY ordinal_position"), {"t": table})}


def sums_sql(table: str, types: dict[str, str], exclude: list[str], cond: str) -> tuple[str, list[str]]:
    """행 수·열마다 값 있는 행 수·숫자 열 합계·글자 열 길이 합 — 결과 칸 이름 목록과 함께."""
    parts, names = ["count(*)"], ["rows"]
    for c, ty in types.items():
        if c in exclude:
            continue
        q = f'"{c}"'
        parts.append(f"count({q})")
        names.append(f"{c}.n")
        if ty in NUMERIC_TYPES:
            parts.append(f"coalesce(sum({q}::numeric), 0)::text")
            names.append(f"{c}.sum")
        elif ty in ("text", "character varying", "character"):
            parts.append(f"coalesce(sum(length({q})), 0)")
            names.append(f"{c}.len")
    return f'SELECT {", ".join(parts)} FROM "{table}" WHERE {cond}', names


def snapshot(conn, tables: list[str], *, exclude: list[str], id_chunks: int = 16, timeout_ms: int = 600_000,
             mode: str = "hash") -> dict:
    t = Timed()
    out: dict = {"db": db_name(conn), "measured_at": now_iso(), "mode": mode, "exclude": exclude,
                 "requested": list(tables), "tables": {}}
    minus = "".join(f" - '{c}'" for c in exclude)
    for tb in tables:
        if not table_exists(conn, tb):
            out["tables"][tb] = None
            continue
        cols = table_columns(conn, tb)
        parts = {}
        types = _col_types(conn, tb) if mode == "sums" else {}
        for name, cond in _chunks(conn, t, tb, cols, id_chunks, timeout_ms):
            if mode == "sums":
                sql, names = sums_sql(tb, types, exclude, cond)
                r = t.run(conn, f"{tb} {name}", sql, fetch="one", timeout_ms=timeout_ms)
                parts[name] = None if r is None else dict(zip(names, (str(v) for v in r)))
                continue
            r = t.run(conn, f"{tb} {name}",
                      f'SELECT count(*), md5(coalesce(string_agg(h, \'\' ORDER BY h COLLATE "C"), \'\')) '
                      f'FROM (SELECT md5((to_jsonb(x){minus})::text) h FROM "{tb}" x WHERE {cond}) z',
                      fetch="one", timeout_ms=timeout_ms)
            parts[name] = None if r is None else [int(r[0]), r[1]]
        out["tables"][tb] = parts
    out["_timings"] = t.log
    return out


def _rows(part) -> object:
    if isinstance(part, dict):
        return part.get("rows")
    return part[0] if part else "—"


def default_tables(conn, name: str) -> list[str]:
    """기본 대상 = TARGETS[DB] + 이 DB 의 보존 표(*_p2_before)."""
    from sqlalchemy import text

    pres = [r[0] for r in conn.execute(text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE :p ORDER BY 1"),
        {"p": PRESERVE_LIKE})]
    base = list(TARGETS.get(name, []))
    return base + [t for t in pres if t not in base]


def evaluate(a: dict, b: dict) -> dict:
    """{status, diff, unverified}. 조각 쿼리 실패(시간 초과 등)·필수 표가 양쪽에 없음 → 검증 못 함. 값이 다르면 차이."""
    diff, unv = [], []
    if a.get("mode", "hash") != b.get("mode", "hash"):
        return {"status": DIFF, "diff": [("(설정)", "방식 다름", a.get("mode", "hash"), b.get("mode", "hash"))], "unverified": []}
    if a.get("exclude") != b.get("exclude"):
        diff.append(("(설정)", "제외 열 다름", a.get("exclude"), b.get("exclude")))
    # 필수 표 = DB 이름의 기본 대상(TARGETS) + 두 스냅샷이 요청한 표. 결과 JSON 의 키가 아니라 이 목록을 순회한다
    # (JSON 에서 표 하나가 빠져 있어도 「비교할 게 없어 통과」가 되지 않게).
    required = (set(TARGETS.get(a.get("db"), [])) | set(TARGETS.get(b.get("db"), []))
                | set(a.get("requested") or []) | set(b.get("requested") or []))
    for tb in sorted(required | set(a["tables"]) | set(b["tables"])):
        x, y = a["tables"].get(tb), b["tables"].get(tb)
        if tb in required and (x is None or y is None):
            where = "양쪽" if x is None and y is None else "왼쪽" if x is None else "오른쪽"
            unv.append((tb, f"필수 표 없음({where})"))
            continue
        if x is None and y is None:
            continue
        if x is None or y is None:
            diff.append((tb, "—", "표 없음" if x is None else "있음", "표 없음" if y is None else "있음"))
            continue
        for part in sorted(set(x) | set(y)):
            px, py = x.get(part, "누락"), y.get(part, "누락")
            if px is None or py is None:
                unv.append((tb, f"{part} 조각 쿼리 실패"))
            elif px != py:
                diff.append((tb, part, _rows(px) if px != "누락" else "—", _rows(py) if py != "누락" else "—"))
    status = DIFF if diff else UNVERIFIED if unv else PASS
    return {"status": status, "diff": diff, "unverified": unv}


def compare(a: dict, b: dict) -> list[tuple]:
    """차이 목록만(검증 못 함은 evaluate 로)."""
    return evaluate(a, b)["diff"]


def pg_verdict(a: dict, b: dict) -> str:
    """pgcheck JSON 두 개 → 어떤 방식을 쓸지(사람이 읽는 문장). 판정 자체는 pg_result."""
    return pg_result(a, b)["verdict"]


def pg_result(a: dict, b: dict) -> dict:
    """PG 버전 확인 결과 파일 객체. 비교할 표가 양쪽 모두 실제로 있고 쿼리 실패가 없어야 판정한다.
    hash 같음·hash 만 다름 → pass(쓸 방식 기록) / sums 도 다름 → diff / 그 밖 → unverified."""
    unv: list[str] = []
    a = {**a, "db": a.get("db") or (a.get("hash") or {}).get("db")}
    b = {**b, "db": b.get("db") or (b.get("hash") or {}).get("db")}
    for side in (a, b):
        for mode in ("hash", "sums"):
            snap = side.get(mode) or {}
            tabs = snap.get("tables") or {}
            if not tabs:
                unv.append(f"{side.get('db')} {mode}: 비교할 표가 없음")
            for t, v in tabs.items():
                if v is None:
                    unv.append(f"{side.get('db')} {mode}: {t} 표 없음")
    eh = evaluate(a.get("hash") or {"tables": {}}, b.get("hash") or {"tables": {}})
    es = evaluate(a.get("sums") or {"tables": {}}, b.get("sums") or {"tables": {}})
    unv += [f"hash {t}: {w}" for t, w in eh["unverified"]] + [f"sums {t}: {w}" for t, w in es["unverified"]]
    fails = snapshot_failures(*(s.get(m) or {} for s in (a, b) for m in ("hash", "sums")))
    if unv or fails:
        status, verdict, mode = "unverified", "검증 못 함 — 작은 표가 없거나 쿼리 실패(해시 방식을 정하지 못함)", None
    elif not eh["diff"]:
        status, verdict, mode = "pass", "hash 같음 → 해시 비교(--mode hash)를 그대로 쓴다", "hash"
    elif not es["diff"]:
        status, verdict, mode = "pass", "hash 만 다름(PG 버전·표기 차이) → --mode sums 로 비교한다", "sums"
    else:
        status, verdict, mode = "diff", "sums 도 다름 → 표가 실제로 다르다(동기화 문제, 3절로 돌아가 멈춤)", None
    obj = make_result(kind="prod_hash_pgcheck", status=status, left_db=a.get("db"), right_db=b.get("db"),
                      diff=len(es["diff"]) if status == "diff" else 0, unverified=unv, failures=fails,
                      detail={"verdict": verdict, "use_mode": mode,
                              "server_versions": [a.get("server_version"), b.get("server_version")]},
                      snapshots=tuple(s.get(m) or {} for s in (a, b) for m in ("hash", "sums")))
    out = finalize_result(obj, [a.get("db")])
    if out["status"] != "pass":
        out["use_mode"] = None
        if out["status"] == "unverified":
            out["verdict"] = "검증 못 함 — " + "; ".join(out.get("validation") or unv or fails)[:300]
    return out


def hash_result(left: dict, right: dict, r: dict) -> dict:
    unv = [f"{t}: {why}" for t, why in r["unverified"]]
    for s in (left, right):
        if not s.get("tables"):
            unv.append(f"{s.get('db')}: 스냅샷에 표가 없음")
    obj = make_result(kind="prod_hash_compare", status=r["status"], left_db=left.get("db"), right_db=right.get("db"),
                      diff=len(r["diff"]), unverified=unv, failures=snapshot_failures(left, right),
                      detail={"mode": left.get("mode", "hash")}, snapshots=(left, right))
    return finalize_result(obj, [left.get("db")])


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("--db-env", required=True, help="접속 URL 환경변수 이름(값은 출력하지 않음)")
    s.add_argument("--env-file", type=Path, default=None)
    s.add_argument("--tables", default="", help="쉼표 목록. 비우면 DB 이름의 기본 대상(TARGETS)")
    s.add_argument("--exclude-cols", default="", help="해시에서 뺄 열(예: id). promote 비교는 비움(같은 덤프라 id 도 같음)")
    s.add_argument("--id-chunks", type=int, default=16)
    s.add_argument("--timeout", type=int, default=600, help="조각 쿼리 시간 제한(초)")
    s.add_argument("--mode", choices=["hash", "sums"], default="hash")
    s.add_argument("--out", type=Path, required=True)
    g = sub.add_parser("pgcheck", help="작은 표로 hash·sums 를 함께 떠서 PG 버전 차이를 판정할 재료를 만든다")
    g.add_argument("--db-env", required=True)
    g.add_argument("--env-file", type=Path, default=None)
    g.add_argument("--tables", default=",".join(PG_CHECK_TABLES))
    g.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("compare")
    c.add_argument("left", type=Path)
    c.add_argument("right", type=Path)
    c.add_argument("--result-out", type=Path, default=None)
    a = p.parse_args(argv)
    if a.cmd == "snapshot":
        with ro_conn(db_url(a.db_env, a.env_file)) as conn:
            name = db_name(conn)
            tables = [x for x in a.tables.split(",") if x] or default_tables(conn, name)
            if not tables:
                raise SystemExit(f"기본 대상 표가 없는 DB: {name} — --tables 로 지정")
            snap = snapshot(conn, tables, exclude=[x for x in a.exclude_cols.split(",") if x],
                            id_chunks=a.id_chunks, timeout_ms=a.timeout * 1000, mode=a.mode)
        write_json(a.out, snap)
        fails = [x for x in snap["_timings"] if not x["ok"]]
        print(f"{name}: 표 {len(tables)} · 조각 쿼리 {len(snap['_timings'])} · 실패 {len(fails)} · "
              f"{sum(x['sec'] for x in snap['_timings']):,.0f}초 → {a.out}")
        if fails:
            print("조각 쿼리 실패가 있어 이 스냅샷으로는 검증 못 함(종료 코드 2)")
        return EXIT[UNVERIFIED] if fails else EXIT[PASS]
    if a.cmd == "pgcheck":
        tables = [x for x in a.tables.split(",") if x]
        with ro_conn(db_url(a.db_env, a.env_file)) as conn:
            both = {"db": db_name(conn), "pgcheck": True,
                    "hash": snapshot(conn, tables, exclude=[], mode="hash"),
                    "sums": snapshot(conn, tables, exclude=[], mode="sums")}
            both["server_version"] = str(conn.exec_driver_sql("SHOW server_version").scalar())
        write_json(a.out, both)
        print(f"{both['db']} (PG {both['server_version']}): pgcheck {', '.join(tables)} → {a.out}")
        return 0
    left, right = read_json(a.left), read_json(a.right)
    if left.get("pgcheck") and right.get("pgcheck"):
        res = pg_result(left, right)
        print(f"PG {left.get('server_version')} vs {right.get('server_version')}: {res['verdict']}")
        if a.result_out:
            write_json(a.result_out, res)
        print(f"종료 코드 {EXIT[res['status']]} (0 통과 · 1 차이 · 2 검증 못 함)")
        return EXIT[res["status"]]
    r = evaluate(left, right)
    res = hash_result(left, right, r)
    r["status"] = res["status"]
    print(f"{left['db']} vs {right['db']}: {STATUS_KO[r['status']]} — 다른 표·조각 {len(r['diff'])} · 검증 못 함 {len(r['unverified'])}")
    if r["diff"]:
        print(md_table(r["diff"], ["표", "조각", "왼쪽 행", "오른쪽 행"]))
    if r["unverified"]:
        print(md_table(r["unverified"], ["표", "사유"]))
    if res.get("validation"):
        print("결과 검증(ops_guards.validate_result): " + "; ".join(res["validation"]))
    if a.result_out:
        write_json(a.result_out, res)
    print(f"종료 코드 {EXIT[r['status']]} (0 통과 · 1 차이 · 2 검증 못 함)")
    return EXIT[r["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
