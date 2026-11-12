"""Phase A-5 N-1 — 분양권 거래유형: 원천 파일 hash 대응률 측정 (읽기 전용).

transaction_hash = sha256('presale|' + 파일명 + '|' + 원본 첫 열). 원천 CSV를 적재기와 같은
함수(read_source_file → _attach_source_keys → refine_dataframe)로 다시 읽어 hash→올바른 deal_type 표를 만들고
DB의 2021-11~2025-08 분양권 행과 맞춘다. DB는 SELECT만.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd

from _db import OUT, ROOT, engine, md_table, q

sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "pipeline" / "collective"))
from collective.refine import read_source_file, refine_dataframe  # noqa: E402

spec = importlib.util.spec_from_file_location("imp", ROOT / "pipeline" / "collective" / "import_refined.py")
imp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imp)

RAW = Path(r"D:\ch2\ch2_Macro\raw")
t0 = time.time()


def log(*a):
    print(f"[{time.time()-t0:7.1f}s]", *a, flush=True)


def main():
    files = sorted(p for p in RAW.rglob("*.csv") if "분양입주권" in p.name and "failed" not in str(p.parent))
    log("candidate files", len(files))
    by_hash: dict[str, set[tuple[str, str]]] = defaultdict(set)  # hash -> {(deal_type, folder)}
    file_rows = []
    for p in files:
        try:
            raw, kind = read_source_file(p)
            keyed = imp._attach_source_keys(raw, p, input_kind=kind)
            df = refine_dataframe(keyed, "presale", input_kind=kind)
        except Exception as ex:  # noqa: BLE001
            file_rows.append((str(p.relative_to(RAW)), "ERR " + type(ex).__name__, 0))
            continue
        dt = df["deal_type"] if "deal_type" in df.columns else pd.Series([None] * len(df))
        for sk, v in zip(df["_source_key"], dt):
            h = hashlib.sha256(("presale|" + str(sk)).encode("utf-8")).hexdigest()
            by_hash[h].add((v if isinstance(v, str) else "", p.parent.name))
        file_rows.append((str(p.relative_to(RAW)), kind, len(df)))
    log("hashes", len(by_hash))
    with engine().connect() as c:
        db = pd.read_sql(
            """select transaction_hash, created_at::date as loaded, contract_date, deal_type
               from collective_transactions where asset_type='presale'
                 and contract_date >= '2021-11-01' and contract_date < '2025-09-01'""", c)
    db["bad"] = ~db["deal_type"].isin(["중개거래", "직거래"]) & db["deal_type"].notna()
    res = []
    for h in db["transaction_hash"]:
        s = by_hash.get(h)
        if not s:
            res.append(("no_match", ""))
            continue
        vals = {v for v, _ in s}
        if len(vals) > 1:
            # 개편 재적재(2026-07-02)는 staging 폴더 파일 — 그 폴더 값으로 고정 가능한지
            stg = {v for v, f in s if "201001_202605" in f or "전남광주" in f or "인천" in f}
            res.append(("ambiguous_staging_resolves" if len(stg) == 1 else "ambiguous", "|".join(sorted(f for _, f in s))))
        else:
            res.append(("match", next(iter(vals))))
    db["m"] = [r[0] for r in res]
    db["new_deal_type"] = [r[1] for r in res]
    g = db.groupby(["loaded", "bad", "m"]).size().reset_index(name="n")
    g2 = db[db.m == "match"].assign(nv=lambda x: x.new_deal_type.replace("", "(공란)")).groupby(["bad", "nv"]).size().reset_index(name="n")
    L = ["# A-5 N-1 분양권 hash 대응", "",
         f"- 원천 후보 파일 {len(files)}개, hash {len(by_hash):,}",
         md_table([tuple(str(x) if not isinstance(x, int) else x for x in r) for r in g.itertuples(index=False)], ["적재일", "비정상값", "대응", "행"]), "",
         "대응된 행의 새 거래유형:",
         md_table([tuple(str(x) if not isinstance(x, int) else x for x in r) for r in g2.itertuples(index=False)], ["비정상값", "새 값", "행"])]
    pd.DataFrame(file_rows, columns=["file", "kind", "rows"]).to_csv(OUT / "a5_presale_files.csv", index=False, encoding="utf-8-sig")
    (OUT / "a5_presale_result.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
