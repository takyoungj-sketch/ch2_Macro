#!/usr/bin/env python3
"""집합 2단계 N-1·N-2 — 거래유형(deal_type) 한 칸 보정. 행 삭제·재적재 없음.

N-1 분양권(계약 2021-11~2025-08): 옛 적재기가 중개사소재지 칸을 거래유형으로 넣었다(직거래는 공란).
     transaction_hash = sha256('presale|파일명|원본 첫 열') → 원천 CSV를 현행 적재 함수로 다시 읽어 hash로 찾는다.
N-2 비주거(계약 2021-11~, deal_type 공란): 적재기 INSERT에 deal_type 칸이 없었다(이번에 고침).
     hash = sha256(asset|source|i|price|gross_area|contract_year), i = 그 실행의 행 순번
     → 실행별 경로 목록 파일(logs/collective_cycle_*_paths.txt, logs/_reform_collective_paths.txt)을 같은 순서로 다시 읽는다.
     여러 실행에서 같은 hash가 나오고 값이 다르면 갱신하지 않는다(대응 불가로 집계).

기본 드라이런(읽기 전용). --apply 는 리허설 DB(…_p2r)에서만. 바꾸기 전 값은 *_dealtype_p2_before 에 남긴다.
--rollback 으로 그 값을 되돌린다.

  python pipeline/collective/fix_p2_deal_types.py --collective-db collective_stats_p2r [--presale] [--commercial] [--apply|--rollback]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "pipeline" / "collective"))
sys.path.insert(0, str(REPO / "pipeline" / "collective_commercial"))

from collective.migrate_p2_keys import PROTECTED, REHEARSAL_RE, GuardError, assert_rehearsal_db, engine_for  # noqa: E402
from collective.refine import read_source_file, refine_dataframe  # noqa: E402

log = logging.getLogger("fix_p2_deal_types")
KNOWN = ("중개거래", "직거래")
PRESALE_FROM, PRESALE_TO = "2021-11-01", "2025-09-01"
COMMERCIAL_FROM = "2021-11-01"
STAGING_TOKEN = "201001_202605"


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _import_refined():
    spec = importlib.util.spec_from_file_location("p2_imp", REPO / "pipeline" / "collective" / "import_refined.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------------------------------------------------------- 경로 재해석(폴더 이동 대응)

class PathResolver:
    """옛 경로(C:·E: 드라이브, 이동 전 폴더) → 현재 raw 아래 같은 「폴더/파일명」."""

    def __init__(self, raw_root: Path):
        self.raw = raw_root
        self._by_tail: dict[str, list[Path]] | None = None

    def _index(self) -> dict[str, list[Path]]:
        if self._by_tail is None:
            d: dict[str, list[Path]] = defaultdict(list)
            for p in self.raw.rglob("*.csv"):
                d[f"{p.parent.name}/{p.name}"].append(p)
            self._by_tail = d
        return self._by_tail

    def resolve(self, line: str) -> Path | None:
        s = line.strip().replace("/", "\\")
        if not s:
            return None
        low = s.lower()
        i = low.find("\\raw\\")
        if i >= 0:
            cand = self.raw / s[i + 5:]
            if cand.is_file():
                return cand
        parts = s.split("\\")
        hits = self._index().get(f"{parts[-2]}/{parts[-1]}", []) if len(parts) >= 2 else []
        return hits[0] if len(hits) == 1 else None


# ---------------------------------------------------------------- N-1

def presale_source_map(raw_root: Path) -> dict[str, dict[str, str]]:
    """hash → {deal_type 값: 폴더 경로} (값이 둘 이상이면 모호)."""
    imp = _import_refined()
    out: dict[str, dict[str, str]] = defaultdict(dict)
    files = sorted(p for p in raw_root.rglob("*.csv") if "분양입주권" in p.name and p.parent.name != "failed")
    for p in files:
        raw, kind = read_source_file(p)
        keyed = imp._attach_source_keys(raw, p, input_kind=kind)
        df = refine_dataframe(keyed, "presale", input_kind=kind)
        vals = df["deal_type"] if "deal_type" in df.columns else pd.Series([None] * len(df))
        for sk, v in zip(df["_source_key"], vals):
            out[_sha("presale|" + str(sk))][v if isinstance(v, str) else ""] = str(p.parent)
    log.info("presale files=%d hashes=%d", len(files), len(out))
    return out


def plan_presale(conn, raw_root: Path) -> tuple[pd.DataFrame, dict]:
    db = pd.read_sql(text("""SELECT id, transaction_hash, deal_type FROM collective_transactions
                             WHERE asset_type='presale' AND contract_date >= :a AND contract_date < :b
                               AND (deal_type IS NULL OR deal_type NOT IN ('중개거래','직거래'))"""),
                     conn, params={"a": PRESALE_FROM, "b": PRESALE_TO})
    src = presale_source_map(raw_root)
    new, status = [], []
    for h in db["transaction_hash"]:
        s = src.get(h)
        if not s:
            new.append(None); status.append("no_match"); continue
        if len(s) > 1:
            stg = {v for v, folder in s.items() if STAGING_TOKEN in folder}
            if len(stg) == 1:
                new.append(next(iter(stg)) or None); status.append("match_staging"); continue
            new.append(None); status.append("ambiguous"); continue
        v = next(iter(s))
        new.append(v or None); status.append("match")
    db["new_deal_type"] = new
    db["status"] = status
    upd = db[db["status"].str.startswith("match") & (db["new_deal_type"].fillna("") != db["deal_type"].fillna(""))]
    counts = dict(candidates=len(db), **db["status"].value_counts().to_dict(),
                  to_update=len(upd), new_values=upd["new_deal_type"].fillna("(공란)").value_counts().to_dict())
    return upd[["id", "deal_type", "new_deal_type"]], counts


# ---------------------------------------------------------------- N-2

def default_run_files(logs_dir: Path) -> list[Path]:
    files = sorted(logs_dir.glob("collective_cycle_*_paths.txt"))
    reform = logs_dir / "_reform_collective_paths.txt"
    return ([reform] if reform.is_file() else []) + files


def commercial_source_map(run_files: list[Path], resolver: PathResolver) -> tuple[dict[str, set[str]], dict]:
    from collective_commercial.molit_raw import load_collective_from_paths

    table: dict[str, set[str]] = defaultdict(set)
    info = {}
    for rf in run_files:
        lines = [ln for ln in rf.read_text(encoding="utf-8").splitlines() if ln.strip()]
        groups = (("collective_shop", "molit_shop_raw", "_상업업무_"), ("collective_factory", "molit_factory_raw", "_공장창고_"))
        miss = 0
        for asset, src, token in groups:
            paths = []
            for ln in lines:
                if token not in Path(ln.strip().replace("\\", "/")).name:
                    continue
                p = resolver.resolve(ln)
                if p is None:
                    miss += 1
                else:
                    paths.append(p)
            df = load_collective_from_paths(paths, asset_type=asset)
            for i, row in enumerate(df.itertuples(index=False)):
                th = _sha(f"{asset}|{src}|{i}|{row.price}|{row.gross_area}|{row.contract_year}")
                v = row.deal_type if isinstance(row.deal_type, str) and row.deal_type in KNOWN else ""
                table[th].add(v)
        info[rf.name] = {"missing_files": miss}
        if miss:
            log.warning("%s: 찾지 못한 파일 %d — 그 실행 행은 대응 실패로 남는다", rf.name, miss)
    return table, info


def plan_commercial(conn, run_files: list[Path], resolver: PathResolver) -> tuple[pd.DataFrame, dict]:
    db = pd.read_sql(text("""SELECT id, transaction_hash, deal_type FROM collective_commercial_transactions
                             WHERE deal_type IS NULL AND contract_date >= :a"""), conn, params={"a": COMMERCIAL_FROM})
    table, info = commercial_source_map(run_files, resolver)
    new, status = [], []
    for h in db["transaction_hash"]:
        s = table.get(h)
        if not s:
            new.append(None); status.append("no_match")
        elif len(s) > 1:
            new.append(None); status.append("collision")
        else:
            v = next(iter(s))
            new.append(v or None); status.append("match")
    db["new_deal_type"] = new
    db["status"] = status
    upd = db[(db["status"] == "match") & db["new_deal_type"].notna()]
    counts = dict(candidates=len(db), **db["status"].value_counts().to_dict(), to_update=len(upd),
                  new_values=upd["new_deal_type"].value_counts().to_dict(), runs=info)
    return upd[["id", "deal_type", "new_deal_type"]], counts


# ---------------------------------------------------------------- 쓰기·되돌리기

def apply_updates(conn, table: str, upd: pd.DataFrame) -> int:
    b = f"{table}_dealtype_p2_before"
    conn.execute(text(f"CREATE TABLE IF NOT EXISTS {b} (id bigint PRIMARY KEY, deal_type text, saved_at timestamptz DEFAULT now())"))
    rows = [{"id": int(i), "o": o if isinstance(o, str) else None, "n": n} for i, o, n in
            zip(upd["id"], upd["deal_type"], upd["new_deal_type"])]
    for i in range(0, len(rows), 5000):
        conn.execute(text(f"INSERT INTO {b} (id, deal_type) VALUES (:id, :o) ON CONFLICT (id) DO NOTHING"), rows[i:i + 5000])
    conn.execute(text("CREATE TEMP TABLE _p2_dt (id bigint PRIMARY KEY, deal_type text) ON COMMIT DROP"))
    for i in range(0, len(rows), 5000):
        conn.execute(text("INSERT INTO _p2_dt VALUES (:id, :n)"), rows[i:i + 5000])
    r = conn.execute(text(f"UPDATE {table} t SET deal_type = u.deal_type FROM _p2_dt u WHERE t.id = u.id"))
    return int(r.rowcount or 0)


def rollback_table(conn, table: str) -> int:
    b = f"{table}_dealtype_p2_before"
    if not conn.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": b}).scalar():
        return 0
    r = conn.execute(text(f"UPDATE {table} t SET deal_type = b.deal_type FROM {b} b WHERE t.id = b.id"))
    conn.execute(text(f"DROP TABLE {b}"))
    return int(r.rowcount or 0)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--collective-db", required=True)
    p.add_argument("--presale", action="store_true")
    p.add_argument("--commercial", action="store_true")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true")
    g.add_argument("--rollback", action="store_true")
    p.add_argument("--raw-root", default=str(REPO / "raw"))
    p.add_argument("--logs-dir", default=str(REPO / "logs"))
    p.add_argument("--run-file", action="append", default=[], help="비주거 실행 경로 목록(여러 번). 기본: logs-dir 의 목록 전체")
    p.add_argument("--base-url", default="")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    do_p = a.presale or not a.commercial
    do_c = a.commercial or not a.presale
    write = a.apply or a.rollback
    if write and (a.collective_db in PROTECTED or not REHEARSAL_RE.match(a.collective_db)):
        raise GuardError(f"쓰기 대상 DB 이름이 리허설 이름(…_p2r)이 아님: {a.collective_db}")
    eng = engine_for(a.collective_db, read_only=not write, base_url=a.base_url or None)
    if a.rollback:
        with eng.begin() as conn:
            assert_rehearsal_db(conn, a.collective_db)
            out = {"presale": rollback_table(conn, "collective_transactions") if do_p else None,
                   "commercial": rollback_table(conn, "collective_commercial_transactions") if do_c else None}
        print(json.dumps(out, ensure_ascii=False))
        return 0
    raw_root = Path(a.raw_root)
    res = {}
    with eng.connect() as conn:
        if do_p:
            up_p, res["presale"] = plan_presale(conn, raw_root)
        if do_c:
            runs = [Path(x) for x in a.run_file] or default_run_files(Path(a.logs_dir))
            up_c, res["commercial"] = plan_commercial(conn, runs, PathResolver(raw_root))
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    if not a.apply:
        print("드라이런 — 쓰지 않았다.")
        return 0
    with eng.begin() as conn:
        assert_rehearsal_db(conn, a.collective_db)
        if do_p:
            res["presale_updated"] = apply_updates(conn, "collective_transactions", up_p)
        if do_c:
            res["commercial_updated"] = apply_updates(conn, "collective_commercial_transactions", up_c)
    print(json.dumps({k: v for k, v in res.items() if k.endswith("_updated")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
