"""Building representative parcel vs land trait slim v1: match rates (plan step 3).

Both databases are opened read-only. Counts only; no management key or parcel number is written.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

BUILDING = Path(r"C:\CH2\parcel_master\building_ledger_v1.sqlite")
SLIM = Path(r"C:\CH2\parcel_master\land_trait_slim_v1.sqlite")
SNAPSHOT_DATE = {"2024-09": date(2024, 9, 30), "2025-07": date(2025, 7, 31), "2026-07": date(2026, 7, 31)}


def ro(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    db.execute("PRAGMA query_only=ON")
    db.execute("PRAGMA cache_size=-1000000")
    return db


def nearest_bit(calendar: dict[int, str], day: date) -> tuple[int, str]:
    return min(calendar.items(), key=lambda kv: abs((date.fromisoformat(kv[1]) - day).days))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    started = time.time()
    building = ro(BUILDING)
    slim = ro(SLIM)
    calendar = {b: a for b, a in slim.execute("SELECT bit, asof FROM asof_calendar")}
    near = {s: nearest_bit(calendar, d) for s, d in SNAPSHOT_DATE.items()}

    per_snapshot: dict[tuple[str, str], Counter] = {}
    all_pnus: set[int] = set()
    for kind in ("title", "summary"):
        for snapshot in SNAPSHOT_DATE:
            counts = Counter()
            for pnu, n in building.execute(
                f"SELECT pnu, COUNT(*) FROM {kind}_observation WHERE snapshot=? AND pnu IS NOT NULL GROUP BY pnu",
                (snapshot,),
            ):
                counts[int(pnu)] = n
            per_snapshot[(kind, snapshot)] = counts
            all_pnus.update(counts)
            print(f"{kind} {snapshot} distinct pnu={len(counts):,}", flush=True)

    mask_of: dict[int, int] = {}
    lookup = "SELECT asof_mask FROM observation WHERE pnu=?"
    for i, pnu in enumerate(sorted(all_pnus), 1):
        if pnu > 2**63 - 1:
            continue
        m = 0
        for (mask,) in slim.execute(lookup, (pnu,)):
            m |= mask
        if m:
            mask_of[pnu] = m
        if i % 1_000_000 == 0:
            print(f"lookup {i:,}/{len(all_pnus):,} {time.time() - started:.0f}s", flush=True)

    report: dict = {
        "run_date": "2026-10-17",
        "land_asof_nearest_overall": {s: a for s, (_, a) in near.items()},
        "land_slim_has_sido_12": slim.execute(
            "SELECT EXISTS(SELECT 1 FROM observation WHERE pnu >= 1200000000000000000 AND pnu < 1300000000000000000)"
        ).fetchone()[0] == 1,
        "results": {},
    }
    # Land deliveries can be partial (one province per asof), so the nearest asof is
    # chosen per province among asofs holding at least half of that province's peak count.
    bit_count: dict[str, Counter] = defaultdict(Counter)
    for pnu, m in mask_of.items():
        sido = str(pnu)[:2]
        for b in calendar:
            if m >> b & 1:
                bit_count[sido][b] += 1
    near_by_sido: dict[tuple[str, str], int] = {}
    for sido, bc in bit_count.items():
        peak = max(bc.values())
        eligible = {b: calendar[b] for b, c in bc.items() if c >= peak / 2}
        for snapshot, day in SNAPSHOT_DATE.items():
            near_by_sido[(sido, snapshot)] = nearest_bit(eligible, day)[0]
    report["land_asof_by_sido"] = {
        f"{s}|{snap}": calendar[b] for (s, snap), b in sorted(near_by_sido.items())
    }
    for (kind, snapshot), counts in per_snapshot.items():
        total = Counter()
        by_sido: dict[str, Counter] = defaultdict(Counter)
        for pnu, n in counts.items():
            m = mask_of.get(pnu, 0)
            sido = str(pnu)[:2]
            bit = near_by_sido.get((sido, snapshot), -1)
            cls = "near_asof" if bit >= 0 and m >> bit & 1 else "other_asof_only" if m else "absent"
            total[f"buildings_{cls}"] += n
            total[f"pnu_{cls}"] += 1
            by_sido[sido][f"buildings_{cls}"] += n
            if str(pnu)[11:15] == "0000":
                total[f"zero_main_lot_{cls}"] += n
        held = building.execute(
            f"SELECT identity_status, COUNT(*) FROM {kind}_observation WHERE snapshot=? AND pnu IS NULL GROUP BY 1",
            (snapshot,),
        ).fetchall()
        buildings = sum(counts.values()) + sum(n for _, n in held)
        report["results"][f"{kind}|{snapshot}"] = {
            "observations": buildings,
            "not_converted": dict(held),
            "totals": dict(total),
            "near_rate_of_all": round(total["buildings_near_asof"] / buildings, 5),
            "any_rate_of_all": round(
                (total["buildings_near_asof"] + total["buildings_other_asof_only"]) / buildings, 5
            ),
            "by_sido": {
                s: {**dict(c), "near_rate": round(c["buildings_near_asof"] / max(1, sum(c.values())), 4)}
                for s, c in sorted(by_sido.items())
            },
        }
    report["distinct_pnu_looked_up"] = len(all_pnus)
    report["elapsed_seconds"] = round(time.time() - started, 1)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
