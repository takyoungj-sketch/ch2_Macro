"""집합 2단계 — C-2 분할 키의 2019~2020 annual 행 범위 교체(Codex 검토 반영, 리허설 4단계).

왜: C-2 는 본 조각이 옛 키를 그대로 쓴다. 키 이전 뒤 빌더가 그 해에 본 조각 거래가 없으면 옛(합친) 값이 남는다.
대상: C-2 판정 표 split 의 본 키(base_key) + 연결표 C-2 조각 키(reason 에 c2_split·c2_chain) × 유형 × 2019·2020.
방법: 키 이전 뒤 원장에서 annual 빌더와 **같은 SQL(ANNUAL_SQL: is_valid·unit_price>0·contract_year)과 같은 레코드 함수
      (annual_record_from_row → compute_stats)**로 다시 계산한다.
      - 계산 결과가 있으면 교체(없던 행이면 넣음), 유효 거래가 0건이면 기존 행을 지운다.
      - 2010~2018 은 건드리지 않는다.
보존: 바뀌거나 지워지는 기존 행은 `collective_building_annual_c2_p2_before` 에 행 전체(p2_action 포함), 새로 넣은 행은 표시 행.
      --rollback 으로 원상태. 다시 돌려도 처음 보존한 원래 행은 덮지 않는다(멱등).
가드: 쓰기는 리허설 DB(assert_rehearsal_db) 또는 --real-apply(런북 5절 조건). 드라이런 기본.

  python -m collective.c2_annual_replace_p2 --collective-db collective_stats_p2r            # 드라이런
  python -m collective.c2_annual_replace_p2 --collective-db collective_stats_p2r --apply
  python -m collective.c2_annual_replace_p2 --collective-db collective_stats_p2r --verify   # c6 에서도 부름
  python -m collective.c2_annual_replace_p2 --collective-db collective_stats_p2r --rollback
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

_PIPE = Path(__file__).resolve().parents[1]
for _p in (_PIPE, _PIPE / "collective"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from build_collective_building_stats import ANNUAL_SQL, annual_record_from_row  # noqa: E402
from collective.building_keys import C2_TABLE  # noqa: E402
from collective.migrate_p2_keys import (  # noqa: E402
    add_real_apply_args,
    assert_rehearsal_db,
    check_write_targets,
    engine_for,
)

T = "collective_building_annual_stats"
KEEP = "collective_building_annual_c2_p2_before"
YEARS = (2019, 2020)
BATCH = "p2_c2_annual"
GRAIN = ["building_key", "asset_type", "contract_year"]
STAT_COLS = ["count", "mean", "std", "ci_lower", "ci_upper", "p25", "median", "p75"]
REC_COLS = ["building_key", "asset_type", "contract_year", "display_name", "addr1", "addr2", "addr3", "addr4",
            "beopjungri_code", *STAT_COLS, "batch_id"]


def _exists(conn: Connection, t: str) -> bool:
    return bool(conn.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"public.{t}"}).scalar())


def targets(conn: Connection) -> pd.DataFrame:
    """(building_key, asset_type) — 판정 표 split 본 키 + 연결표 C-2 조각 키."""
    parts = []
    if _exists(conn, C2_TABLE):
        parts.append(pd.read_sql(text(f"SELECT DISTINCT base_key AS building_key, asset_type FROM {C2_TABLE} "
                                      "WHERE decision = 'split'"), conn))
    if _exists(conn, "collective_building_key_map"):
        parts.append(pd.read_sql(text("""SELECT DISTINCT new_key AS building_key, asset_type FROM collective_building_key_map
                                         WHERE reason LIKE '%c2_split%' OR reason = 'c2_chain'"""), conn))
    if not parts:
        return pd.DataFrame(columns=["building_key", "asset_type"])
    return pd.concat(parts, ignore_index=True).drop_duplicates().reset_index(drop=True)


def _keys_sql(sql: str):
    return text(sql).bindparams(bindparam("keys", expanding=True), bindparam("years", expanding=True))


def recompute(conn: Connection, tg: pd.DataFrame) -> list[dict]:
    """원장 재계산(annual 빌더와 같은 SQL·함수). 대상 (키·유형)만."""
    if tg.empty:
        return []
    sql = ANNUAL_SQL.format(addr1_clause="", asset_clause="AND building_key IN :keys AND contract_year IN :years")
    want = set(zip(tg["building_key"], tg["asset_type"]))
    keys = sorted(set(tg["building_key"]))
    out: list[dict] = []
    for i in range(0, len(keys), 2000):
        rows = conn.execute(_keys_sql(sql), {"keys": keys[i:i + 2000], "years": list(YEARS)}).mappings().all()
        for r in rows:
            if (r["building_key"], r["asset_type"]) not in want:
                continue
            rec = annual_record_from_row(r, BATCH)
            if rec is not None and rec["count"] > 0:
                out.append(rec)
    return out


def existing(conn: Connection, tg: pd.DataFrame) -> pd.DataFrame:
    if tg.empty:
        return pd.DataFrame(columns=["id", *GRAIN, *STAT_COLS])
    keys = sorted(set(tg["building_key"]))
    frames = []
    for i in range(0, len(keys), 2000):
        frames.append(pd.read_sql(_keys_sql(
            f"SELECT id, {', '.join(GRAIN)}, {', '.join(STAT_COLS)} FROM {T} WHERE building_key IN :keys "
            "AND contract_year IN :years"), conn, params={"keys": keys[i:i + 2000], "years": list(YEARS)}))
    df = pd.concat(frames, ignore_index=True)
    want = set(zip(tg["building_key"], tg["asset_type"]))
    return df[[(k, a) in want for k, a in zip(df["building_key"], df["asset_type"])]].reset_index(drop=True)


def plan(conn: Connection) -> dict:
    tg = targets(conn)
    recs = recompute(conn, tg)
    ex = existing(conn, tg)
    have = {(k, a, int(y)) for k, a, y in zip(ex["building_key"], ex["asset_type"], ex["contract_year"])}
    comp = {(r["building_key"], r["asset_type"], int(r["contract_year"])) for r in recs}
    act = {g: ("replace" if g in comp else "delete") for g in have}
    act.update({g: "insert" for g in comp - have})
    return {"targets": tg, "records": recs, "existing": ex, "actions": act}


def summary(p: dict) -> dict:
    a = list(p["actions"].values())
    return {"target_keys": int(len(p["targets"])), "existing_rows": int(len(p["existing"])),
            "replace": a.count("replace"), "insert": a.count("insert"), "delete": a.count("delete"),
            "recomputed_tx": int(sum(r["count"] for r in p["records"]))}


def _cols(conn: Connection, t: str) -> list[str]:
    return [r[0] for r in conn.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=:t "
        "ORDER BY ordinal_position"), {"t": t})]


def apply(eng, dbname: str) -> dict:
    with eng.begin() as conn:
        assert_rehearsal_db(conn, dbname)
        p = plan(conn)
        if not _exists(conn, KEEP):
            conn.execute(text(f"CREATE TABLE {KEEP} AS SELECT a.*, NULL::text AS p2_action, now() AS p2_saved_at "
                              f"FROM {T} a WITH NO DATA"))
        saved = set(map(tuple, conn.execute(text(f"SELECT building_key, asset_type, contract_year FROM {KEEP}")).all()))
        saved = {(str(k).strip(), a, int(y)) for k, a, y in saved}
        cols = _cols(conn, T)
        n_saved = 0
        for _, r in p["existing"].iterrows():
            g = (str(r["building_key"]).strip(), r["asset_type"], int(r["contract_year"]))
            if g in saved:
                continue
            conn.execute(text(f"INSERT INTO {KEEP} ({', '.join(cols)}, p2_action) SELECT {', '.join(cols)}, :act "
                              f"FROM {T} WHERE id = :id"), {"act": p["actions"][g], "id": int(r["id"])})
            n_saved += 1
        for g, a in p["actions"].items():
            if a == "insert" and g not in saved:
                conn.execute(text(f"INSERT INTO {KEEP} (building_key, asset_type, contract_year, p2_action) "
                                  "VALUES (:k, :a, :y, 'insert')"), {"k": g[0], "a": g[1], "y": g[2]})
        ids = [int(x) for x in p["existing"]["id"]]
        n_del = 0
        for i in range(0, len(ids), 5000):
            n_del += conn.execute(text(f"DELETE FROM {T} WHERE id = ANY(:i)"), {"i": ids[i:i + 5000]}).rowcount or 0
        if n_del != len(ids):
            raise RuntimeError(f"삭제 {n_del} ≠ 계획 {len(ids)} — 롤백")
        if p["records"]:
            conn.execute(text(f"INSERT INTO {T} ({', '.join(REC_COLS)}, computed_at) VALUES "
                              f"({', '.join(':' + c for c in REC_COLS)}, now())"),
                         [{c: r[c] for c in REC_COLS} for r in p["records"]])
        return {**summary(p), "saved_rows": n_saved, "deleted_rows": n_del, "written_rows": len(p["records"])}


def rollback(eng, dbname: str) -> dict:
    with eng.begin() as conn:
        assert_rehearsal_db(conn, dbname)
        if not _exists(conn, KEEP):
            return {"restored": 0, "removed": 0}
        removed = conn.execute(text(f"""DELETE FROM {T} a USING {KEEP} k WHERE a.building_key = k.building_key
                                        AND a.asset_type = k.asset_type AND a.contract_year = k.contract_year""")).rowcount
        cols = _cols(conn, T)
        restored = conn.execute(text(f"INSERT INTO {T} ({', '.join(cols)}) SELECT {', '.join(cols)} FROM {KEEP} "
                                     "WHERE p2_action IN ('replace', 'delete')")).rowcount
        conn.execute(text(f"DROP TABLE {KEEP}"))
        return {"restored": int(restored or 0), "removed": int(removed or 0)}


def verify(conn: Connection) -> list[tuple[str, object, object, bool]]:
    """(지표, 기대, 실제, 통과) — c6 에서도 쓴다. 대상 행 통계 = 원장 재계산, 원장 근거 없는 대상 행 0."""
    tg = targets(conn)
    if tg.empty:
        return [("C-2 2019~2020 annual 대상 키", "> 0(C-2 반영 뒤)", 0, False)]
    recs = {(r["building_key"], r["asset_type"], int(r["contract_year"])): r for r in recompute(conn, tg)}
    ex = existing(conn, tg)
    mism = no_basis = 0
    for r in ex.to_dict("records"):
        g = (str(r["building_key"]).strip(), r["asset_type"], int(r["contract_year"]))
        c = recs.get(g)
        if c is None:
            no_basis += 1
            continue
        for col in STAT_COLS:
            a, b = r[col], c[col]
            if a is None or b is None or (isinstance(a, float) and a != a):
                if not ((a is None or a != a) and b is None):
                    mism += 1
                    break
            elif round(float(a), 2) != round(float(b), 2):
                mism += 1
                break
    have = {(str(k).strip(), a, int(y)) for k, a, y in zip(ex["building_key"], ex["asset_type"], ex["contract_year"])}
    missing = len(set(recs) - have)
    return [("C-2 2019~2020 annual 대상 키", "> 0", len(tg), len(tg) > 0),
            ("대상 행 통계 ≠ 원장 재계산", 0, mism, mism == 0),
            ("원장 근거 없는 대상 행", 0, no_basis, no_basis == 0),
            ("원장에는 있는데 annual 에 없는 (키·유형·연도)", 0, missing, missing == 0)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collective-db", required=True)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true")
    g.add_argument("--rollback", action="store_true")
    g.add_argument("--verify", action="store_true")
    ap.add_argument("--base-url", default="")
    add_real_apply_args(ap)
    a = ap.parse_args(argv)
    if a.real_apply and (a.rollback or a.verify):
        raise SystemExit("--real-apply 는 적용만 한다(실제 DB 되돌리기는 런북의 로컬 덤프 복원)")
    if a.real_apply:
        a.apply = True
    base = a.base_url or None
    if a.apply or a.rollback:
        check_write_targets([a.collective_db], a, base_url=base)
    if a.rollback:
        print(json.dumps(rollback(engine_for(a.collective_db, read_only=False, base_url=base), a.collective_db)))
        return 0
    if a.apply:
        print(json.dumps(apply(engine_for(a.collective_db, read_only=False, base_url=base), a.collective_db),
                         ensure_ascii=False))
        return 0
    with engine_for(a.collective_db, read_only=True, base_url=base).connect() as conn:
        if a.verify:
            rows = verify(conn)
            for name, exp, got, ok in rows:
                print(f"{'OK ' if ok else 'NG '} {name}: 기대 {exp} / 실제 {got}")
            return 0 if all(r[3] for r in rows) else 1
        print(json.dumps({"dry_run": True, **summary(plan(conn))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
