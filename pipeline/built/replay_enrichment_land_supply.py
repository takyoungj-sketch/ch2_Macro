"""Swap the A2 land-area fallback from AL_D003 (latest, 대 only) to land trait slim v1 (plan step 4).

Same register caches (ledger-ordered), same rules. Only the third land-area fallback changes.
Slim value = area of the latest asof row whose jimok is 08 (대), general lots only.
Both sources are read-only. Writes counts only.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
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
from built.recover_address import CACHE, SNAPSHOTS, TX_SQL, load_land_ledger, lot_str, to_f, to_i  # noqa: E402
from built.replay_enrichment_from_ledger import diff, records, run_matching  # noqa: E402
from built.replay_register_cache_from_ledger import SCRATCH  # noqa: E402

SLIM = Path(r"C:\CH2\parcel_master\land_trait_slim_v1.sqlite")
INT64_MAX = 2**63 - 1


def slim_land(slim: sqlite3.Connection, keys: set[tuple[str, int, int]]) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for bjd10, bun, ji in sorted(keys):
        if not (len(bjd10) == 10 and bjd10.isdigit()) or bun > 9999 or ji > 9999:
            continue
        pnu = int(f"{bjd10}1{bun:04d}{ji:04d}")
        if pnu > INT64_MAX:
            continue
        best = None
        for year, month, mask, jimok, area in slim.execute(
            "SELECT price_year, price_month, asof_mask, jimok_code, area FROM observation WHERE pnu=?", (pnu,)
        ):
            rank = (mask.bit_length(), year, month)
            if best is None or rank > best[0]:
                best = (rank, jimok, area)
        if best and best[1] == "08":
            a = to_f(best[2])
            if a == a:
                out[(bjd10, lot_str(bun, ji))] = a
    return out


def title_keys(sido: str) -> set[tuple[str, int, int]]:
    keys = set()
    for snap in SNAPSHOTS:
        t = pd.read_csv(SCRATCH / f"title_{sido}_{snap}.csv", dtype=str, keep_default_na=False)
        for sg, bd, b, j in zip(t["sigungu_code"], t["bjd_code"], t["bun"], t["ji"]):
            bun = to_i(b)
            if bun is not None:
                keys.add((sg.strip() + bd.strip(), bun, to_i(j) or 0))
    return keys


def compare_dicts(old: dict, new: dict, keys: set[tuple[str, int, int]]) -> Counter:
    c = Counter()
    for bjd10, bun, ji in keys:
        k = (bjd10, lot_str(bun, ji))
        a, b = old.get(k), new.get(k)
        if a is None and b is None:
            c["neither"] += 1
        elif b is None:
            c["al_d003_only"] += 1
        elif a is None:
            c["slim_only"] += 1
        else:
            c["both_equal" if abs(a - b) <= 0.01 else "both_differ"] += 1
    return c


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sidos", default="")
    args = ap.parse_args()
    sidos = [s for s in args.sidos.split(",") if s] or sorted(
        {p.name.split("_")[1] for p in CACHE.glob("title_*_2026-07.csv")}
    )
    eng = get_built_engine()
    slim = sqlite3.connect(SLIM.resolve().as_uri() + "?mode=ro", uri=True)
    slim.execute("PRAGMA query_only=ON")
    slim.execute("PRAGMA cache_size=-1000000")
    report: dict = {"results": {}}
    total = Counter()
    for sido in sidos:
        started = time.time()
        with eng.connect() as conn:
            tx = pd.read_sql(text(TX_SQL), conn, params={"sido_like": f"{sido}%", "min_year": 2019})
        al_d003 = load_land_ledger(sido, False)
        keys = title_keys(sido)
        from_slim = slim_land(slim, keys)
        res_old, _ = run_matching(tx, SCRATCH, sido, al_d003)
        res_new, _ = run_matching(tx, SCRATCH, sido, from_slim)
        a, b = records(res_old), records(res_new)
        tiers = Counter()
        for h in a.keys() | b.keys():
            tiers[f"{a.get(h, {}).get('match_tier', '-')}->{b.get(h, {}).get('match_tier', '-')}"] += 1
        row = {
            "transactions": len(tx),
            "register_parcels": len(keys),
            "land_dict": dict(compare_dicts(al_d003, from_slim, keys)),
            "confirmed_al_d003": len(a),
            "confirmed_slim": len(b),
            "al_d003_vs_slim": diff(a, b),
            "tier_transitions": {k: v for k, v in tiers.items() if k.split("->")[0] != k.split("->")[1]},
            "seconds": round(time.time() - started, 1),
        }
        report["results"][sido] = row
        for k in ("transactions", "confirmed_al_d003", "confirmed_slim"):
            total[k] += row[k]
        for k, v in row["al_d003_vs_slim"].items():
            if k != "field_diff":
                total[f"diff.{k}"] += v
        for k, v in row["land_dict"].items():
            total[f"dict.{k}"] += v
        print(f"{sido} old={len(a):,} new={len(b):,} {row['al_d003_vs_slim']} {row['seconds']}s", flush=True)
        args.out.write_text(json.dumps({**report, "total": dict(total)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dict(total), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
