"""Replay composite enrichment matching with ledger-supplied register caches (plan step 4).

Per province: (1) current raw caches vs ledger-ordered caches, (2) current rerun vs frozen
`built_transaction_enrichment` rows, (3) whether the matched building's management key is
uniquely determined (for `bldrgst_pk`). Reads the DB only. Writes counts only.
Zone labels are excluded: their supply (AL_D155) does not change here.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "backend"))

from built.db_utils import get_built_engine  # noqa: E402
from built.enrichment_rows import to_enrichment_records  # noqa: E402
from built.recover_address import (  # noqa: E402
    CACHE, GROSS_TOL, PRIMARY, SNAPSHOTS, TX_SQL, build_parcels, load_land_ledger, match_all, to_f, to_i,
)
from built.replay_register_cache_from_ledger import SCRATCH  # noqa: E402
from built.snapshot_policy import apply_snapshot_policy  # noqa: E402

FIELDS = ("recovered_lot", "match_tier", "structure_raw", "max_floor", "approve_year",
          "land_area_source", "n_range", "n_exact", "snapshots_matched")
FROZEN_SQL = """
SELECT e.transaction_hash, e.recovered_lot, e.match_tier, e.structure_raw, e.max_floor, e.approve_year,
       e.land_area_source, e.n_range, e.n_exact, e.snapshots_matched, e.bldrgst_pk
FROM built_transaction_enrichment e
JOIN built_transactions t ON t.transaction_hash = e.transaction_hash
WHERE t.sigungu_code LIKE :sido_like AND t.contract_year >= 2019
"""


def run_matching(tx: pd.DataFrame, folder: Path, sido: str, land_ledger: dict) -> tuple[pd.DataFrame, dict]:
    results = {}
    titles = {}
    for snap in SNAPSHOTS:
        title = pd.read_csv(folder / f"title_{sido}_{snap}.csv", dtype=str, keep_default_na=False)
        summ = pd.read_csv(folder / f"summary_{sido}_{snap}.csv", dtype=str, keep_default_na=False)
        parcels, idx = build_parcels(title, summ, land_ledger)
        results[snap] = match_all(tx, parcels, idx)
        titles[snap] = title
    return apply_snapshot_policy(results, policy="time_fallback", primary=PRIMARY), titles


def records(res: pd.DataFrame) -> dict[str, dict]:
    recs = to_enrichment_records(res, None, coverage_scope="replay", matched_cycle="replay")
    return {r["transaction_hash"]: {k: r.get(k) for k in FIELDS} for r in recs}


def norm(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, (list, tuple)):
        return tuple(v)
    return v


def diff(a: dict[str, dict], b: dict[str, dict]) -> dict:
    out = Counter()
    fields = Counter()
    for h in a.keys() | b.keys():
        if h not in b:
            out["only_left"] += 1
        elif h not in a:
            out["only_right"] += 1
        else:
            bad = [k for k in FIELDS if norm(a[h][k]) != norm(b[h][k])]
            out["identical" if not bad else "different"] += 1
            for k in bad:
                fields[k] += 1
    return {**dict(out), "field_diff": dict(fields)}


def pk_resolution(res: pd.DataFrame, titles: dict[str, pd.DataFrame]) -> Counter:
    """Is the chosen building (nearest gross on the chosen parcel) a single management key?"""
    by_parcel = {}
    for snap, t in titles.items():
        bjd10 = t["sigungu_code"].str.strip() + t["bjd_code"].str.strip()
        lot = [
            f"{to_i(b)}-{to_i(j) or 0}" if (to_i(j) or 0) else f"{to_i(b)}"
            for b, j in zip(t["bun"], t["ji"])
        ]
        keys = bjd10 + "|" + pd.Series(lot, index=t.index)
        by_parcel[snap] = t.assign(_key=keys).groupby("_key")
    out = Counter()
    for r in res.itertuples(index=False):
        if r.tier not in ("A1", "A2") or not isinstance(r.parcel, str) or not isinstance(r.transaction_hash, str):
            continue
        g = r.gross_area
        try:
            group = by_parcel[r.snapshot_used].get_group(r.parcel)
        except KeyError:
            out["parcel_not_found"] += 1
            continue
        gross = group["gross_area"].map(to_f)
        dist = (gross - g).abs()
        best = dist.min()
        n = int(((dist - best).abs() <= 1e-9).sum())
        out["unique_pk" if n == 1 and best <= GROSS_TOL else "tied_pk" if n > 1 else "no_exact_building"] += 1
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sidos", default="")
    args = ap.parse_args()
    sidos = [s for s in args.sidos.split(",") if s] or sorted(
        {p.name.split("_")[1] for p in CACHE.glob("title_*_2026-07.csv")}
    )
    eng = get_built_engine()
    report: dict = {"rule": "time_fallback, primary " + PRIMARY, "results": {}}
    total = Counter()
    for sido in sidos:
        started = time.time()
        with eng.connect() as conn:
            tx = pd.read_sql(text(TX_SQL), conn, params={"sido_like": f"{sido}%", "min_year": 2019})
            frozen_df = pd.read_sql(text(FROZEN_SQL), conn, params={"sido_like": f"{sido}%"})
        land_ledger = load_land_ledger(sido, False)
        res_cache, titles = run_matching(tx, CACHE, sido, land_ledger)
        res_ledger, _ = run_matching(tx, SCRATCH, sido, land_ledger)
        a, b = records(res_cache), records(res_ledger)
        frozen = {
            r.transaction_hash: {k: getattr(r, k) for k in FIELDS} for r in frozen_df.itertuples(index=False)
        }
        row = {
            "transactions": len(tx),
            "confirmed_cache_run": len(a),
            "confirmed_ledger_run": len(b),
            "frozen_rows": len(frozen),
            "frozen_bldrgst_pk_filled": int(frozen_df["bldrgst_pk"].notna().sum()),
            "cache_vs_ledger": diff(a, b),
            "frozen_vs_rerun": diff(frozen, a),
            "bldrgst_pk_resolution": dict(pk_resolution(res_ledger, titles)),
            "seconds": round(time.time() - started, 1),
        }
        report["results"][sido] = row
        for k in ("transactions", "confirmed_cache_run", "confirmed_ledger_run", "frozen_rows"):
            total[k] += row[k]
        for side in ("cache_vs_ledger", "frozen_vs_rerun"):
            for k, v in row[side].items():
                if k != "field_diff":
                    total[f"{side}.{k}"] += v
        for k, v in row["bldrgst_pk_resolution"].items():
            total[f"pk.{k}"] += v
        print(f"{sido} tx={len(tx):,} cache={len(a):,} ledger={len(b):,} frozen={len(frozen):,} "
              f"c-vs-l={row['cache_vs_ledger']} {row['seconds']}s", flush=True)
        args.out.write_text(json.dumps({**report, "total": dict(total)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dict(total), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
