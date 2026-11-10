"""Rejudge stored land trait links. Dry-run by default.

Rejudge design and rollout: docs/lab/LAND_LINK_V2_ROLLOUT_PLAN_20261110.md.
Dry-run reads the link table under ``SET TRANSACTION READ ONLY`` and opens the
ledger ``mode=ro``. Judging uses LAND_CODE_HISTORY_LAYER_V2 + LAND_LINK_RULE_V1,
the same as monthly supply.

Targets (``--target``):

- ``honam_v2``: unlinked rows whose stored ledger legal-dong code starts with 12.
  The selection does not use a plate-date filter: those rows failed on the code,
  not on the plate.
- ``new_plate``: unlinked rows whose contract date is on or after ``--plate-asof``
  (the earliest new plate). A contract earlier than the new plate cannot gain a
  pre-contract plate. Dry-run only for now.

Linked rows (exact, label_normalized) are never targets. With ``--report-linked``
they are judged again and only counted (linked→unlinked, parcel changed).

``--apply`` (``--target honam_v2`` only) needs migration
``db/084_land_trait_link_event.sql``. It also needs ``--expect-host`` and
``--expect-db`` naming the connected database, and a ``--cycle-id``. In one
transaction it inserts one event row per planned change, then updates the link
row while the row still has its previous unlinked status. If either count
differs from the plan, the whole transaction rolls back.

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
APPLY_TARGETS = frozenset({"honam_v2"})
MANIFEST = ROOT / "docs" / "lab" / "land_trait_ledger_v1_freeze_20261017.json"
COLUMNS = """
    t.transaction_hash, t.contract_date, t.beopjungri_code, t.sigungu_code,
    t.land_category, t.zone_type, t.area_sqm, t.is_partial_ownership,
    t.is_cancelled, t.is_valid, t.lot_display,
    l.link_status AS previous_status, l.recovered_lot AS previous_lot,
    l.ledger_beopjungri_code AS previous_bjd, l.rule_version AS previous_rule_version,
    l.price_status AS previous_price_status, l.trait_asof AS previous_trait_asof,
    l.code_resolution AS previous_code_resolution
"""

PLAN_COLUMNS = """
    transaction_hash char(64), previous_status text, previous_rule_version text,
    previous_price_status text, previous_trait_asof date, previous_bjd char(10),
    previous_code_resolution text, new_status text, new_rule_version text,
    price_status text, official_price_won numeric, price_year smallint, trait_asof date,
    ledger_beopjungri_code char(10), code_resolution text, recovered_lot text
"""

EVENT_SQL = f"""
    WITH plan AS (SELECT * FROM jsonb_to_recordset(CAST(:payload AS jsonb)) AS p({PLAN_COLUMNS}))
    INSERT INTO land_transaction_trait_link_event (
        transaction_hash, cycle_id, target, previous_status, previous_rule_version,
        previous_price_status, previous_trait_asof, previous_ledger_beopjungri_code,
        previous_code_resolution, new_status, new_rule_version, new_price_status,
        new_trait_asof, ledger_latest_asof, applied_by
    )
    SELECT p.transaction_hash, :cycle_id, :target, p.previous_status, p.previous_rule_version,
           p.previous_price_status, p.previous_trait_asof, p.previous_bjd,
           p.previous_code_resolution, p.new_status, p.new_rule_version, p.price_status,
           p.trait_asof, CAST(:ledger_latest_asof AS date), :applied_by
    FROM plan p
    JOIN land_transaction_trait_link l ON l.transaction_hash = p.transaction_hash
    WHERE l.link_status = p.previous_status
      AND l.link_status NOT IN ('exact', 'label_normalized')
"""

UPDATE_SQL = f"""
    WITH plan AS (SELECT * FROM jsonb_to_recordset(CAST(:payload AS jsonb)) AS p({PLAN_COLUMNS}))
    UPDATE land_transaction_trait_link l
       SET link_status = p.new_status,
           rule_version = p.new_rule_version,
           price_status = p.price_status,
           official_price_won = p.official_price_won,
           price_year = p.price_year,
           trait_asof = p.trait_asof,
           ledger_beopjungri_code = p.ledger_beopjungri_code,
           code_resolution = p.code_resolution,
           recovered_lot = p.recovered_lot,
           judged_at = now(),
           ledger_latest_asof = CAST(:ledger_latest_asof AS date)
      FROM plan p
     WHERE l.transaction_hash = p.transaction_hash
       AND l.link_status = p.previous_status
       AND l.link_status NOT IN ('exact', 'label_normalized')
"""


class ApplyRefused(RuntimeError):
    """Nothing was written."""


def ledger_latest_asof(path: Path = MANIFEST) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    return max(data["load_report"]["asofs"])


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
            for record in classify(code, batch, pairs, db, rule_version=RULE_VERSION_V2):
                found[record["transaction_hash"]] = record
    return found


def build_plan(targets, judged, rule_version):
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
                "transaction_hash": digest,
                "previous_status": old,
                "previous_rule_version": row["previous_rule_version"],
                "previous_price_status": row["previous_price_status"],
                "previous_trait_asof": row["previous_trait_asof"],
                "previous_bjd": row["previous_bjd"],
                "previous_code_resolution": row["previous_code_resolution"],
                "new_status": new,
                "new_rule_version": rule_version,
                "price_status": record["price_status"],
                "official_price_won": record["official_price_won"],
                "price_year": record["price_year"],
                "trait_asof": record["trait_asof"],
                "ledger_beopjungri_code": record["ledger_beopjungri_code"],
                "code_resolution": record["code_resolution"],
                "recovered_lot": record["recovered_lot"],
            })
    return plan, moves, by_month, by_sido


def apply_plan(engine, plan, *, target, cycle_id, applied_by, latest_asof, expect_host, expect_db):
    """One transaction: event rows, then the guarded update. Any count mismatch rolls back."""
    if target not in APPLY_TARGETS:
        raise ApplyRefused(f"apply is not allowed for target {target}")
    if (engine.url.host, engine.url.database) != (expect_host, expect_db):
        raise ApplyRefused("connected database does not match --expect-host/--expect-db")
    if not plan:
        return {"events": 0, "updated": 0}
    params = {
        "payload": json.dumps(plan, default=str), "cycle_id": cycle_id, "target": target,
        "ledger_latest_asof": latest_asof, "applied_by": applied_by,
    }
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL lock_timeout = '5s'"))
        conn.execute(text("SET LOCAL statement_timeout = '600s'"))
        ready = conn.execute(text(
            "SELECT to_regclass('public.land_transaction_trait_link_event') IS NOT NULL"
        )).scalar()
        if not ready:
            raise ApplyRefused("migration 084_land_trait_link_event.sql is not applied")
        events = conn.execute(text(EVENT_SQL), params).rowcount
        if events != len(plan):
            raise ApplyRefused(f"expected {len(plan)} event rows, got {events}; rolled back")
        updated = conn.execute(text(UPDATE_SQL), params).rowcount
        if updated != len(plan):
            raise ApplyRefused(f"expected {len(plan)} updates, got {updated}; rolled back")
    return {"events": events, "updated": updated}


def run(args) -> dict:
    started = time.perf_counter()
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        pairs = v1.load_pairs(conn)
        targets = select_targets(conn, args.target, args.plate_asof, linked=False)
        linked_rows = select_targets(conn, args.target, args.plate_asof, linked=True) if args.report_linked else []

    uri = LEDGER.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        use_pairs, pair_summary = ledger_generation_pairs(pairs, db)
        judged = rejudge(targets, use_pairs, db)
        judged_linked = rejudge(linked_rows, use_pairs, db) if linked_rows else {}
    rule_version = RULE_VERSION_V2
    plan, moves, by_month, by_sido = build_plan(targets, judged, rule_version)

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

    applied = None
    if args.apply:
        applied = apply_plan(
            engine, plan, target=args.target, cycle_id=args.cycle_id, applied_by=args.applied_by,
            latest_asof=args.ledger_latest_asof or ledger_latest_asof(),
            expect_host=args.expect_host, expect_db=args.expect_db,
        )
    engine.dispose()

    report = {
        "mode": "apply" if args.apply else "dry_run",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": args.target,
        "plate_asof": args.plate_asof,
        "cycle_id": args.cycle_id,
        "rule_version": rule_version,
        "pairs": pair_summary,
        "unlinked_targets": len(targets),
        "would_update": len(plan),
        "would_link": sum(1 for item in plan if item["new_status"] in LINKED),
        "applied": applied,
        "moves": dict(moves.most_common()),
        "by_month": {k: dict(v) for k, v in sorted(by_month.items())},
        "by_sido": {k: dict(v) for k, v in sorted(by_sido.items())},
        "linked_rows_checked": len(linked_rows),
        "linked_rows_report_only": dict(linked_moves),
        "seconds": round(time.perf_counter() - started),
        "link_table_written": bool(applied and applied["updated"]),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("honam_v2", "new_plate"), required=True)
    parser.add_argument("--plate-asof", help="earliest new plate date, required for new_plate")
    parser.add_argument("--report-linked", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--apply", action="store_true", help="write; honam_v2 only")
    parser.add_argument("--cycle-id")
    parser.add_argument("--applied-by", default="land_trait_link_rejudge")
    parser.add_argument("--expect-host")
    parser.add_argument("--expect-db")
    parser.add_argument("--ledger-latest-asof")
    return parser


def check_args(parser, args) -> None:
    if args.target == "new_plate" and not args.plate_asof:
        parser.error("--plate-asof is required for new_plate")
    if args.apply:
        if args.target not in APPLY_TARGETS:
            parser.error(f"--apply is only allowed for {sorted(APPLY_TARGETS)}")
        if not (args.cycle_id and args.expect_host and args.expect_db):
            parser.error("--apply needs --cycle-id, --expect-host and --expect-db")
        if args.report_linked:
            parser.error("--apply does not take --report-linked")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    check_args(parser, args)
    report = run(args)
    print(json.dumps({k: report[k] for k in (
        "mode", "target", "unlinked_targets", "would_update", "would_link", "applied", "moves",
        "linked_rows_report_only", "seconds",
    )}, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
