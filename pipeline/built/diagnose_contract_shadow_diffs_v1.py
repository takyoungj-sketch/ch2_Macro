"""Plan step 9 (input): why zone display differs between the frozen enrichment and the contract test table,
and where the 285 orphan enrichment rows came from.

Zone: for frozen rows that are linked in the test table and have both values, each difference is put in one
bucket — representative-label rule (the new label is among the frozen AL_D155 labels), observation time
(slim value changed between contract year and latest), source difference (new label not among AL_D155
labels), with the transaction-source zone (상가·공장 원장) as a third witness and the building cross-checks
as a link-error flag.

Orphans: frozen rows whose hash is no longer in built_transactions. The hash covers asset, address, lot,
contract year, price, gross area and building use, so a corrected row comes back with a new hash and a
cancelled row is dropped at refine. An orphan with a current row on the same legal dong and road, in the
snapshot window, linked to the same parcel and not frozen, is counted as "likely re-hashed".

Read-only. Counts only.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "backend"))

from app.built.enrichment_join import ZONE_COARSE_LABELS, canonical_zone_label  # noqa: E402
from built.build_link_contract_shadow_v1 import OUT as SHADOW_DB  # noqa: E402
from built.db_utils import get_built_engine  # noqa: E402
from built.measure_link_quality_v1 import ROWS  # noqa: E402

FROZEN_SQL = """
SELECT e.transaction_hash, e.zone_labels, e.zone_source, e.recovered_lot, e.evidence->>'snapshot_used' AS snap,
       e.evidence->>'tx_road' AS tx_road, t.transaction_hash IS NOT NULL AS in_ledger,
       t.asset_type, t.zone_type AS tx_zone
FROM built_transaction_enrichment e
LEFT JOIN built_transactions t ON t.transaction_hash = e.transaction_hash
"""
CURRENT_SQL = """
SELECT transaction_hash, beopjungri_code, road_name, contract_year, contract_month
FROM built_transactions WHERE contract_year >= 2025
"""
SNAP_WINDOW = {"2025-07": ((2025, 7), (2026, 6)), "2026-07": ((2026, 7), (2099, 12)), "2024-09": ((2024, 9), (2025, 6))}


def fine_set(labels) -> set[str]:
    out = set()
    for raw in labels or []:
        for part in str(raw).split(","):
            t = part.strip()
            if t and t.lower() != "nan" and t not in ZONE_COARSE_LABELS:
                c = canonical_zone_label([t])
                if c:
                    out.add(c)
    return out


def canon(x) -> str | None:
    return canonical_zone_label([x]) if isinstance(x, str) and x.strip() else None


def zone_diff(fz: pd.DataFrame, new: pd.DataFrame, rows: pd.DataFrame) -> dict:
    df = fz[fz["in_ledger"]].merge(new, on="transaction_hash", how="inner").merge(
        rows[["transaction_hash", "road_ok", "approve_ok", "register"]], on="transaction_hash", how="left")
    df["old"] = df["zone_labels"].map(lambda v: canonical_zone_label(list(v) if v is not None else []))
    df["old_set"] = df["zone_labels"].map(fine_set)
    df["tx"] = df["tx_zone"].map(canon)
    df["latest"] = df["zone_latest"].map(canon)
    df["cy"] = df["zone_contract_year"].map(canon)
    df["link_flag"] = (
        (df["road_ok"] == False) | (df["approve_ok"] == False) | (df["register"] == "집합")  # noqa: E712
    ).fillna(False).astype(bool)
    out = {"compared_rows": int(len(df))}
    for var in ("latest", "cy"):
        both = df[df["old"].notna() & df[var].notna()]
        diff = both[both["old"] != both[var]]
        buckets = Counter()
        witness = Counter()
        pairs = Counter()
        for r in diff.itertuples(index=False):
            new_v = getattr(r, var)
            if var == "cy" and isinstance(r.latest, str) and new_v != r.latest:
                b = "observation_time"
            elif new_v in r.old_set:
                b = "representative_rule"
            else:
                b = "source_difference"
            buckets[b] += 1
            if not isinstance(r.tx, str):
                w = "no_tx_zone"
            elif r.tx == new_v and r.tx != r.old:
                w = "tx_agrees_new"
            elif r.tx == r.old and r.tx != new_v:
                w = "tx_agrees_old"
            else:
                w = "tx_agrees_neither"
            witness[f"{b}|{w}"] += 1
            if b == "source_difference" and r.link_flag:
                witness[f"{b}|link_crosscheck_failed"] += 1
            pairs[f"{r.old} -> {new_v}"] += 1
        out[var] = {
            "both_present": int(len(both)),
            "same": int(len(both) - len(diff)),
            "differs": int(len(diff)),
            "buckets": dict(buckets),
            "witness": dict(sorted(witness.items())),
            "old_multi_label_among_diffs": int((diff["old_set"].map(len) > 1).sum()),
            "top_pairs": dict(pairs.most_common(15)),
            "old_missing_new_present": int((df["old"].isna() & df[var].notna()).sum()),
            "old_present_new_missing": int((df["old"].notna() & df[var].isna()).sum()),
            "old_missing_reason": {
                "zone_source_null": int((df["old"].isna() & df["zone_source"].isna()).sum()),
                "coarse_only": int((df["old"].isna() & df["zone_source"].notna()).sum()),
            },
        }
    # where the transaction-source zone exists (상가·공장), which side matches it
    tx = df[df["tx"].notna()]
    out["tx_zone_agreement"] = {
        "rows_with_tx_zone": int(len(tx)),
        "old_display": int((tx["old"] == tx["tx"]).sum()),
        "old_any_label": int(sum(t in s for t, s in zip(tx["tx"], tx["old_set"]))),
        "new_latest": int((tx["latest"] == tx["tx"]).sum()),
        "new_contract_year": int((tx["cy"] == tx["tx"]).sum()),
    }
    return out


def orphans(fz: pd.DataFrame, cur: pd.DataFrame, rows: pd.DataFrame) -> dict:
    orph = fz[~fz["in_ledger"]].copy()
    frozen = set(fz["transaction_hash"])
    parcel = rows.set_index("transaction_hash")["parcel"].to_dict()
    cur = cur[~cur["transaction_hash"].isin(frozen)]
    by_key = {}
    for r in cur.itertuples(index=False):
        by_key.setdefault((r.beopjungri_code, r.road_name), []).append(r)
    kinds = Counter()
    for r in orph.itertuples(index=False):
        bjd = (r.recovered_lot or "").split("|")[0]
        lo, hi = SNAP_WINDOW.get(r.snap, ((0, 0), (9999, 12)))
        cands = [
            c for c in by_key.get((bjd, r.tx_road), [])
            if lo <= (c.contract_year, c.contract_month) <= hi and parcel.get(c.transaction_hash) == r.recovered_lot
        ]
        if cands:
            kinds["likely_rehashed_same_parcel"] += 1
        elif by_key.get((bjd, r.tx_road)):
            kinds["same_road_other_parcel_only"] += 1
        else:
            kinds["no_current_row_on_road"] += 1
    return {
        "frozen_rows": int(len(fz)),
        "orphans": int(len(orph)),
        "by_snapshot": orph["snap"].value_counts().to_dict(),
        "by_sido": orph["recovered_lot"].str.slice(0, 2).value_counts().to_dict(),
        "classification": dict(kinds),
        "hash_fields": "asset_type, addr1-5, lot_number, contract_year, price, gross_area, building_use",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    with get_built_engine().connect() as c:
        fz = pd.read_sql(text(FROZEN_SQL), c)
        cur = pd.read_sql(text(CURRENT_SQL), c)
    with sqlite3.connect(f"file:{SHADOW_DB}?mode=ro", uri=True) as s:
        new = pd.read_sql(
            "SELECT target_key AS transaction_hash, variable, value_text FROM ledger_link_value_v1"
            " WHERE variable IN ('zone_latest','zone_contract_year')", s
        ).pivot(index="transaction_hash", columns="variable", values="value_text").reset_index()
    rows = pd.read_pickle(ROWS)
    rep = {"step": "9-input", "zone": zone_diff(fz, new, rows), "orphans": orphans(fz, cur, rows)}
    args.out.write_text(json.dumps(rep, ensure_ascii=False, indent=2, default=int), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1, default=int))


if __name__ == "__main__":
    main()
