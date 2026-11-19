"""임대 C-2 판정 표 적재.

기본은 읽기 전용이다. 쓰기는 테스트 fixture 또는 로컬 리허설 rent_stats_rc2r 만 허용한다.
rent_stats 와 집합 DB에는 연결하지 않는다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, make_url

from pipeline.collective.building_keys import main_lot_of
from pipeline.collective.migrate_p2_keys import server_url_from_env

TABLE = "rent_building_key_c2_units"
LOG_TABLE = "rent_c2_migration_log"
STEP = "load_rent_c2_units"

APPROVED_ROWS = 6054
APPROVED_SHA256 = "2660f8e2d75728caa06c6e7899141d8f7cbfbb7698c2bd89637b53ea22506681"

COLS = [
    "base_key",
    "asset_type",
    "beopjungri_code",
    "main_lot",
    "part",
    "decision",
    "evidence",
    "source",
    "collective_sha256",
    "note",
]
PK = ["base_key", "asset_type", "beopjungri_code", "main_lot"]
DECISIONS = {"split", "keep", "pending"}
EVIDENCE = {"", "collective_reuse", "collective_ledger", "title_register", "manual"}
FORBIDDEN_DBS = {
    "rent_stats",
    "collective_stats",
    "built_stats",
    "land_stats",
    "macro_ts",
    "platform",
    "postgres",
    "parcel_master",
}
REHEARSAL_DB = "rent_stats_rc2r"
FIXTURE_RE = re.compile(r"^ch2rent_c2u_p2r(_[a-z0-9]+)?$")

DDL = """
CREATE TABLE IF NOT EXISTS rent_building_key_c2_units (
    base_key varchar(64) NOT NULL,
    asset_type varchar(16) NOT NULL,
    beopjungri_code varchar(10) NOT NULL,
    main_lot varchar(16) NOT NULL,
    part integer NOT NULL,
    decision varchar(8) NOT NULL CHECK (decision IN ('split', 'keep', 'pending')),
    evidence varchar(32) NOT NULL DEFAULT ''
        CHECK (evidence IN ('', 'collective_reuse', 'collective_ledger', 'title_register', 'manual')),
    source varchar(32) NOT NULL,
    collective_sha256 char(64) NOT NULL,
    decided_at timestamptz NOT NULL DEFAULT now(),
    note text,
    PRIMARY KEY (base_key, asset_type, beopjungri_code, main_lot),
    CHECK (decision = 'keep' OR main_lot <> '')
);
CREATE TABLE IF NOT EXISTS rent_c2_migration_log (
    id bigserial PRIMARY KEY,
    step varchar(64) NOT NULL,
    detail jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
"""


class LoadError(RuntimeError):
    pass


class GuardError(RuntimeError):
    pass


def rent_engine(dbname: str, *, apply: bool, base_url: str | None = None) -> Engine:
    """fixture 연결. 이 역할의 기본값이 읽기 전용이라 쓸 때만 그 세션에서 끈다."""
    url = make_url(base_url or server_url_from_env()).set(database=dbname)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg2")
    mode = "off" if apply else "on"
    opts = f"-c statement_timeout=0 -c default_transaction_read_only={mode}"
    return create_engine(url, pool_pre_ping=True, connect_args={"options": opts})


def assert_rehearsal_local(target) -> None:
    ops = str(Path(__file__).resolve().parents[2] / "scripts" / "ops" / "collective_p2_verify")
    if ops not in sys.path:
        sys.path.insert(0, ops)
    from ops_guards import TargetError, assert_local_target

    try:
        assert_local_target(target)
    except TargetError as exc:
        raise GuardError(str(exc)) from None


def assert_write_db(name: str) -> None:
    if name == REHEARSAL_DB or FIXTURE_RE.fullmatch(name):
        return
    raise GuardError("이 적재기는 fixture 또는 리허설 데이터베이스만 연다")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_sha256(df: pd.DataFrame) -> str:
    cols = ["base_key", "asset_type", "beopjungri_code", "main_lot", "part", "decision", "evidence"]
    ordered = df[cols].sort_values(PK).reset_index(drop=True)
    lines = ["\t".join(cols)]
    for row in ordered.itertuples(index=False):
        lines.append("\t".join("" if v is None else str(v) for v in row))
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def check_approved_file(path: Path, df: pd.DataFrame, sha: str, rows: int) -> None:
    got = file_sha256(path)
    if got != sha or len(df) != rows:
        raise LoadError(
            f"승인 파일과 다름: 행 {len(df)} (기대 {rows}), "
            f"SHA 일치 {got == sha}"
        )


def read_units(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise LoadError(f"파일 없음: {path.name}")
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    missing = [c for c in COLS if c not in df.columns]
    if missing:
        raise LoadError("판정 파일에 필요한 열이 없다")
    out = df[COLS].copy()
    out["main_lot"] = out["main_lot"].map(lambda v: main_lot_of(v) or "")
    out["part"] = pd.to_numeric(out["part"], errors="coerce")
    return out


def validate(df: pd.DataFrame) -> None:
    if df.empty:
        raise LoadError("판정 파일이 비어 있다")
    if df["part"].isna().any() or (df["part"] < 0).any() or (df["part"] != df["part"].round()).any():
        raise LoadError("part가 0 이상의 정수가 아니다")
    bad_decision = ~df["decision"].isin(DECISIONS)
    if bad_decision.any():
        raise LoadError(f"decision 값이 범위 밖이다: {int(bad_decision.sum())}행")
    bad_evidence = ~df["evidence"].isin(EVIDENCE)
    if bad_evidence.any():
        raise LoadError(f"evidence 값이 범위 밖이다: {int(bad_evidence.sum())}행")
    bad_sha = ~df["collective_sha256"].str.fullmatch(r"[0-9a-f]{64}")
    if bad_sha.any():
        raise LoadError(f"collective SHA 형식이 아니다: {int(bad_sha.sum())}행")
    if df["source"].eq("").any() or df["base_key"].eq("").any() or df["beopjungri_code"].eq("").any():
        raise LoadError("base_key, 법정동, source는 비울 수 없다")
    if df["asset_type"].eq("").any():
        raise LoadError("asset_type은 비울 수 없다")
    needs_lot = df["decision"].ne("keep") & df["main_lot"].eq("")
    if needs_lot.any():
        raise LoadError(f"keep가 아닌데 본번이 없다: {int(needs_lot.sum())}행")
    if df.duplicated(PK).any():
        raise LoadError(f"기본키가 중복이다: {int(df.duplicated(PK).sum())}행")
    pending_part = df["decision"].eq("pending") & df["part"].ne(0)
    if pending_part.any():
        raise LoadError(f"pending의 part가 0이 아니다: {int(pending_part.sum())}행")


def final_state_errors(df: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    split = df[df["decision"].eq("split")]
    if not split.empty:
        group = ["base_key", "asset_type", "beopjungri_code"]
        parts = split.groupby(group, sort=False)["part"].agg(lambda s: set(int(v) for v in s))
        missing = int(sum(0 not in s for s in parts))
        single = int(sum(len(s) < 2 for s in parts))
        if missing:
            errors.append(f"분할 묶음에 part 0이 없다: {missing}")
        if single:
            errors.append(f"분할 묶음이 조각 하나뿐이다: {single}")
    # 집합 final_state_errors와 같다. part 0은 옛 key라 법정동을 넘어도 되고, 0이 아닌 조각만 거부한다.
    nonzero = df.loc[pd.to_numeric(df["part"], errors="coerce").fillna(0).ne(0)]
    if not nonzero.empty:
        crossed = int(
            nonzero.groupby(["base_key", "part"], sort=False)["beopjungri_code"].nunique().gt(1).sum()
        )
        if crossed:
            errors.append(f"0이 아닌 조각이 법정동을 넘는다: {crossed}")
    mixed = int(df.groupby("base_key", sort=False)["asset_type"].nunique().gt(1).sum())
    if mixed:
        errors.append(f"같은 base_key에 자산이 둘 이상이다: {mixed}")
    return errors


def _table_exists(conn: Connection) -> bool:
    return bool(conn.execute(text("SELECT to_regclass(:name)"), {"name": TABLE}).scalar())


def _read_current(conn: Connection) -> pd.DataFrame:
    if not _table_exists(conn):
        return pd.DataFrame(columns=PK + ["part", "decision", "evidence", "collective_sha256"])
    rows = conn.execute(text(
        f"SELECT {', '.join(PK)}, part, decision, evidence, collective_sha256 FROM {TABLE}"
    )).mappings().all()
    if not rows:
        return pd.DataFrame(columns=PK + ["part", "decision", "evidence", "collective_sha256"])
    out = pd.DataFrame(rows)
    out["part"] = pd.to_numeric(out["part"])
    return out


def compare(cur: pd.DataFrame, df: pd.DataFrame) -> dict:
    want = df[PK + ["part", "decision", "evidence", "collective_sha256"]].copy()
    want["part"] = want["part"].astype(int)
    if cur.empty:
        return {"insert": len(want), "same": 0, "conflict": 0}
    merged = want.merge(cur, on=PK, how="left", suffixes=("", "_db"), indicator=True)
    new = merged["_merge"].eq("left_only")
    both = merged["_merge"].eq("both")
    same = both & (
        merged["part"].astype(int).eq(merged["part_db"].astype(int))
        & merged["decision"].eq(merged["decision_db"])
        & merged["evidence"].eq(merged["evidence_db"])
        & merged["collective_sha256"].eq(merged["collective_sha256_db"])
    )
    return {
        "insert": int(new.sum()),
        "same": int(same.sum()),
        "conflict": int((both & ~same).sum()) + int(len(cur) - int(both.sum())),
    }


def summary(path: Path, df: pd.DataFrame, diff: dict) -> dict:
    return {
        "file": path.name,
        "rows": int(len(df)),
        "file_sha256": file_sha256(path),
        "content_sha256": content_sha256(df),
        "insert": diff["insert"],
        "same": diff["same"],
        "conflict": diff["conflict"],
        "split": int(df["decision"].eq("split").sum()),
        "keep": int(df["decision"].eq("keep").sum()),
        "pending": int(df["decision"].eq("pending").sum()),
    }


def _insert(conn: Connection, df: pd.DataFrame) -> None:
    payload = df[COLS].copy()
    payload["part"] = payload["part"].astype(int)
    payload["note"] = payload["note"].replace("", None)
    conn.execute(
        text(
            f"""
            INSERT INTO {TABLE}
                (base_key, asset_type, beopjungri_code, main_lot, part, decision,
                 evidence, source, collective_sha256, note)
            VALUES
                (:base_key, :asset_type, :beopjungri_code, :main_lot, :part, :decision,
                 :evidence, :source, :collective_sha256, :note)
            """
        ),
        payload.to_dict("records"),
    )


def _log(conn: Connection, info: dict) -> None:
    conn.execute(
        text(f"INSERT INTO {LOG_TABLE} (step, detail) VALUES (:step, CAST(:detail AS jsonb))"),
        {"step": STEP, "detail": json.dumps(info, ensure_ascii=False)},
    )


def load(engine: Engine, path: Path, df: pd.DataFrame, *, apply: bool) -> dict:
    errors = final_state_errors(df)
    if errors:
        raise LoadError("; ".join(errors))
    with engine.connect() as conn:
        cur = _read_current(conn)
        diff = compare(cur, df)
        info = summary(path, df, diff)
        if not apply:
            return info
        if diff["conflict"]:
            raise LoadError(f"이미 있는 판정과 값이 다르다: {diff['conflict']}")
        if diff["insert"] == 0:
            return info
        with engine.begin() as write:
            write.execute(text(DDL))
            fresh = _read_current(write)
            again = compare(fresh, df)
            if again["conflict"]:
                raise LoadError(f"이미 있는 판정과 값이 다르다: {again['conflict']}")
            new_keys = df.merge(fresh[PK], on=PK, how="left", indicator=True)
            _insert(write, new_keys[new_keys["_merge"].eq("left_only")])
            _log(write, info)
        return info


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="임대 C-2 판정 표 적재")
    parser.add_argument("--rent-db", required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--approved-sha256", default=None)
    parser.add_argument("--approved-rows", type=int, default=None)
    parser.add_argument(
        "--test-fixture-unapproved",
        action="store_true",
        help="테스트 fixture 전용. 승인 파일 검사를 건너뛴다",
    )
    args = parser.parse_args(argv)
    try:
        assert_write_db(args.rent_db)
        base = make_url(args.base_url or server_url_from_env()).set(database=args.rent_db)
        if args.rent_db == REHEARSAL_DB or (args.apply and args.test_fixture_unapproved):
            assert_rehearsal_local(base)
        df = read_units(args.csv)
        validate(df)
        if args.apply:
            if args.test_fixture_unapproved:
                if FIXTURE_RE.fullmatch(args.rent_db) is None:
                    raise GuardError("테스트 우회는 로컬 fixture 데이터베이스에서만 된다")
            else:
                if args.approved_sha256 not in (None, APPROVED_SHA256):
                    raise LoadError("승인 상수는 정해진 값만 쓸 수 있다")
                if args.approved_rows is not None and args.approved_rows != APPROVED_ROWS:
                    raise LoadError("승인 상수는 정해진 값만 쓸 수 있다")
                check_approved_file(args.csv, df, APPROVED_SHA256, APPROVED_ROWS)
        elif args.approved_sha256 is not None or args.approved_rows is not None:
            check_approved_file(
                args.csv,
                df,
                args.approved_sha256 or "",
                -1 if args.approved_rows is None else args.approved_rows,
            )
        engine = rent_engine(args.rent_db, apply=args.apply, base_url=args.base_url)
        try:
            info = load(engine, args.csv, df, apply=args.apply)
        finally:
            engine.dispose()
    except (LoadError, GuardError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(
        f"rows={info['rows']} insert={info['insert']} same={info['same']} "
        f"conflict={info['conflict']} apply={args.apply}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
