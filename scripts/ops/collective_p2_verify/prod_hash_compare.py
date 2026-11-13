"""집합 2단계 운영 확인 — 반영(promote) 뒤 로컬과 운영의 대상 표가 행 단위로 같은지(읽기 전용).

두 단계로 쓴다(운영 서버는 로컬 DB 에 닿지 않으므로 각자 스냅샷을 만들고 파일로 비교):
  snapshot  : 한 DB 의 대상 표마다 조각별 (행 수, 행 해시)를 JSON 으로 쓴다.
  compare   : 두 JSON 을 비교해 다른 표·조각을 낸다. 다르면 종료 코드 1.

행 해시 = md5(정렬한 행 md5 이어붙이기), 행 md5 = md5((to_jsonb(행) - 제외 열)::text).
큰 표는 조각으로 나눈다: building_key 가 있으면 키 첫 글자(16진 16조각), 없고 정수 id 가 있으면 id 범위 N조각, 둘 다 없으면 통째.
조각마다 쿼리 하나·시간 제한 하나(--timeout, 기본 600초). 출력에는 표 이름·조각 이름·건수·해시만 있다(행 값 없음).

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

from _common import Timed, db_name, db_url, md_table, read_json, ro_conn, table_columns, table_exists, write_json  # noqa: E402

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
    ],
    "rent_stats": ["rent_transactions", "rent_building_stats", "rent_building_rolling_stats", "rent_sale_building_map",
                   "rent_building_geocodes", "rent_building_key_map"],
    "built_stats": ["built_transactions", "built_scope_stats"],
}
HEX = "0123456789abcdef"


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


def snapshot(conn, tables: list[str], *, exclude: list[str], id_chunks: int = 16, timeout_ms: int = 600_000) -> dict:
    t = Timed()
    out: dict = {"db": db_name(conn), "exclude": exclude, "tables": {}}
    minus = "".join(f" - '{c}'" for c in exclude)
    for tb in tables:
        if not table_exists(conn, tb):
            out["tables"][tb] = None
            continue
        cols = table_columns(conn, tb)
        parts = {}
        for name, cond in _chunks(conn, t, tb, cols, id_chunks, timeout_ms):
            r = t.run(conn, f"{tb} {name}",
                      f'SELECT count(*), md5(coalesce(string_agg(h, \'\' ORDER BY h COLLATE "C"), \'\')) '
                      f'FROM (SELECT md5((to_jsonb(x){minus})::text) h FROM "{tb}" x WHERE {cond}) z',
                      fetch="one", timeout_ms=timeout_ms)
            parts[name] = None if r is None else [int(r[0]), r[1]]
        out["tables"][tb] = parts
    out["_timings"] = t.log
    return out


def compare(a: dict, b: dict) -> list[tuple]:
    diff = []
    for tb in sorted(set(a["tables"]) | set(b["tables"])):
        x, y = a["tables"].get(tb), b["tables"].get(tb)
        if x is None or y is None:
            if x != y:
                diff.append((tb, "—", "표 없음" if x is None else "있음", "표 없음" if y is None else "있음"))
            continue
        for part in sorted(set(x) | set(y)):
            px, py = x.get(part), y.get(part)
            if px is None or py is None or px != py:
                diff.append((tb, part, px[0] if px else "—", py[0] if py else "—"))
    if a.get("exclude") != b.get("exclude"):
        diff.append(("(설정)", "제외 열 다름", a.get("exclude"), b.get("exclude")))
    return diff


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
    s.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("compare")
    c.add_argument("left", type=Path)
    c.add_argument("right", type=Path)
    a = p.parse_args(argv)
    if a.cmd == "snapshot":
        with ro_conn(db_url(a.db_env, a.env_file)) as conn:
            name = db_name(conn)
            tables = [x for x in a.tables.split(",") if x] or TARGETS.get(name)
            if not tables:
                raise SystemExit(f"기본 대상 표가 없는 DB: {name} — --tables 로 지정")
            snap = snapshot(conn, tables, exclude=[x for x in a.exclude_cols.split(",") if x],
                            id_chunks=a.id_chunks, timeout_ms=a.timeout * 1000)
        write_json(a.out, snap)
        fails = [x for x in snap["_timings"] if not x["ok"]]
        print(f"{name}: 표 {len(tables)} · 조각 쿼리 {len(snap['_timings'])} · 실패 {len(fails)} · "
              f"{sum(x['sec'] for x in snap['_timings']):,.0f}초 → {a.out}")
        return 1 if fails else 0
    left, right = read_json(a.left), read_json(a.right)
    diff = compare(left, right)
    print(f"{left['db']} vs {right['db']}: 다른 표·조각 {len(diff)}")
    if diff:
        print(md_table(diff, ["표", "조각", "왼쪽 행", "오른쪽 행"]))
    return 1 if diff else 0


if __name__ == "__main__":
    raise SystemExit(main())
