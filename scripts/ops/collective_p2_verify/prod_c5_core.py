"""집합 2단계 운영 확인 — c5 핵심 지표(읽기 전용). 반영 뒤 운영에서, 같은 것을 로컬(반영 뒤)에서 돌려 비교한다.

지표
  1 옛 시도명 행 = 0       collective_transactions · collective_commercial_transactions · built_transactions ·
                            rent_transactions · built_scope_stats(as_of)                                 [가벼움]
  2 합성 주소 = 0          collective_building_stats as_of 3/5/7 · rent_building_stats as_of            [무거움]
  3 annual 합 = 원장 합    2019~ 시도·연도·유형 불일치 0                                               [무거움]
  4 분할 키 수              연결표 행·사유별 옛/새 키 수 · 원장에 남은 분할 옛 키 행 = 0 · 임대 연결표    [가벼움~중간]
  5 커버리지                최신 as_of 5년 아파트 단지의 속성·공시지가·지오코드 비율                      [가벼움]
  6 한 키 안 동 이름 2개+   판정 목록(분할·유지) 밖 = 0 · C-2형 판정 밖 = 0                             [무거움]
출력: 표준출력 markdown + --out JSON(건수·비율만, 지번·주소·키 없음). --expect 로 로컬 결과와 비교하면 다른 지표를 표시한다.
종료 코드: 기대값(0) 위반이나 --expect 차이가 있으면 1.

예상 소요(로컬 실측 기반 추정, 운영은 최대 2배):
  가벼운 지표만(--skip-heavy) 1분 안 · 전체 약 15~30분(합성 주소·임대 합성 주소·annual·동 이름 검사가 대부분)
쿼리 시간 제한: 가벼움 10초(넘으면 실패로 기록), 무거움 --heavy-timeout(기본 900초). 무거운 검사는 T 승인 뒤 실행한다.

사용(운영 서버 예):
  python prod_c5_core.py --env-file /opt/ch2_Macro/backend/.env --out /var/backups/ch2/p2/prod_c5.json
  python prod_c5_core.py --env-file backend/.env --out logs/collective_p2/local_c5.json            (로컬)
  python prod_c5_core.py --env-file ... --expect logs/collective_p2/local_c5.json                 (비교)
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import sql_copies as S  # noqa: E402
from _common import Timed, db_name, db_url, md_table, read_json, ro_conn, table_exists, write_json  # noqa: E402

REPO = HERE.parents[2]
DEFAULT_SPLIT_UNITS = REPO / "pipeline" / "collective" / "data" / "p2_split_units.csv"


def judged_keys(conn, t: Timed, split_units: Path | None) -> set[str]:
    """판정이 끝난 키: C-01 목록(유지·분할) + 연결표 분할 새 키 + C-2 판정 표(collective_building_key_c2_units)."""
    keys: set[str] = set()
    if split_units and split_units.is_file():
        with split_units.open(encoding="utf-8", newline="") as f:
            keys |= {r["base_key"] for r in csv.DictReader(f) if r.get("decision") in ("keep", "split")}
    if table_exists(conn, "collective_building_key_map"):
        rows = t.run(conn, "연결표 분할 새 키", "SELECT DISTINCT new_key FROM collective_building_key_map "
                     "WHERE reason LIKE '%split%'") or []
        keys |= {r[0] for r in rows}
    if table_exists(conn, "collective_building_key_c2_units"):
        rows = t.run(conn, "C-2 판정 표 키", "SELECT DISTINCT base_key FROM collective_building_key_c2_units") or []
        keys |= {r[0] for r in rows}
    return keys


def collect(cconn, rconn, bconn, *, as_of=None, heavy_ms: int, skip_heavy: bool,
            split_units: Path | None = DEFAULT_SPLIT_UNITS) -> dict:
    t = Timed()
    m: dict = {"db": {"collective": db_name(cconn), "rent": db_name(rconn) if rconn is not None else None,
                      "built": db_name(bconn) if bconn is not None else None}}
    a = as_of or t.run(cconn, "최신 as_of", "SELECT max(as_of_month) FROM collective_building_stats", fetch="scalar")
    m["as_of"] = str(a)
    leg = {"l": S.LEGACY_SIDO}
    # 1 옛 시도명
    for name, conn, sql, p in (
        ("collective_transactions", cconn, "SELECT count(*) FROM collective_transactions WHERE addr1 = ANY(:l)", leg),
        ("collective_commercial_transactions", cconn,
         "SELECT count(*) FROM collective_commercial_transactions WHERE addr1 = ANY(:l)", leg),
        ("built_transactions", bconn, "SELECT count(*) FROM built_transactions WHERE addr1 = ANY(:l)", leg),
        ("rent_transactions", rconn, "SELECT count(*) FROM rent_transactions WHERE addr1 = ANY(:l)", leg),
        ("built_scope_stats(as_of)", bconn, "SELECT count(*) FROM built_scope_stats WHERE as_of_month = :a AND addr1 = ANY(:l)",
         {**leg, "a": a}),
    ):
        if conn is None:
            continue
        # 원장 전체 훑기라 큰 표는 10초를 넘을 수 있다 → 무거움 시간 사용(인덱스 없으면 순차 스캔)
        v = t.run(conn, f"옛 시도명 {name}", sql, p, timeout_ms=heavy_ms, fetch="scalar")
        m[f"legacy_sido.{name}"] = None if v is None else int(v)
    # 4 분할 키 수
    if table_exists(cconn, "collective_building_key_map"):
        rows = t.run(cconn, "연결표 사유별", "SELECT reason, count(*), count(DISTINCT old_key), count(DISTINCT new_key) "
                     "FROM collective_building_key_map GROUP BY 1 ORDER BY 1") or []
        for reason, n, o, nk in rows:
            m[f"keymap.{reason}.rows"], m[f"keymap.{reason}.old_keys"], m[f"keymap.{reason}.new_keys"] = int(n), int(o), int(nk)
        v = t.run(cconn, "분할 옛 키 남은 원장 행",
                  # C-01 분할 옛 키는 원장에서 모두 사라져야 한다. C-2 는 본 조각이 옛 키를 그대로 쓰므로 세지 않는다.
                  "SELECT count(*) FROM collective_transactions t WHERE t.building_key IN (SELECT old_key FROM "
                  "collective_building_key_map WHERE reason LIKE '%split%')",
                  timeout_ms=heavy_ms, fetch="scalar")
        m["split_old_key_rows_left"] = None if v is None else int(v)
    else:
        m["keymap"] = "연결표 없음"
    if rconn is not None and table_exists(rconn, "rent_building_key_map"):
        v = t.run(rconn, "임대 연결표 행", "SELECT count(*) FROM rent_building_key_map", fetch="scalar")
        m["rent_keymap.rows"] = None if v is None else int(v)
    # 5 커버리지
    for nm, tbl in (("attributes", "collective_building_attributes"), ("land_price", "collective_building_assessed_land_price"),
                    ("geocodes", "collective_building_geocodes")):
        r = t.run(cconn, f"커버리지 {nm}", f"""SELECT count(*) FILTER (WHERE EXISTS (SELECT 1 FROM {tbl} x WHERE x.building_key = s.building_key)),
                   count(*) FROM collective_building_stats s
                   WHERE s.as_of_month = :a AND s.window_years = 5 AND s.asset_type = 'apartment'""", {"a": a},
                  timeout_ms=heavy_ms, fetch="one")
        if r is not None:
            m[f"coverage.{nm}"] = round(int(r[0]) / max(int(r[1]), 1), 6)
            m[f"coverage.{nm}.n"] = [int(r[0]), int(r[1])]
    if not skip_heavy:
        # 2 합성 주소
        rows = t.run(cconn, "합성 주소 building_stats", S.SYNTH_SQL, {"as_of": a}, timeout_ms=heavy_ms)
        if rows is not None:
            for w, n in rows:
                m[f"synthetic.building_stats.{int(w)}y"] = int(n)
        if rconn is not None:
            ra = t.run(rconn, "임대 최신 as_of", "SELECT max(as_of_month) FROM rent_building_stats", fetch="scalar",
                       timeout_ms=heavy_ms)
            rows = t.run(rconn, "합성 주소 rent_building_stats", S.RENT_SYNTH_SQL, {"a": ra}, timeout_ms=heavy_ms)
            if rows is not None:
                for w, n in rows:
                    m[f"synthetic.rent_building_stats.{int(w)}y"] = int(n)
        # 3 annual = 원장
        rows = t.run(cconn, "annual 합 = 원장 합", S.ANNUAL_VS_LEDGER_SQL, timeout_ms=heavy_ms)
        m["annual_vs_ledger_mismatch"] = None if rows is None else len(rows)
        # 6 동 이름 2개+ · C-2형
        rows = t.run(cconn, "동 이름 ≥2 이름 키", S.MULTI_LEAF_SQL, timeout_ms=heavy_ms)
        if rows is not None:
            judged = judged_keys(cconn, t, split_units)
            m["multi_dong_keys"] = len(rows)
            m["multi_dong_pending"] = len({r[0] for r in rows} - judged)
        rows = t.run(cconn, "C-2형", S.C2_SHAPE_SQL, timeout_ms=heavy_ms)
        if rows is not None:
            judged = judged_keys(cconn, t, split_units)
            m["c2_shape"] = len(rows)
            m["c2_shape_pending"] = len({r[0] for r in rows} - judged)
    m["_timings"] = t.log
    return m


ZERO = ("legacy_sido.", "synthetic.", "annual_vs_ledger_mismatch", "split_old_key_rows_left", "multi_dong_pending")


def violations(m: dict, expect: dict | None = None) -> list[tuple[str, object, object]]:
    bad = []
    for k, v in m.items():
        if k.startswith("_") or k in ("db", "as_of"):
            continue
        if any(k.startswith(z) for z in ZERO) and v not in (0, None):
            bad.append((k, v, 0))
    if expect:
        for k, v in expect.items():
            if k.startswith("_") or k in ("db",):
                continue
            if m.get(k) != v:
                bad.append((k, m.get(k), v))
    for x in m.get("_timings", []):
        if not x["ok"]:
            bad.append((f"쿼리 실패: {x['query']}", x.get("error"), "성공"))
    return bad


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--env-file", type=Path, default=None)
    p.add_argument("--collective-env", default="COLLECTIVE_DATABASE_URL")
    p.add_argument("--rent-env", default="RENT_DATABASE_URL")
    p.add_argument("--built-env", default="BUILT_DATABASE_URL")
    p.add_argument("--as-of", default=None)
    p.add_argument("--heavy-timeout", type=int, default=900, help="무거운 쿼리 시간 제한(초)")
    p.add_argument("--skip-heavy", action="store_true")
    p.add_argument("--split-units", type=Path, default=DEFAULT_SPLIT_UNITS)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--expect", type=Path, default=None, help="비교할 JSON(로컬 반영 뒤 같은 스크립트 결과)")
    a = p.parse_args(argv)
    with ro_conn(db_url(a.collective_env, a.env_file)) as c, ro_conn(db_url(a.rent_env, a.env_file)) as r, \
            ro_conn(db_url(a.built_env, a.env_file)) as b:
        m = collect(c, r, b, as_of=a.as_of, heavy_ms=a.heavy_timeout * 1000, skip_heavy=a.skip_heavy,
                    split_units=a.split_units)
    if a.out:
        write_json(a.out, m)
    print(md_table([(k, v) for k, v in m.items() if not k.startswith("_")], ["지표", "값"]))
    print()
    print(md_table([(x["query"], x["sec"], x["timeout_ms"] // 1000, "OK" if x["ok"] else x.get("error"))
                    for x in m["_timings"]], ["쿼리", "초", "제한(초)", "결과"]))
    bad = violations(m, read_json(a.expect) if a.expect else None)
    if bad:
        print("\n## 확인 필요\n")
        print(md_table(bad, ["지표", "값", "기대"]))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
