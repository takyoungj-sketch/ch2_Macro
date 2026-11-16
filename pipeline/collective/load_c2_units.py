#!/usr/bin/env python3
"""집합 2단계 P3 — C-2 판정 파일(c25 확정, `logs/collective_p2/c2_units_final.csv`)을 리허설 DB 의
`collective_building_key_c2_units` 에 적재한다.

- 쓰기는 리허설 DB(…_p2r) 또는 실제 적용 모드(`--real-apply`, 로컬 실제 `collective_stats` — 런북 5.1 1단계)만:
  이름 확인(check_write_targets) + 접속 뒤 current_database() 확인(assert_rehearsal_db).
  실제 적용 모드는 키 이전과 같은 가드(루프백·--confirm-db·동기화 확인 통과)에 더해
  승인된 판정 파일의 SHA-256(`--approved-sha256`)·행 수(`--approved-rows`, 이번 4,311)가 파일과 같아야 한다.
  적재 기록(p2_migration_log)에 파일 해시·내용 해시를 남긴다 → `migrate_p2_keys --real-apply` 가 시작 전에 대조한다.
  운영은 promote 로 따라간다.
- 드라이런 기본(읽기 전용 접속, 검사·건수만). --apply 로 한 트랜잭션에 적재.
- 멱등: 같은 (base_key, 법정동, 본번) 행이 이미 같은 값이면 건너뛴다. 값이 다른 행이 있으면 아무것도 쓰지 않고 멈춘다.
  표에만 있는 행(자동 등록 등)은 건드리지 않고 건수만 낸다.
- 출력은 건수만(지번·키 원문을 내지 않는다).

  python pipeline/collective/load_c2_units.py --collective-db collective_stats_p2r            # 드라이런
  python pipeline/collective/load_c2_units.py --collective-db collective_stats_p2r --apply
  python pipeline/collective/load_c2_units.py --collective-db collective_stats --real-apply --confirm-db collective_stats \\
      --sync-result logs/collective_p2/sync_result_collective.json --approved-sha256 <승인 해시> --approved-rows 4311
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "pipeline" / "collective"))

from collective.building_keys import C2_DDL, C2_TABLE, main_lot_of  # noqa: E402
from collective.migrate_p2_keys import (  # noqa: E402
    GuardError,
    _exec_script,
    add_real_apply_args,
    assert_rehearsal_db,
    check_write_targets,
    engine_for,
)

DEFAULT_CSV = REPO / "logs" / "collective_p2" / "c2_units_final.csv"
COLS = ["base_key", "asset_type", "beopjungri_code", "main_lot", "building_year", "part", "decision", "source", "note"]
PK = ["base_key", "beopjungri_code", "main_lot"]
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_BJD = re.compile(r"^[0-9]{10}$")
ASSETS = {"apartment", "rowhouse", "officetel", "presale"}


class LoadError(RuntimeError):
    pass


def _int_or_none(v) -> int | None:
    if v is None or (isinstance(v, float) and v != v) or str(v).strip() == "":
        return None
    return int(float(v))


def read_units(path: Path) -> pd.DataFrame:
    """CSV → 정규화된 판정 행(COLS). 형식이 틀리면 LoadError(어느 검사인지와 건수만)."""
    if not Path(path).is_file():
        raise LoadError(f"판정 파일 없음: {Path(path).name}")
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    miss = [c for c in COLS if c not in df.columns and c != "note"]
    if miss:
        raise LoadError(f"판정 파일 열 없음: {miss}")
    if "note" not in df.columns:
        df["note"] = ""
    df = df[COLS].copy()
    for c in ("base_key", "asset_type", "beopjungri_code", "decision", "source", "note"):
        df[c] = df[c].astype(str).str.strip()
    df["main_lot"] = df["main_lot"].map(main_lot_of)
    for c in ("building_year", "part"):                     # 정수 또는 None(object) — float·NaN 으로 바뀌지 않게
        df[c] = pd.Series([_int_or_none(v) for v in df[c]], index=df.index, dtype="object")
    errs = validate(df)
    if errs:
        raise LoadError("판정 파일 검사 실패: " + "; ".join(errs))
    return df


def validate(df: pd.DataFrame) -> list[str]:
    errs: list[str] = []

    def bad(name: str, mask) -> None:
        n = int(mask.sum())
        if n:
            errs.append(f"{name} {n}행")

    bad("base_key 형식(sha256 16진 64자) 아님", ~df["base_key"].str.match(_HEX64))
    bad("법정동 코드 10자리 아님", ~df["beopjungri_code"].str.match(_BJD))
    bad("유형 모름", ~df["asset_type"].isin(ASSETS))
    bad("decision 이 split·keep 아님", ~df["decision"].isin({"split", "keep"}))
    sp = df["decision"] == "split"
    bad("split 인데 조각 번호 없음", sp & df["part"].isna())
    bad("split 인데 본번 없음", sp & (df["main_lot"] == ""))
    bad("조각 번호 음수", df["part"].map(lambda x: x is not None and x < 0))
    bad("분양권 split", sp & (df["asset_type"] == "presale"))
    bad("(키·법정동·본번) 중복", df.duplicated(PK, keep=False))
    if sp.any():
        g = df[sp].groupby(["base_key", "beopjungri_code"])["part"]
        no0 = g.apply(lambda s: 0 not in set(s))
        if int(no0.sum()):
            errs.append(f"본 조각(0) 없는 (키·법정동) {int(no0.sum())}")
        nz = df[sp & (df["part"].map(lambda x: x is not None and x != 0))]
        reuse = nz.groupby(["base_key", "part"])["beopjungri_code"].nunique()
        if int((reuse > 1).sum()):
            # 조각 키 = 원문 + 조각 번호 → 법정동이 달라도 번호가 같으면 한 키로 합쳐진다
            errs.append(f"0 이 아닌 조각 번호를 두 법정동에서 같이 쓰는 키 {int((reuse > 1).sum())}")
        one = g.apply(lambda s: len(set(s)) < 2)
        if int(one.sum()):
            errs.append(f"조각이 하나뿐인 split (키·법정동) {int(one.sum())}")
    t = df.groupby("base_key")["asset_type"].nunique()
    if int((t > 1).sum()):
        errs.append(f"키 하나에 유형 여럿 {int((t > 1).sum())}")
    return errs


def _table_rows(conn: Connection) -> pd.DataFrame:
    if not conn.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"public.{C2_TABLE}"}).scalar():
        return pd.DataFrame(columns=COLS)
    return pd.read_sql(text(f"SELECT {', '.join(COLS)} FROM {C2_TABLE}"), conn)


def _norm_cmp(v):
    if v is None or (isinstance(v, float) and v != v):
        return None
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def compare(df: pd.DataFrame, cur: pd.DataFrame) -> dict:
    """파일 행 ↔ 표 행: 새로 넣을 행·이미 같은 행·값이 다른 행·표에만 있는 행."""
    cmp_cols = ["asset_type", "building_year", "part", "decision"]
    cur_map = {tuple(r[c] for c in PK): tuple(_norm_cmp(r[c]) for c in cmp_cols)
               for r in cur.to_dict("records")}
    new, same, diff = [], 0, 0
    keys = set()
    for r in df.to_dict("records"):
        k = tuple(r[c] for c in PK)
        keys.add(k)
        if k not in cur_map:
            new.append(r)
        elif cur_map[k] == tuple(_norm_cmp(r[c]) for c in cmp_cols):
            same += 1
        else:
            diff += 1
    only_table = sum(1 for k in cur_map if k not in keys)
    return {"new": new, "same": same, "diff": diff, "only_table": only_table}


def final_state_errors(df: pd.DataFrame, cur: pd.DataFrame) -> list[str]:
    """적재 뒤 최종 상태(표에 이미 있는 행 + 파일의 새 행) 검사.
    조각 키 = 원문 + 조각 번호라서, 0 이 아닌 (키, 조각 번호)가 서로 다른 법정동에 쓰이면 다른 건물이 한 키로 합쳐진다.
    같은 법정동 안의 여러 본번이 한 조각인 것은 정상이다. 각 (키·법정동) split 묶음에는 본 조각 0 이 있어야 한다."""
    k = set(map(tuple, df[PK].itertuples(index=False, name=None)))
    old = cur[[tuple(r) not in k for r in cur[PK].itertuples(index=False, name=None)]] if len(cur) else cur
    fin = pd.concat([df[COLS], old[COLS]], ignore_index=True) if len(old) else df[COLS].copy()
    fin["part"] = fin["part"].map(_norm_cmp)
    sp = fin[fin["decision"] == "split"]
    errs: list[str] = []
    nz = sp[sp["part"].map(lambda x: x is not None and x != 0)]
    reuse = nz.groupby(["base_key", "part"])["beopjungri_code"].nunique()
    if int((reuse > 1).sum()):
        errs.append(f"최종 상태에서 0 이 아닌 (키, 조각 번호)가 두 법정동 이상에 쓰임 {int((reuse > 1).sum())}")
    no0 = sp.groupby(["base_key", "beopjungri_code"])["part"].apply(lambda s_: 0 not in set(s_))
    if int(no0.sum()):
        errs.append(f"최종 상태에서 본 조각(0) 없는 (키·법정동) {int(no0.sum())}")
    t = fin.groupby("base_key")["asset_type"].nunique()
    if int((t > 1).sum()):
        errs.append(f"최종 상태에서 키 하나에 유형 여럿 {int((t > 1).sum())}")
    return errs


def summary(df: pd.DataFrame) -> dict:
    sp = df[df["decision"] == "split"]
    units = sp.groupby(["base_key", "beopjungri_code"])["part"].nunique()
    return {"rows": len(df), "split_rows": len(sp), "keep_rows": int((df["decision"] == "keep").sum()),
            "split_units": int(len(units)), "added_keys": int((units - 1).sum()),
            "by_asset": {a: int(n) for a, n in sp.drop_duplicates(["base_key", "beopjungri_code"])["asset_type"]
                         .value_counts().sort_index().items()}}


APPROVED_ROWS_DEFAULT = 4311     # c25 확정 판정 파일 행 수(T 승인 값 — 실제 DB 모드는 인자로 다시 받는다)
LOG_STEP = "load_c2_units"
AUTO_SOURCES = ("p2_migrate", "auto_ingest")   # 판정 파일이 아닌 자동 등록 행(키 이전·월간 적재)


def file_sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def content_sha256(df: pd.DataFrame) -> str:
    """판정 내용의 정규 해시: (키·법정동·본번) 순 정렬, 비교 열(유형·연도·조각·판정)만. 파일 행과 표 행이 같은 값이면 같다."""
    import hashlib

    cols = [*PK, "asset_type", "building_year", "part", "decision"]
    recs = sorted(tuple("" if _norm_cmp(r[c]) is None else str(_norm_cmp(r[c])) for c in cols)
                  for r in df[cols].to_dict("records"))
    return hashlib.sha256("\n".join("\t".join(r) for r in recs).encode("utf-8")).hexdigest()


def check_approved_file(path: Path, df: pd.DataFrame, sha: str, rows: int) -> None:
    """승인된 판정 파일인지: 파일 바이트 SHA-256 과 행 수가 승인값과 같아야 한다."""
    sha = (sha or "").strip().lower()
    if not _HEX64.match(sha):
        raise LoadError("승인 SHA-256 형식이 아님(16진 64자)")
    got = file_sha256(path)
    if got != sha:
        raise LoadError(f"판정 파일 SHA-256 이 승인값과 다름({got[:12]}… ≠ {sha[:12]}…)")
    if len(df) != int(rows):
        raise LoadError(f"판정 파일 행 수 {len(df):,} ≠ 승인 {int(rows):,}")


def approved_table_state(conn: Connection, sha: str, rows: int) -> dict:
    """키 이전(--real-apply) 시작 전 확인: 판정 표가 승인 파일 그대로 적재돼 있는가.
    ① 표가 있고 판정 행이 있음 ② 판정 행(자동 등록 p2_migrate·auto_ingest 제외) 수 = 승인 행 수
    ③ 마지막 적재 기록(p2_migration_log step=load_c2_units)의 파일 SHA-256 = 승인값
    ④ 지금 표 판정 행의 정규 해시 = 그 적재 기록의 내용 해시(적재 뒤 표가 바뀌지 않음).
    하나라도 어긋나면 LoadError."""
    sha = (sha or "").strip().lower()
    if not conn.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"public.{C2_TABLE}"}).scalar():
        raise LoadError(f"C-2 판정 표({C2_TABLE})가 없음 — 먼저 load_c2_units --real-apply")
    cur = pd.read_sql(text(f"SELECT {', '.join(COLS)} FROM {C2_TABLE} WHERE coalesce(source, '') NOT IN :a")
                      .bindparams(a=AUTO_SOURCES), conn)
    if cur.empty:
        raise LoadError("C-2 판정 표가 비었음 — 키 이전 거부")
    if len(cur) != int(rows):
        raise LoadError(f"C-2 판정 표 행 수 {len(cur):,} ≠ 승인 {int(rows):,} — 키 이전 거부")
    has_log = conn.execute(text("SELECT to_regclass('public.p2_migration_log') IS NOT NULL")).scalar()
    rec = conn.execute(text("SELECT detail FROM p2_migration_log WHERE step = :s ORDER BY id DESC LIMIT 1"),
                       {"s": LOG_STEP}).scalar() if has_log else None
    if isinstance(rec, str):
        rec = json.loads(rec)
    if not rec or not rec.get("file_sha256"):
        raise LoadError("판정 표 적재 기록(파일 해시)이 없음 — 승인 파일로 적재했는지 확인 불가, 키 이전 거부")
    if rec["file_sha256"] != sha:
        raise LoadError(f"판정 표를 적재한 파일 SHA-256 이 승인값과 다름({rec['file_sha256'][:12]}…) — 키 이전 거부")
    now = content_sha256(cur)
    if now != rec.get("content_sha256"):
        raise LoadError("판정 표 내용이 적재 기록과 다름(적재 뒤 바뀜) — 키 이전 거부")
    return {"rows": len(cur), "file_sha256": rec["file_sha256"], "content_sha256": now}


def load(eng: Engine, dbname: str, df: pd.DataFrame, *, apply: bool, file_hash: str | None = None) -> dict:
    """apply=False 면 읽기만. True 면 한 트랜잭션에서 표를 만들고 새 행만 넣는다(값이 다른 행이 있으면 멈춤)."""
    ctx = eng.begin() if apply else eng.connect()
    with ctx as conn:
        if apply:
            assert_rehearsal_db(conn, dbname)
        cur = _table_rows(conn)
        cmpr = compare(df, cur)
        out = {"db": dbname, **summary(df), "table_rows_before": len(cur), "insert": len(cmpr["new"]),
               "already_same": cmpr["same"], "value_differs": cmpr["diff"], "table_only_rows": cmpr["only_table"]}
        if cmpr["diff"]:
            raise LoadError(f"표에 값이 다른 행 {cmpr['diff']}개 — 쓰지 않음(판정 파일·표 확인)")
        fe = final_state_errors(df, cur)
        if fe:
            raise LoadError("최종 상태 검사 실패 — 쓰지 않음: " + "; ".join(fe))
        if not apply:
            return out
        _exec_script(conn, C2_DDL)
        rows = [{c: (None if (isinstance(v, float) and v != v) else v) for c, v in r.items()} for r in cmpr["new"]]
        for i in range(0, len(rows), 2000):
            conn.execute(text(f"""INSERT INTO {C2_TABLE} ({', '.join(COLS)})
                                  VALUES ({', '.join(':' + c for c in COLS)})"""), rows[i:i + 2000])
        after = compare(df, _table_rows(conn))
        if after["new"] or after["diff"]:
            raise LoadError("적재 뒤 표와 파일이 다름 — 되돌림")
        out["table_rows_after"] = int(conn.execute(text(f"SELECT count(*) FROM {C2_TABLE}")).scalar() or 0)
        out["file_sha256"] = file_hash
        out["content_sha256"] = content_sha256(df)
        conn.execute(text("CREATE TABLE IF NOT EXISTS p2_migration_log (id serial PRIMARY KEY, "
                          "run_at timestamptz NOT NULL DEFAULT now(), step text NOT NULL, detail jsonb)"))
        conn.execute(text("INSERT INTO p2_migration_log (step, detail) VALUES ('load_c2_units', CAST(:d AS jsonb))"),
                     {"d": json.dumps(out, ensure_ascii=False)})
        return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--collective-db", required=True)
    p.add_argument("--csv", default=str(DEFAULT_CSV), help="판정 파일(기본 logs/collective_p2/c2_units_final.csv)")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--base-url", default="", help="DB 서버 URL(기본 backend/.env)")
    add_real_apply_args(p)
    p.add_argument("--approved-sha256", default="", help="승인된 판정 파일의 SHA-256(실제 DB 모드 필수)")
    p.add_argument("--approved-rows", type=int, default=None,
                   help=f"승인된 판정 파일 행 수(실제 DB 모드 필수, 이번 {APPROVED_ROWS_DEFAULT:,})")
    a = p.parse_args(argv)
    base = a.base_url or None
    if a.real_apply:
        if not a.approved_sha256 or a.approved_rows is None:
            raise LoadError("--real-apply 는 --approved-sha256 · --approved-rows 가 필요하다")
        a.apply = True
    df = read_units(Path(a.csv))
    if a.approved_sha256 or a.approved_rows is not None:
        check_approved_file(Path(a.csv), df, a.approved_sha256, -1 if a.approved_rows is None else a.approved_rows)
    if a.apply:
        # 리허설(…_p2r) 또는 실제 적용 모드(키 이전과 같은 가드: 루프백·--confirm-db·동기화 확인 통과)
        check_write_targets([a.collective_db], a, base_url=base)
    eng = engine_for(a.collective_db, read_only=not a.apply, base_url=base)
    try:
        out = load(eng, a.collective_db, df, apply=a.apply, file_hash=file_sha256(Path(a.csv)))
    finally:
        eng.dispose()
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if not a.apply:
        print("드라이런 — 쓰지 않았다. 쓰려면 --apply (리허설 DB 만).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GuardError, LoadError) as ex:
        print(f"중단: {ex}", file=sys.stderr)
        raise SystemExit(2)
