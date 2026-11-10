"""Rejudge stored land trait links. DRY-RUN ONLY.

Implements the rejudge design in docs/lab/LAND_LINK_GAP_REVIEW_20261110.md.
There is no apply mode. The link table is read under ``SET TRANSACTION READ ONLY``
and the ledger is opened ``mode=ro``. The event table DDL is a draft
(``docs/lab/land_trait_link_event_ddl_draft.sql``) and is not applied.

Targets (``--target``):

- ``honam_v2``: unlinked rows whose stored ledger legal-dong code starts with 12.
  These are judged with LAND_CODE_HISTORY_LAYER_V2. The selection does not use a
  plate-date filter: those rows failed on the code, not on the plate.
- ``new_plate``: unlinked rows whose contract date is on or after ``--plate-asof``
  (the earliest new plate). These are judged with V1. A contract earlier than
  the new plate cannot gain a pre-contract plate.

Linked rows (exact, label_normalized) are never targets. With ``--report-linked``
they are judged again and only counted (linked→unlinked, parcel changed).

Outputs:
- ``--out``: counts only (repo-safe).
- ``--plan``: optional local file listing hash, previous status and new status
  for each row that would change. It belongs under C:\\CH2\\parcel_master, not in git.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from sqlalchemy import text  # noqa: E402

from db_utils import get_engine  # noqa: E402
from parcel_master import land_trait_link_materialize as v1  # noqa: E402
from parcel_master.land_code_history_layer_v2 import RULE_VERSION_V2, ledger_generation_pairs  # noqa: E402
from parcel_master.land_trait_link_missing import classify  # noqa: E402
from parcel_master.national_land_link_shadow import LEDGER  # noqa: E402

LINKED = ("exact", "label_normalized")
COLUMNS = """
    t.transaction_hash, t.contract_date, t.beopjungri_code, t.sigungu_code,
    t.land_category, t.zone_type, t.area_sqm, t.is_partial_ownership,
    t.is_cancelled, t.is_valid, t.lot_display,
    l.link_status AS previous_status, l.recovered_lot AS previous_lot,
    l.ledger_beopjungri_code AS previous_bjd, l.rule_version AS previous_rule_version
"""


def _orphan_filter(conn) -> str:
    has = conn.execute(text(
        "SELECT 1 FROM information_schema.columns WHERE table_name = 'land_transaction_trait_link' AND column_name = 'orphaned'"
    )).first()
    return " AND NOT l.orphaned" if has else ""


def select_targets(conn, target: str, plate_asof: str | None, linked: bool) -> list[dict]:
    orphan = _orphan_filter(conn)
    status = "l.link_status IN ('exact','label_normalized')" if linked else "l.link_status NOT IN ('exact','label_normalized')"
    if target == "honam_v2":
        where = f"{status} AND left(l.ledger_beopjungri_code, 2) = '12'"
        params = {}
    else:
        where = f"{status} AND t.contract_date >= :asof"
        params = {"asof": plate_asof}
    sql = text(f"""
        SELECT {COLUMNS}
        FROM land_transaction_trait_link l
        JOIN land_transactions t USING (transaction_hash)
        WHERE {where}{orphan}
        ORDER BY t.sigungu_code
    """)
    return [dict(row) for row in conn.execute(sql, params).mappings()]


def rejudge(rows, pairs, db):
    found = {}
    for code, group in groupby(rows, lambda row: str(row["sigungu_code"] or "").strip()):
        batch = list(group)
        if len(code) == 5 and code.isdigit():
            for record in classify(code, batch, pairs, db):
                found[record["transaction_hash"]] = record
    return found


def run(args) -> dict:
    started = time.perf_counter()
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        pairs = v1.load_pairs(conn)
        targets = select_targets(conn, args.target, args.plate_asof, linked=False)
        linked_rows = select_targets(conn, args.target, args.plate_asof, linked=True) if args.report_linked else []
    engine.dispose()

    uri = LEDGER.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        if args.target == "honam_v2":
            use_pairs, pair_summary = ledger_generation_pairs(pairs, db)
            rule_version = RULE_VERSION_V2
        else:
            use_pairs, pair_summary = pairs, {}
            rule_version = v1.RULE_VERSION
        judged = rejudge(targets, use_pairs, db)
        judged_linked = rejudge(linked_rows, use_pairs, db) if linked_rows else {}

    moves = Counter()
    by_month = defaultdict(Counter)
    by_sido = defaultdict(Counter)
    plan = []
    for row in targets:
        digest = str(row["transaction_hash"]).strip()
        record = judged.get(digest)
        new = record["link_status"] if record else "not_judged"
        old = row["previous_status"]
        move = "unlinked_to_linked" if new in LINKED else ("unchanged" if new == old else "reason_changed")
        moves[f"{old} -> {new}"] += 1
        by_month[str(row["contract_date"])[:7]][move] += 1
        by_sido[str(row["sigungu_code"])[:2]][move] += 1
        if record and new != old:
            plan.append({
                "transaction_hash": digest, "previous_status": old, "previous_rule_version": row["previous_rule_version"],
                "new_status": new, "new_rule_version": rule_version, "price_status": record["price_status"],
                "official_price_won": record["official_price_won"], "price_year": record["price_year"],
                "trait_asof": record["trait_asof"], "ledger_beopjungri_code": record["ledger_beopjungri_code"],
                "code_resolution": record["code_resolution"], "recovered_lot": record["recovered_lot"],
            })

    linked_moves = Counter()
    for row in linked_rows:
        record = judged_linked.get(str(row["transaction_hash"]).strip())
        if record is None:
            linked_moves["not_judged"] += 1
        elif record["link_status"] not in LINKED:
            linked_moves["linked_to_unlinked"] += 1
        elif (record["ledger_beopjungri_code"], record["recovered_lot"]) != (row["previous_bjd"], row["previous_lot"]):
            linked_moves["parcel_changed"] += 1
        else:
            linked_moves["same"] += 1

    if args.plan:
        args.plan.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(args.plan, "wt", encoding="utf-8") as handle:
            json.dump({"target": args.target, "rule_version": rule_version, "rows": plan}, handle, default=str)

    report = {
        "mode": "dry_run",
        "apply_supported": False,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": args.target,
        "plate_asof": args.plate_asof,
        "rule_version": rule_version,
        "pairs": pair_summary,
        "unlinked_targets": len(targets),
        "would_update": len(plan),
        "would_link": sum(1 for item in plan if item["new_status"] in LINKED),
        "moves": dict(moves.most_common()),
        "by_month": {k: dict(v) for k, v in sorted(by_month.items())},
        "by_sido": {k: dict(v) for k, v in sorted(by_sido.items())},
        "linked_rows_checked": len(linked_rows),
        "linked_rows_report_only": dict(linked_moves),
        "seconds": round(time.perf_counter() - started),
        "link_table_written": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("honam_v2", "new_plate"), required=True)
    parser.add_argument("--plate-asof", help="earliest new plate date, required for new_plate")
    parser.add_argument("--report-linked", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--plan", type=Path)
    args = parser.parse_args()
    if args.target == "new_plate" and not args.plate_asof:
        parser.error("--plate-asof is required for new_plate")
    report = run(args)
    print(json.dumps({k: report[k] for k in ("target", "unlinked_targets", "would_update", "would_link", "moves", "linked_rows_report_only", "seconds")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
