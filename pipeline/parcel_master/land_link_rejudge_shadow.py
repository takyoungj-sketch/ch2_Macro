"""Shadow: does a newer ledger plate change V1 verdicts that are already stored?

Read only. Writes one JSON report, never the link table.

For each transaction in the window it runs LAND_LINK_RULE_V1 three ways:

- ``full``: every plate in the national ledger (what a re-run today would give).
- ``drop_last``: plates and conflict rows dated on or after ``--cutoff`` removed.
  This stands in for the verdict made before the newest plate arrived.
- ``code_gen``: full plates, but a reissued legal-dong code falls back to its
  previous code while the ledger holds no parcel under the new sido prefix.

The stored production status is read alongside so ``full`` can be checked
against it. Individual parcels and transactions are not written out.
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
from parcel_master.cheongju_land_link_probe import _add_plate  # noqa: E402
from parcel_master.land_trait_link_missing import _ranges  # noqa: E402
from parcel_master.national_land_link_shadow import LEDGER  # noqa: E402

LINKED = {"exact", "label_normalized"}
FAR_FUTURE = "9999-12-31"

FETCH = text(
    """
    SELECT t.transaction_hash, t.contract_date, t.beopjungri_code, t.sigungu_code,
           t.land_category, t.zone_type, t.area_sqm, t.is_partial_ownership,
           t.is_cancelled, t.is_valid, t.lot_display, l.link_status AS stored_status
    FROM land_transactions t
    LEFT JOIN land_transaction_trait_link l USING (transaction_hash)
    WHERE t.contract_date >= :start AND t.contract_date < :stop
    ORDER BY t.sigungu_code
    """
)

CONFLICT_SQL = """
    SELECT pnu, asof, price_year, price_month, source_file,
           jimok_code, jimok_label, area, zone1_code, zone1_label,
           zone2_code, zone2_label, use_code, use_label, height_code, height_label,
           shape_code, shape_label, road_code, road_label, price
    FROM observation_conflict WHERE pnu IN ({markers})
    ORDER BY pnu, asof, attr_hash
"""


def code_gen_pairs(pairs: dict, db) -> tuple[dict, list[str]]:
    """Hold the previous code while the ledger has no parcel under the new prefix."""
    missing = []
    for prefix in sorted({current[:2] for current in pairs}):
        upper = str(int(prefix) + 1).zfill(2)
        hit = db.execute(
            "SELECT 1 FROM parcel_observation WHERE pnu >= ? AND pnu < ? LIMIT 1", (prefix, upper)
        ).fetchone()
        if hit is None:
            missing.append(prefix)
    adjusted = {
        current: (previous, FAR_FUTURE if current[:2] in missing else effective)
        for current, (previous, effective) in pairs.items()
    }
    return adjusted, missing


def _load_rows(db, code, rows, pairs):
    found = []
    for low, high in _ranges(code, rows, pairs):
        found.extend(
            db.execute(
                """
                SELECT pnu, asof, price_year, price_month, jimok_label, area,
                       zone1_label, zone2_label, price
                FROM parcel_observation WHERE pnu >= ? AND pnu < ?
                """,
                (low, high),
            ).fetchall()
        )
    return found


def _plates(rows, cutoff=None):
    plates = defaultdict(list)
    index = defaultdict(set)
    for row in rows:
        if cutoff and str(row[1])[:10] >= cutoff:
            continue
        _add_plate(plates, index, row, prefixes=(row[0][:5],))
    for entries in plates.values():
        entries.sort()
    return plates, index


def _conflict_loader(db, cutoff=None):
    cache: dict[str, list] = {}

    def load(prefix, targets):
        grouped = defaultdict(list)
        keys = sorted(pnu for pnu in targets if pnu.startswith(prefix))
        for start in range(0, len(keys), 500):
            chunk = keys[start : start + 500]
            todo = [pnu for pnu in chunk if pnu not in cache]
            for pnu in todo:
                cache[pnu] = []
            if todo:
                markers = ",".join("?" for _ in todo)
                for item in db.execute(CONFLICT_SQL.format(markers=markers), todo):
                    cache[item[0]].append(item)
            for pnu in chunk:
                for item in cache[pnu]:
                    asof = str(item[1])[:10]
                    if cutoff and asof >= cutoff:
                        continue
                    grouped[(item[0], asof, str(item[2]), str(item[3]))].append(item)
        return grouped

    return load


def _verdicts(code, batch, pairs, db, cutoff=None):
    rows = _load_rows(db, code, batch, pairs)
    plates, index = _plates(rows, cutoff)
    records, _ = v1._classify(code, plates, index, pairs, batch, conflict_loader=_conflict_loader(db, cutoff))
    return {
        record["transaction_hash"]: (
            record["link_status"],
            (record["ledger_beopjungri_code"], record["recovered_lot"]),
        )
        for record in records
    }


def run(start: str, stop: str, cutoff: str, out: Path, sido: set[str] | None) -> dict:
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        pairs = v1.load_pairs(conn)
        fetched = [dict(row) for row in conn.execute(FETCH, {"start": start, "stop": stop}).mappings()]
    engine.dispose()
    if sido:
        fetched = [row for row in fetched if str(row["sigungu_code"] or "")[:2] in sido]
    stored = {str(row["transaction_hash"]).strip(): row["stored_status"] for row in fetched}
    month_of = {str(row["transaction_hash"]).strip(): str(row["contract_date"])[:7] for row in fetched}
    sido_of = {str(row["transaction_hash"]).strip(): str(row["sigungu_code"])[:2] for row in fetched}

    full: dict[str, tuple] = {}
    dropped: dict[str, tuple] = {}
    gen: dict[str, tuple] = {}
    started = time.perf_counter()
    uri = LEDGER.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        gen_pairs, missing_prefixes = code_gen_pairs(pairs, db)
        groups = groupby(fetched, lambda row: str(row["sigungu_code"] or "").strip())
        for number, (code, group) in enumerate(groups, start=1):
            batch = list(group)
            if len(code) != 5 or not code.isdigit():
                continue
            full.update(_verdicts(code, batch, pairs, db))
            dropped.update(_verdicts(code, batch, pairs, db, cutoff))
            if code[:2] in missing_prefixes:
                gen.update(_verdicts(code, batch, gen_pairs, db))
            if number % 25 == 0:
                print(f"{number} sigungu {time.perf_counter() - started:.0f}s", flush=True)

    for key, verdict in full.items():
        gen.setdefault(key, verdict)

    moves = Counter()
    moves_by_sido = defaultdict(Counter)
    for key, (before, parcel_before) in dropped.items():
        after, parcel_after = full[key]
        was, now = before in LINKED, after in LINKED
        if was and now:
            move = "linked_parcel_changed" if parcel_before != parcel_after else "linked_same_parcel"
        elif was:
            move = "linked_to_unlinked"
        elif now:
            move = "unlinked_to_linked"
        else:
            move = "unlinked_reason_changed" if before != after else "unlinked_same"
        moves[move] += 1
        moves_by_sido[sido_of[key]][move] += 1

    full = {key: verdict[0] for key, verdict in full.items()}
    dropped = {key: verdict[0] for key, verdict in dropped.items()}
    gen = {key: verdict[0] for key, verdict in gen.items()}

    def tally(verdicts, group_of):
        result = defaultdict(Counter)
        for key, status in verdicts.items():
            result[group_of[key]][status] += 1
        return {name: dict(counts) for name, counts in sorted(result.items())}

    transitions = Counter()
    transitions_by_month = defaultdict(Counter)
    for key, before in dropped.items():
        after = full.get(key)
        if before != after:
            transitions[f"{before} -> {after}"] += 1
            transitions_by_month[month_of[key]][f"{before} -> {after}"] += 1

    agree = Counter()
    for key, status in full.items():
        stored_status = stored.get(key)
        if stored_status is None:
            agree["stored_missing"] += 1
        elif stored_status == status:
            agree["same"] += 1
        else:
            agree[f"stored {stored_status} / shadow {status}"] += 1

    gen_changes = Counter()
    for key, status in gen.items():
        if full[key] != status:
            gen_changes[f"{full[key]} -> {status}"] += 1

    def linked_rate(verdicts):
        by_month = defaultdict(lambda: [0, 0])
        for key, status in verdicts.items():
            bucket = by_month[month_of[key]]
            bucket[0] += 1
            bucket[1] += int(status in LINKED)
        return {
            month: {"judged": n, "linked": k, "rate": round(100 * k / n, 2) if n else None}
            for month, (n, k) in sorted(by_month.items())
        }

    report = {
        "rule_version": v1.RULE_VERSION,
        "mode": "shadow_rejudge_read_only",
        "window": [start, stop],
        "cutoff_dropped_from": cutoff,
        "sido_filter": sorted(sido) if sido else None,
        "transactions_fetched": len(fetched),
        "judged": len(full),
        "ledger_prefixes_without_parcels": missing_prefixes,
        "linked_rate": {
            "drop_last": linked_rate(dropped),
            "full": linked_rate(full),
            "code_gen": linked_rate(gen),
        },
        "status_by_month": {
            "drop_last": tally(dropped, month_of),
            "full": tally(full, month_of),
        },
        "status_by_sido_full": tally(full, sido_of),
        "status_by_sido_code_gen": tally(gen, sido_of),
        "drop_last_to_full_moves": dict(moves.most_common()),
        "drop_last_to_full_moves_by_sido": {k: dict(v) for k, v in sorted(moves_by_sido.items())},
        "drop_last_to_full_transitions": dict(transitions.most_common()),
        "drop_last_to_full_by_month": {m: dict(c.most_common()) for m, c in sorted(transitions_by_month.items())},
        "full_vs_stored": dict(agree.most_common()),
        "code_gen_changes": dict(gen_changes.most_common()),
        "seconds": round(time.perf_counter() - started),
        "link_table_written": False,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2026-04-01")
    parser.add_argument("--stop", default="2026-11-01")
    parser.add_argument("--cutoff", default="2026-07-20")
    parser.add_argument("--sido", nargs="*")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.start, args.stop, args.cutoff, args.out, set(args.sido) if args.sido else None)
    print(json.dumps({k: report[k] for k in ("judged", "full_vs_stored", "drop_last_to_full_moves", "drop_last_to_full_transitions", "code_gen_changes", "seconds")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
