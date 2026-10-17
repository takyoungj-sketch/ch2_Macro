"""Plan step 4-A: for sido 12, judge parcel/tier changes between current caches and the bridged
2024-09/2025-07 caches (built by replay_honam_bridge) with evidence not used for matching."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "backend"))

from built.classify_frozen_replay_diffs import age_ok, judge, road_ok  # noqa: E402
from built.db_utils import get_built_engine  # noqa: E402
from built.recover_address import CACHE, TX_SQL, load_land_ledger  # noqa: E402
from built.replay_enrichment_from_ledger import run_matching  # noqa: E402
from built.replay_honam_bridge import BRIDGED  # noqa: E402


def evidence(r) -> tuple:
    return road_ok(r["tx_road"], r["reg_road"]), age_ok(r["contract_year"], r["tx_age"], r["approve"])


def one_side(road, age) -> str:
    seen = [x for x in (road, age) if x is not None]
    if not seen:
        return "no_evidence"
    if all(seen):
        return "supported"
    return "contradicted" if not any(seen) else "partly_contradicted"


def rate(res: pd.DataFrame) -> dict:
    conf = res[res["tier"].notna()]
    road = [road_ok(r["tx_road"], r["reg_road"]) for _, r in conf.iterrows()]
    age = [age_ok(r["contract_year"], r["tx_age"], r["approve"]) for _, r in conf.iterrows()]
    road = [x for x in road if x is not None]
    age = [x for x in age if x is not None]
    return {
        "confirmed": len(conf),
        "road_checked": len(road), "road_agree": sum(road),
        "approve_checked": len(age), "approve_agree": sum(age),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--followup", type=Path, help="local CSV of rows to re-check (kept outside the repo)")
    args = ap.parse_args()
    followup: list[dict] = []
    with get_built_engine().connect() as conn:
        tx = pd.read_sql(text(TX_SQL), conn, params={"sido_like": "12%", "min_year": 2019})
    land = load_land_ledger("12", False)
    cur, _ = run_matching(tx, CACHE, "12", land)
    brg, _ = run_matching(tx, BRIDGED, "12", land)
    a = cur.set_index("transaction_hash")
    b = brg.set_index("transaction_hash")
    both = a.index[a["tier"].notna()].intersection(b.index[b["tier"].notna()])
    verdicts = {"parcel_differs": Counter(), "new_in_bridged": Counter(), "lost_in_bridged": Counter()}
    for h in both:
        if a.at[h, "parcel"] != b.at[h, "parcel"]:
            v = judge(*evidence(a.loc[h]), *evidence(b.loc[h]))
            verdicts["parcel_differs"][v] += 1
            if v != "rerun_supported":
                followup.append({"transaction_hash": h, "sido": "12", "source": "4A_parcel_differs", "detail": v,
                                 "lot_a": a.at[h, "parcel"], "lot_b": b.at[h, "parcel"]})
    for h in b.index[b["tier"].notna()].difference(both):
        v = one_side(*evidence(b.loc[h]))
        verdicts["new_in_bridged"][v] += 1
        if v in ("contradicted", "partly_contradicted"):
            followup.append({"transaction_hash": h, "sido": "12", "source": "4A_new_in_bridged", "detail": v,
                             "lot_a": "", "lot_b": b.at[h, "parcel"]})
    for h in a.index[a["tier"].notna()].difference(both):
        verdicts["lost_in_bridged"][one_side(*evidence(a.loc[h]))] += 1
    if args.followup:
        pd.DataFrame(followup).to_csv(args.followup, index=False, encoding="utf-8-sig")
    report = {
        "auto_check_current": rate(cur),
        "auto_check_bridged": rate(brg),
        "verdicts": {k: dict(v) for k, v in verdicts.items()},
        "note": "auto cross-check agreement, not link accuracy",
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
