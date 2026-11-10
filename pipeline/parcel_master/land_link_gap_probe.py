"""Probe: why are recent V1 transactions ``other_unmatched``?

Read only. Writes one JSON report of counts. No parcel, PNU or lot is written.

Each ``other_unmatched`` transaction (V1 rerun with every plate) falls in one bucket:

- ``a_no_parcel_with_mask``: no parcel in the legal dong carries the masked main lot.
- ``a_jimok_area_differs``: such parcels exist, but no plate has the same jimok and area.
- ``b_*``: a parcel matches jimok, area and mask in some plate, yet the latest
  pre-contract plate does not match and no later plate matches either.
- ``c_later_multiple``: two or more parcels match only after the contract.

It also counts parcels that exist only in ``observation_conflict`` (never in the
candidate index built from ``parcel_observation``) and the transactions whose
jimok, area and mask such a parcel would have matched.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from contextlib import closing
from itertools import groupby
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from sqlalchemy import text  # noqa: E402

from db_utils import get_engine  # noqa: E402
from parcel_master import land_trait_link_materialize as v1  # noqa: E402
from parcel_master.cheongju_land_gap_probe import _split_candidates  # noqa: E402
from parcel_master.cheongju_land_link_probe import compact_jimok, latest_consistent_plate  # noqa: E402
from parcel_master.land_link_rejudge_shadow import _conflict_loader, _load_rows, _plates  # noqa: E402
from parcel_master.land_trait_link_missing import _ranges  # noqa: E402
from parcel_master.national_land_link_shadow import LEDGER  # noqa: E402
from parcel_master.trait_link_helpers import area_key, lot_matches  # noqa: E402

FETCH = text(
    """
    SELECT t.transaction_hash, t.contract_date, t.beopjungri_code, t.sigungu_code,
           t.land_category, t.zone_type, t.area_sqm, t.is_partial_ownership,
           t.is_cancelled, t.is_valid, t.lot_display
    FROM land_transactions t
    WHERE t.contract_date >= :start AND t.contract_date < :stop
    ORDER BY t.sigungu_code
    """
)


def _conflict_only(db, code, batch, pairs, known):
    """PNU -> set of (jimok, area) for parcels seen only in observation_conflict."""
    found = defaultdict(set)
    for low, high in _ranges(code, batch, pairs):
        for pnu, jimok_label, area in db.execute(
            "SELECT pnu, jimok_label, area FROM observation_conflict WHERE pnu >= ? AND pnu < ?",
            (low, high),
        ):
            if pnu in known:
                continue
            area_text = area_key(area)
            if area_text is not None:
                found[pnu].add((compact_jimok(jimok_label), area_text))
    return found


def _bucket(row, prior, later, index, plates, by_bjd):
    bjd, jimok, area, mask, day = row
    candidates = [
        pnu for pnu in index.get((bjd, jimok, area), ()) if lot_matches(mask, pnu, str(int(pnu[11:15])))
    ]
    if not candidates:
        masked = [pnu for pnu in by_bjd.get(bjd, ()) if lot_matches(mask, pnu, str(int(pnu[11:15])))]
        if not masked:
            return "a_no_parcel_with_mask"
        same_jimok = [plate[4] for pnu in masked for plate in plates[pnu] if plate[3] == jimok]
        if not same_jimok:
            return "a_jimok_differs"
        target = float(area)
        if any(abs(float(value) - target) <= max(1.0, target * 0.01) for value in same_jimok):
            return "a_area_near_same_jimok"
        return "a_area_differs"
    if len(later) >= 2:
        return "c_later_multiple"
    reasons = set()
    for pnu in candidates:
        group = latest_consistent_plate(plates[pnu], day)
        if group is None:
            pre = [plate for plate in plates[pnu] if plate[0] <= day]
            reasons.add("b_inconsistent_latest_plate" if pre else "b_no_precontract_plate")
            continue
        plate = group[0]
        if plate[3] != jimok or plate[4] != area:
            reasons.add("b_latest_jimok_or_area_changed")
        elif not plate[5]:
            reasons.add("b_latest_zone_blank_or_unmapped")
        else:
            reasons.add("b_latest_zone_differs")
    order = (
        "b_latest_zone_blank_or_unmapped",
        "b_latest_zone_differs",
        "b_latest_jimok_or_area_changed",
        "b_inconsistent_latest_plate",
        "b_no_precontract_plate",
    )
    return next(reason for reason in order if reason in reasons)


def run(start, stop, out, sido):
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        pairs = v1.load_pairs(conn)
        fetched = [dict(row) for row in conn.execute(FETCH, {"start": start, "stop": stop}).mappings()]
    engine.dispose()
    if sido:
        fetched = [row for row in fetched if str(row["sigungu_code"] or "")[:2] in sido]

    buckets = defaultdict(Counter)
    by_month = defaultdict(Counter)
    statuses = Counter()
    conflict_only_parcels = 0
    conflict_only_hits = Counter()
    started = time.perf_counter()
    uri = LEDGER.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        for number, (code, group) in enumerate(
            groupby(fetched, lambda row: str(row["sigungu_code"] or "").strip()), start=1
        ):
            batch = list(group)
            if len(code) != 5 or not code.isdigit():
                continue
            rows = _load_rows(db, code, batch, pairs)
            plates, index = _plates(rows)
            records, _ = v1._classify(code, plates, index, pairs, batch, conflict_loader=_conflict_loader(db))
            status = {record["transaction_hash"]: record["link_status"] for record in records}
            by_bjd = defaultdict(list)
            for pnu in plates:
                by_bjd[pnu[:10]].append(pnu)
            only = _conflict_only(db, code, batch, pairs, plates)
            conflict_only_parcels += len(only)
            only_by_bjd = defaultdict(list)
            for pnu in only:
                only_by_bjd[pnu[:10]].append(pnu)
            for row in batch:
                digest = str(row["transaction_hash"] or "").strip()
                kind = status.get(digest)
                if kind is None:
                    continue
                statuses[kind] += 1
                if kind in ("exact", "label_normalized"):
                    continue
                day = str(row["contract_date"])[:10]
                bjd, _ = v1.resolve_beopjungri(str(row["beopjungri_code"]).strip(), day, pairs)
                jimok = str(row["land_category"] or "").strip()
                area = area_key(row["area_sqm"]) or ""
                mask = row["lot_display"]
                hit = any(
                    (jimok, area) in only[pnu] and lot_matches(mask, pnu, str(int(pnu[11:15])))
                    for pnu in only_by_bjd.get(bjd, ())
                )
                if hit:
                    conflict_only_hits[kind] += 1
                if kind != "other_unmatched":
                    continue
                prior, later = _split_candidates(bjd, jimok, area, str(row["zone_type"]), mask, day, index, plates)
                name = _bucket((bjd, jimok, area, mask, day), prior, later, index, plates, by_bjd)
                if name.startswith("a_") and hit:
                    name += "+conflict_only_match"
                buckets[code[:2]][name] += 1
                by_month[day[:7]][name] += 1
            if number % 25 == 0:
                print(f"{number} sigungu {time.perf_counter() - started:.0f}s", flush=True)

    total = Counter()
    for counts in buckets.values():
        total.update(counts)
    report = {
        "rule_version": v1.RULE_VERSION,
        "mode": "gap_probe_read_only",
        "window": [start, stop],
        "sido_filter": sorted(sido) if sido else None,
        "status": dict(statuses.most_common()),
        "other_unmatched_buckets": dict(total.most_common()),
        "other_unmatched_by_sido": {k: dict(v.most_common()) for k, v in sorted(buckets.items())},
        "other_unmatched_by_month": {k: dict(v.most_common()) for k, v in sorted(by_month.items())},
        "conflict_only_parcels_in_scanned_ranges": conflict_only_parcels,
        "unlinked_with_conflict_only_match": dict(conflict_only_hits.most_common()),
        "seconds": round(time.perf_counter() - started),
        "link_table_written": False,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2026-08-01")
    parser.add_argument("--stop", default="2026-11-01")
    parser.add_argument("--sido", nargs="*")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.start, args.stop, args.out, set(args.sido) if args.sido else None)
    print(json.dumps({k: report[k] for k in ("status", "other_unmatched_buckets", "conflict_only_parcels_in_scanned_ranges", "unlinked_with_conflict_only_match", "seconds")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
