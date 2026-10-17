"""Plan step 4-E: management key (bldrgst_pk) for linked composite transactions, in a shadow file.

Most links have one nearest-gross building on the parcel and keep its key. For ties (several
buildings with the same nearest gross area) a key is filled only with direct evidence:
  same_pk_duplicate          — every tied row carries the same key (one building listed twice)
  others_approved_after      — all other candidates were approved after the contract month,
                               so they did not exist when the deal was made
Matching approval year or floors alone is not enough; those are counted as hints and held.
Output: local SQLite outside the repo (no DB / enrichment writes). Counts only in the report.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "backend"))

from built.measure_link_quality_v1 import ROWS, VERIFY  # noqa: E402
from built.recover_address import CACHE, GROSS_TOL, to_f, to_i  # noqa: E402
from built.register_ledger import connect as ledger_connect  # noqa: E402
from built.replay_honam_bridge import BRIDGED  # noqa: E402

SHADOW = VERIFY / "bldrgst_pk_shadow_v1.sqlite"
RAW = {"register": 1, "dong": 22, "main_annex": 23, "struct": 32, "use": 35, "floors": 43, "approve": 60}


def tied_buildings(sido: str, snap: str, parcels: set[str], gross: dict[str, list[float]]) -> dict:
    folder = BRIDGED if sido == "12" else CACHE
    t = pd.read_csv(folder / f"title_{sido}_{snap}.csv", dtype=str, keep_default_na=False)
    key = (t["sigungu_code"].str.strip() + t["bjd_code"].str.strip() + "|"
           + t["bun"].map(lambda b: str(to_i(b))) + t["ji"].map(lambda j: f"-{to_i(j)}" if to_i(j) else ""))
    t = t[key.isin(parcels)].assign(parcel=key[key.isin(parcels)])
    out = defaultdict(list)
    for r in t.itertuples(index=False):
        out[r.parcel].append({"pk": r.pk.strip(), "gross": to_f(r.gross_area)})
    return out


def raw_attrs(db: sqlite3.Connection, pks: list[str]) -> dict[str, dict]:
    out = {}
    for i in range(0, len(pks), 900):
        chunk = pks[i:i + 900]
        q = f"SELECT pk, raw FROM title_version WHERE pk IN ({','.join('?' * len(chunk))})"
        for pk, raw in db.execute(q, chunk):
            p = raw.decode("cp949", errors="replace").split("|")
            if len(p) <= max(RAW.values()):
                continue
            out[pk] = {k: p[i].strip() for k, i in RAW.items()}
    return out


def decide(cands: list[str], attrs: dict, contract_ym: int) -> tuple[str | None, str, list[str]]:
    hints = []
    if len(set(cands)) == 1:
        return cands[0], "same_pk_duplicate", hints
    cands = sorted(set(cands))
    existed = []
    for pk in cands:
        a = attrs.get(pk, {})
        ap = a.get("approve", "")
        if len(ap) >= 6 and ap[:6].isdigit() and int(ap[:6]) > contract_ym:
            continue
        existed.append(pk)
    if len(existed) == 1:
        return existed[0], "others_approved_after", hints
    pool = existed or cands
    sig = {tuple(attrs.get(pk, {}).get(k) for k in ("struct", "use", "floors", "approve")) for pk in pool}
    if len(sig) == 1:
        hints.append("attributes_identical")
    kinds = Counter(attrs.get(pk, {}).get("register") for pk in pool)
    if kinds.get("1") == 1 and len(pool) > 1:
        hints.append("one_general_rest_collective")
    mains = Counter(attrs.get(pk, {}).get("main_annex") for pk in pool)
    if mains.get("0") == 1 and len(pool) > 1:
        hints.append("one_main_rest_annex")
    return None, "held_ambiguous", hints


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    df = pd.read_pickle(ROWS)
    linked = df[df["tier"].notna()].copy()
    ties = linked[linked["register"] == "동률"]
    db = ledger_connect()
    decided: dict[str, tuple] = {}
    hint_counts = Counter()
    for (sido, snap), g in ties.groupby(["sido", "snapshot_used"]):
        b = tied_buildings(sido, snap, set(g["parcel"]), {})
        cand_by_hash = {}
        for r in g.itertuples(index=False):
            blds = [x for x in b.get(r.parcel, []) if not math.isnan(x["gross"])]
            if not blds:
                cand_by_hash[r.transaction_hash] = []
                continue
            near = min(abs(x["gross"] - r.gross_area) for x in blds)
            cand_by_hash[r.transaction_hash] = [
                x["pk"] for x in blds if abs(abs(x["gross"] - r.gross_area) - near) <= 1e-9 and near <= GROSS_TOL
            ]
        attrs = raw_attrs(db, sorted({pk for c in cand_by_hash.values() for pk in c}))
        for r in g.itertuples(index=False):
            cands = cand_by_hash[r.transaction_hash]
            if not cands:
                decided[r.transaction_hash] = (None, "held_no_candidates", len(cands), "")
                continue
            ym = int(r.contract_year) * 100 + int(r.contract_month or 12)
            pk, rule, hints = decide(cands, attrs, ym)
            for h in hints:
                hint_counts[h] += 1
            decided[r.transaction_hash] = (pk, rule, len(set(cands)), ",".join(hints))
        print(sido, snap, len(g), flush=True)

    rows = []
    rule_by = defaultdict(Counter)
    for r in linked.itertuples(index=False):
        if r.transaction_hash in decided:
            pk, rule, n, hints = decided[r.transaction_hash]
        else:
            pk, rule, n, hints = (r.bldrgst_pk, "unique_nearest", 1, "")
        rows.append((r.transaction_hash, pk, rule, n, hints, r.snapshot_used))
        for k in ("all", f"asset:{r.asset_type}", f"sido:{r.sido}"):
            rule_by[k][rule] += 1
    SHADOW.unlink(missing_ok=True)
    out = sqlite3.connect(SHADOW)
    out.execute(
        "CREATE TABLE pk_shadow (transaction_hash TEXT PRIMARY KEY, bldrgst_pk TEXT, rule TEXT NOT NULL,"
        " n_candidates INTEGER, hints TEXT, snapshot_used TEXT)"
    )
    out.executemany("INSERT INTO pk_shadow VALUES (?,?,?,?,?,?)", rows)
    out.execute("CREATE TABLE info (k TEXT PRIMARY KEY, v TEXT)")
    out.executemany("INSERT INTO info VALUES (?,?)", [
        ("source", "measure_link_quality_v1 proposed config"), ("rule_version", "BLDRGST_PK_SHADOW_V1"),
    ])
    out.commit()
    out.close()
    report = {
        "linked": int(len(linked)), "ties": int(len(ties)),
        "rules": {k: dict(v) for k, v in rule_by.items()},
        "held_hints": dict(hint_counts),
        "shadow_file": str(SHADOW),
        "note": "hints are not used to fill; only same_pk_duplicate and others_approved_after fill a key",
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("linked", "ties", "held_hints")}, ensure_ascii=False))
    print(json.dumps(report["rules"]["all"], ensure_ascii=False))


if __name__ == "__main__":
    main()
