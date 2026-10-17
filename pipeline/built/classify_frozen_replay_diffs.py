"""Plan step 4-B: classify frozen enrichment rows that the current rerun does not reproduce.

Frozen = `built_transaction_enrichment` (2019+). Rerun = current code on the register caches.
Each differing row gets a type; rows whose parcel differs are checked against evidence not
used for matching (road name, approval year vs building age). Read-only; counts only.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "backend"))

from built.db_utils import get_built_engine  # noqa: E402
from built.recover_address import CACHE, TX_SQL, load_land_ledger  # noqa: E402
from built.replay_enrichment_from_ledger import FIELDS, norm, records, run_matching  # noqa: E402

FROZEN_SQL = """
SELECT e.transaction_hash, e.recovered_lot, e.match_tier, e.structure_raw, e.max_floor, e.approve_year,
       e.land_area_source, e.n_range, e.n_exact, e.snapshots_matched, e.matched_cycle,
       e.evidence->>'reg_road' AS reg_road, e.evidence->>'snapshot_via' AS via
FROM built_transaction_enrichment e
JOIN built_transactions t ON t.transaction_hash = e.transaction_hash
WHERE t.sigungu_code LIKE :sido_like AND t.contract_year >= 2019
"""


def road_ok(tx_road: str, reg_road) -> bool | None:
    if not tx_road or not isinstance(reg_road, str) or not reg_road:
        return None
    return tx_road in reg_road or reg_road in tx_road


def age_ok(contract_year, building_age, approve) -> bool | None:
    try:
        built = int(contract_year) - int(float(building_age))
        return abs(built - int(approve)) <= 1
    except (TypeError, ValueError):
        return None


def judge(old_road, old_age, new_road, new_age) -> str:
    old = [x for x in (old_road, old_age) if x is not None]
    new = [x for x in (new_road, new_age) if x is not None]
    if not old and not new:
        return "undecidable_no_evidence"
    if not old or not new:
        return "undecidable_one_side_no_evidence"
    if all(old) and not all(new):
        return "frozen_supported"
    if all(new) and not all(old):
        return "rerun_supported"
    if all(old) and all(new):
        return "both_supported"
    return "neither_supported"


def classify(frozen: dict, rerun: dict | None) -> str:
    if rerun is None:
        return "not_reproduced"
    bad = {k for k in FIELDS if norm(frozen[k]) != norm(rerun[k])}
    if "recovered_lot" in bad:
        return "parcel_differs"
    if "match_tier" in bad:
        return "tier_differs_same_parcel"
    if bad <= {"snapshots_matched", "n_range", "n_exact"}:
        return "snapshot_or_count_only"
    return "attribute_differs_same_parcel"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sidos", default="11,26,27,28,30,41,43,44,47,48,51,52")
    args = ap.parse_args()
    eng = get_built_engine()
    types = Counter()
    by_type_cycle: dict[str, Counter] = defaultdict(Counter)
    detail: dict[str, Counter] = defaultdict(Counter)
    judgements = Counter()
    all_cycles = Counter()
    for sido in args.sidos.split(","):
        with eng.connect() as conn:
            tx = pd.read_sql(text(TX_SQL), conn, params={"sido_like": f"{sido}%", "min_year": 2019})
            fz = pd.read_sql(text(FROZEN_SQL), conn, params={"sido_like": f"{sido}%"})
        res, _ = run_matching(tx, CACHE, sido, load_land_ledger(sido, False))
        rerun = records(res)
        by_hash = res.set_index("transaction_hash", drop=False)
        txi = tx.set_index("transaction_hash")
        for r in fz.itertuples(index=False):
            all_cycles[r.matched_cycle] += 1
            frozen = {k: getattr(r, k) for k in FIELDS}
            got = rerun.get(r.transaction_hash)
            if got is not None and all(norm(frozen[k]) == norm(got[k]) for k in FIELDS):
                continue
            kind = classify(frozen, got)
            types[kind] += 1
            by_type_cycle[kind][r.matched_cycle] += 1
            row = by_hash.loc[r.transaction_hash] if r.transaction_hash in by_hash.index else None
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            if kind == "not_reproduced" and row is not None:
                detail[kind][str(row["fail"])] += 1
            if kind == "snapshot_or_count_only" and got is not None:
                frozen_snap = (list(r.snapshots_matched) or ["-"])[0]
                detail[kind][f"{frozen_snap}->{(got['snapshots_matched'] or ['-'])[0]}|via={r.via}"] += 1
            if kind == "parcel_differs" and row is not None:
                t = txi.loc[r.transaction_hash]
                tx_road = str(row["tx_road"] or "")
                verdict = judge(
                    road_ok(tx_road, r.reg_road), age_ok(t["contract_year"], t["building_age"], r.approve_year),
                    road_ok(tx_road, row["reg_road"]), age_ok(t["contract_year"], t["building_age"], row["approve"]),
                )
                judgements[verdict] += 1
        print(sido, dict(types), flush=True)
    report = {
        "types": dict(types),
        "types_by_matched_cycle": {k: dict(v) for k, v in by_type_cycle.items()},
        "frozen_rows_by_matched_cycle": dict(all_cycles),
        "detail": {k: dict(v) for k, v in detail.items()},
        "parcel_differs_evidence": dict(judgements),
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
