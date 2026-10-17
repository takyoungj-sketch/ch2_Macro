"""Plan step 4-F: one report of link, accuracy, coverage, temporal fitness and conflict metrics.

Inputs (local, read-only):
  built_link_quality_v1_rows.pkl  — proposed configuration, all eligible transactions (4-C)
  built_zone_asof_v1_rows.pkl     — contract-year zone status for linked rows (4-D)
  bldrgst_pk_shadow_v1.sqlite     — attr_shadow: identification class and per-variable values (4-E)

Denominators are kept apart: eligible transactions (E) and linked transactions (L).
Independent sample accuracy is reported as unverified until the sample worksheet is judged.
Counts only in the repo.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from built.measure_link_quality_v1 import ROWS, VERIFY  # noqa: E402
from built.measure_zone_asof_v1 import OUT_ROWS as ZONE_ROWS  # noqa: E402
from built.resolve_tied_bldrgst_pk_v1 import SHADOW  # noqa: E402

BUILDING_VARS = ("struct", "use", "floors", "approve")
ZONE_FIT = {"observed", "estimated"}
ZONE_NEAR = {"adjacent_before", "adjacent_after"}


def rate(n, d) -> float | None:
    return round(n / d, 4) if d else None


def load() -> pd.DataFrame:
    r = pd.read_pickle(ROWS)
    z = pd.read_pickle(ZONE_ROWS)[["transaction_hash", "status", "why", "stability"]]
    with sqlite3.connect(f"file:{SHADOW}?mode=ro", uri=True) as db:
        a = pd.read_sql("SELECT * FROM attr_shadow", db)
    a = a.rename(columns={v: f"b_{v}" for v in BUILDING_VARS})
    df = r.merge(z, on="transaction_hash", how="left").merge(a, on="transaction_hash", how="left")
    df["linked"] = df["tier"].notna()
    snap = df["snapshot_used"].dropna().str.slice(0, 4).astype(int) * 12 + df["snapshot_used"].dropna().str.slice(5, 7).astype(int)
    df["snap_gap_m"] = snap - (df["contract_year"] * 12 + df["contract_month"])
    return df


def coverage(g: pd.DataFrame) -> dict:
    """Per variable: confirmed supply, candidate-agree (not identification), missing. Denominator = rows of g."""
    n = len(g)
    lk = g[g["linked"]]
    out = {"eligible": n, "linked": len(lk), "link_rate": rate(len(lk), n)}
    ident = lk["identification"].value_counts().to_dict()
    out["identification"] = {k: int(ident.get(k, 0)) for k in ("confirmed", "candidates_agree", "candidates_conflict")}
    conf = lk["identification"] == "confirmed"
    agree = lk["identification"] == "candidates_agree"
    cflt = lk["identification"] == "candidates_conflict"
    vars_ = {}
    for v in BUILDING_VARS:
        has = lk[f"b_{v}"].notna()
        c, ag, cfv = int((conf & has).sum()), int(((agree | cflt) & has).sum()), int(lk[f"{v}_conflict"].fillna(0).sum())
        vars_[v] = {
            "confirmed_value": c,
            "candidate_same_value": ag,
            "candidate_conflict_missing": cfv,
            "of_eligible_confirmed": rate(c, n),
            "of_linked_confirmed": rate(c, len(lk)),
        }
    land = int(lk["slim_land"].notna().sum())
    vars_["land_area_slim"] = {"value": land, "of_eligible": rate(land, n), "of_linked": rate(land, len(lk))}
    fit = int(lk["status"].isin(ZONE_FIT).sum())
    near = int(lk["status"].isin(ZONE_NEAR).sum())
    vars_["zone_contract_year"] = {
        "contract_year_value": fit,
        "adjacent_year_value": near,
        "unknown": int((lk["status"] == "unknown").sum()),
        "of_eligible_contract_year": rate(fit, n),
        "of_linked_contract_year": rate(fit, len(lk)),
    }
    road = int(lk["reg_road"].notna().sum())
    vars_["register_road"] = {"value": road, "of_linked": rate(road, len(lk))}
    out["variables"] = vars_
    return out


def temporal(lk: pd.DataFrame) -> dict:
    n = len(lk)
    gap = lk["snap_gap_m"]
    bins = {
        "register_at_or_before_contract": int((gap <= 0).sum()),
        "after_1_12m": int(((gap > 0) & (gap <= 12)).sum()),
        "after_13_36m": int(((gap > 12) & (gap <= 36)).sum()),
        "after_37m_plus": int((gap > 36).sum()),
    }
    ap = pd.to_numeric(lk["approve"], errors="coerce")
    return {
        "denominator": "linked",
        "linked": n,
        "zone_status": lk["status"].value_counts().to_dict(),
        "zone_contract_year_rate": rate(int(lk["status"].isin(ZONE_FIT).sum()), n),
        "zone_stability": lk["stability"].value_counts().to_dict(),
        "register_snapshot_gap": bins,
        "register_after_contract_rate": rate(int((gap > 0).sum()), n),
        "approve_after_contract_year": int((ap > lk["contract_year"]).sum()),
    }


def conflicts(lk: pd.DataFrame) -> dict:
    n = len(lk)
    out = {"denominator": "linked", "linked": n}
    for v in BUILDING_VARS:
        k = int(lk[f"{v}_conflict"].fillna(0).sum())
        out[f"building_{v}"] = {"n": k, "rate": rate(k, n)}
    why = lk.loc[lk["status"] == "unknown", "why"].value_counts().to_dict()
    out["zone_unknown_why"] = why
    out["zone_next_base_differs"] = int((lk["stability"] == "next_base_differs").sum())
    land_bad = int((lk["land_a1_ok"] == False).sum())  # noqa: E712
    land_known = int(lk["land_a1_ok"].notna().sum())
    out["land_area_tx_vs_slim_differs"] = {"n": land_bad, "of_compared": land_known, "rate": rate(land_bad, land_known)}
    out["register_collective_link"] = int((lk["register"] == "집합").sum())
    return out


def by(df: pd.DataFrame, key: str) -> dict:
    return {str(k): coverage(g) for k, g in df.groupby(key, sort=True)}


def compact(rows: dict) -> dict:
    """Region/type/year table: link rate and confirmed coverage of key variables over eligible."""
    out = {}
    for k, c in rows.items():
        v = c["variables"]
        out[k] = {
            "eligible": c["eligible"],
            "linked": c["linked"],
            "link_rate": c["link_rate"],
            "confirmed_building": c["identification"]["confirmed"],
            "candidates_agree": c["identification"]["candidates_agree"],
            "candidates_conflict": c["identification"]["candidates_conflict"],
            "struct_confirmed_of_eligible": v["struct"]["of_eligible_confirmed"],
            "approve_confirmed_of_eligible": v["approve"]["of_eligible_confirmed"],
            "land_area_of_eligible": v["land_area_slim"]["of_eligible"],
            "zone_contract_year_of_eligible": v["zone_contract_year"]["of_eligible_contract_year"],
            "zone_contract_year_of_linked": v["zone_contract_year"]["of_linked_contract_year"],
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    df = load()
    lk = df[df["linked"]]
    report = {
        "step": "4-F",
        "config": "proposed: slim land area + Honam bridge (12); register caches 2024-09/2025-07/2026-07",
        "denominators": {
            "eligible": "2019+ composite transactions excluding partial ownership and missing code",
            "linked": "eligible rows with a building matched (tier A1/A2)",
        },
        "sample_accuracy": {
            "status": "unverified",
            "note": "stratified worksheet drawn (4-C), not judged; KAIS purposive 28 (25 right) is not an estimate",
        },
        "national": coverage(df),
        "temporal_fitness": temporal(lk),
        "conflict_rates": conflicts(lk),
        "by_sido": compact(by(df, "sido")),
        "by_asset": compact(by(df, "asset_type")),
        "by_residential": compact(by(df, "residential")),
        "by_contract_year": compact(by(df, "contract_year")),
        "temporal_by_contract_year": {str(y): temporal(g) for y, g in lk.groupby("contract_year")},
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=int), encoding="utf-8")
    nat = report["national"]
    print(json.dumps({"eligible": nat["eligible"], "linked": nat["linked"], "identification": nat["identification"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
