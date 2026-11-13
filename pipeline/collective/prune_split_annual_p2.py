"""집합 2단계 — 2019~2020 annual 의 분할 옛 키 행 정리(T 조건부 승인 2026-11-13).

대상: `collective_building_annual_stats` 에서 contract_year 2019·2020, building_key 가 연결표
(`collective_building_key_map`, reason 에 split)로 쪼개진 옛 키인 행.
조건: (옛 키·유형·연도)마다 「옛 행 count = 그 옛 키의 새 조각 키들의 같은 유형·연도 count 합」일 때만 삭제.
      불일치 행은 지우지 않고 목록으로 낸다.
보존: 지운 행 전체를 `collective_building_annual_split_p2_before` 에 남긴다(되돌리기 `--rollback`).
가드: 쓰기 접속마다 `assert_rehearsal_db`(지정 이름 = 접속 이름, *_p2r 패턴, 보호 목록 밖). 한 트랜잭션. 드라이런 기본.

  python -m collective.prune_split_annual_p2 --collective-db collective_stats_p2r            # 드라이런
  python -m collective.prune_split_annual_p2 --collective-db collective_stats_p2r --apply
  python -m collective.prune_split_annual_p2 --collective-db collective_stats_p2r --rollback
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

_PIPE = Path(__file__).resolve().parents[1]
if str(_PIPE) not in sys.path:
    sys.path.insert(0, str(_PIPE))

from collective.migrate_p2_keys import assert_rehearsal_db, engine_for  # noqa: E402

T = "collective_building_annual_stats"
KEEP = "collective_building_annual_split_p2_before"
YEARS = (2019, 2020)

PLAN_SQL = f"""
WITH km AS (
    SELECT old_key, new_key, asset_type FROM collective_building_key_map WHERE reason LIKE '%split%'
), old AS (
    SELECT a.id, a.building_key AS old_key, a.asset_type, a.contract_year, a.count AS old_n
    FROM {T} a
    WHERE a.contract_year IN :years AND a.building_key IN (SELECT old_key FROM km)
), frag AS (
    SELECT km.old_key, a.asset_type, a.contract_year, sum(a.count) AS new_n, count(*) AS new_rows
    FROM km JOIN {T} a ON a.building_key = km.new_key AND a.asset_type = km.asset_type
    WHERE a.contract_year IN :years
    GROUP BY 1, 2, 3
)
SELECT o.id, o.old_key, o.asset_type, o.contract_year, o.old_n,
       COALESCE(f.new_n, 0) AS new_n, COALESCE(f.new_rows, 0) AS new_rows
FROM old o LEFT JOIN frag f
  ON f.old_key = o.old_key AND f.asset_type = o.asset_type AND f.contract_year = o.contract_year
ORDER BY o.asset_type, o.contract_year, o.old_key
"""


def plan(conn: Connection) -> pd.DataFrame:
    from sqlalchemy import bindparam

    df = pd.read_sql(text(PLAN_SQL).bindparams(bindparam("years", expanding=True)), conn, params={"years": list(YEARS)})
    df["match"] = df["old_n"].astype(int) == df["new_n"].astype(int)
    return df


def summary(df: pd.DataFrame) -> dict:
    ok, bad = df[df["match"]], df[~df["match"]]
    return {"target_rows": int(len(df)), "target_tx": int(df["old_n"].sum()),
            "delete_rows": int(len(ok)), "delete_tx": int(ok["old_n"].sum()),
            "mismatch_rows": int(len(bad)), "mismatch_tx": int(bad["old_n"].sum()),
            "mismatch_no_fragment_rows": int((bad["new_rows"] == 0).sum())}


def apply(eng, dbname: str) -> dict:
    with eng.begin() as conn:
        assert_rehearsal_db(conn, dbname)
        df = plan(conn)
        ids = [int(x) for x in df.loc[df["match"], "id"]]
        conn.execute(text(f"CREATE TABLE IF NOT EXISTS {KEEP} (LIKE {T} INCLUDING DEFAULTS)"))
        n_keep = n_del = 0
        for i in range(0, len(ids), 5000):
            chunk = ids[i:i + 5000]
            n_keep += conn.execute(text(f"INSERT INTO {KEEP} SELECT * FROM {T} WHERE id = ANY(:i) "
                                        f"AND id NOT IN (SELECT id FROM {KEEP})"), {"i": chunk}).rowcount or 0
            n_del += conn.execute(text(f"DELETE FROM {T} WHERE id = ANY(:i)"), {"i": chunk}).rowcount or 0
        if n_del != len(ids):
            raise RuntimeError(f"삭제 {n_del} ≠ 계획 {len(ids)} — 롤백")
        return {**summary(df), "kept": n_keep, "deleted": n_del}


def rollback(eng, dbname: str) -> int:
    with eng.begin() as conn:
        assert_rehearsal_db(conn, dbname)
        if not conn.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"public.{KEEP}"}).scalar():
            return 0
        n = conn.execute(text(f"INSERT INTO {T} SELECT * FROM {KEEP} k WHERE NOT EXISTS (SELECT 1 FROM {T} a WHERE a.id = k.id)")).rowcount
        conn.execute(text(f"DROP TABLE {KEEP}"))
        return int(n or 0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collective-db", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--mismatch-csv", default="", help="불일치 목록 CSV 경로(키만, 지번 없음)")
    a = ap.parse_args()
    if a.apply and a.rollback:
        raise SystemExit("--apply 와 --rollback 은 같이 쓰지 않는다")
    if a.rollback:
        print(json.dumps({"restored": rollback(engine_for(a.collective_db, read_only=False), a.collective_db)}))
        return
    if a.apply:
        out = apply(engine_for(a.collective_db, read_only=False), a.collective_db)
    else:
        with engine_for(a.collective_db, read_only=True).connect() as conn:
            df = plan(conn)
        out = {"dry_run": True, **summary(df)}
    if a.mismatch_csv:
        with engine_for(a.collective_db, read_only=True).connect() as conn:
            df = plan(conn)
        df[~df["match"]].drop(columns=["id"]).to_csv(a.mismatch_csv, index=False, encoding="utf-8-sig")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
