"""Capture a monthly ledger key baseline, then publish only new supply candidates."""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
from collections import defaultdict
from datetime import date
from pathlib import Path

from sqlalchemy import text

from ledger_supply_store import SUPPLY, append

LOG = logging.getLogger(__name__)
COLLECTIVE_TYPES = "('apartment', 'rowhouse', 'officetel')"
DROP_WARNING_PP = 10.0


def engine_for(domain):
    if domain == "land":
        from db_utils import get_engine

        engine = get_engine()
    elif domain == "built":
        from built.db_utils import get_built_engine

        engine = get_built_engine()
    else:
        from collective.db_utils import get_collective_engine

        engine = get_collective_engine()
    if engine.url.host not in ("localhost", "127.0.0.1", "::1") or engine.url.database != f"{domain}_stats":
        raise ValueError("Monthly ledger supply requires the expected local domain database")
    return engine


def window_keys(conn, domain, start, stop):
    params = {"start": start, "stop": stop}
    if domain == "collective":
        rows = conn.execute(text(f"""
            SELECT DISTINCT building_key, asset_type
            FROM collective_transactions
            WHERE contract_date >= :start AND contract_date < :stop
              AND building_key IS NOT NULL AND btrim(building_key) <> ''
              AND asset_type IN {COLLECTIVE_TYPES}
        """), params)
        return {tuple(row) for row in rows}
    # Domain is validated against SUPPLY at the CLI boundary.
    rows = conn.execute(text(f"""
        SELECT transaction_hash FROM {domain}_transactions
        WHERE contract_date >= :start AND contract_date < :stop AND transaction_hash IS NOT NULL
    """), params)
    return {str(row[0]).strip() for row in rows}


def read_baseline(path, domain, start, stop):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    if data["window"] != [domain, start, stop]:
        raise ValueError("Monthly supply key baseline belongs to a different window")
    if domain == "collective":
        return {tuple(key) for key in data["keys"]}
    return set(data["keys"])


def capture(db, domain, start, stop, path):
    if path.exists():
        read_baseline(path, domain, start, stop)
        return
    with db.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        keys = window_keys(conn, domain, start, stop)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as handle:
        json.dump({"window": [domain, start, stop], "keys": sorted(keys)}, handle)
    tmp.replace(path)
    LOG.info("대장 신규 키 기준 저장 %s %d건", domain, len(keys))


def prepare(db, domain, start, stop, cycle, new_keys):
    if not new_keys:
        return [], {}
    if domain == "land":
        from parcel_master.land_trait_link_missing import missing_records

        _, records = missing_records(db, start, stop, keys=new_keys)
        return records, _counts(records, "link_status")
    if domain == "built":
        from built.ledger_supply_missing import missing_records

        cache = os.getenv("CH2_BUILT_REGISTER_CACHE")
        _, records, states = missing_records(
            db, start, stop, cycle, keys=new_keys, cache=Path(cache) if cache else None,
        )
        return records, states
    from collective.ledger_supply_missing import missing_records

    _, records, states = missing_records(db, start, stop, keys=new_keys)
    return records, states


def _counts(records, field):
    result = defaultdict(int)
    for row in records:
        result[row[field]] += 1
    return dict(result)


def reconcile_orphans(conn, domain, removed, returned):
    if domain == "collective":
        return 0, 0
    spec = SUPPLY[domain]
    if domain == "land":
        conn.execute(text("""
            ALTER TABLE public.land_transaction_trait_link
            ADD COLUMN IF NOT EXISTS orphaned boolean NOT NULL DEFAULT false
        """))
        mark = "orphaned = true"
        restore = "orphaned = false"
        can_mark = "NOT e.orphaned"
        can_restore = "e.orphaned"
    else:
        mark = """supply_hold = 'orphaned',
          evidence = jsonb_set(coalesce(e.evidence, '{}'::jsonb), '{prior_supply_hold}',
                               coalesce(to_jsonb(e.supply_hold), 'null'::jsonb))"""
        restore = "supply_hold = e.evidence->>'prior_supply_hold', evidence = e.evidence - 'prior_supply_hold'"
        can_mark = "e.supply_hold IS DISTINCT FROM 'orphaned'"
        can_restore = "e.supply_hold = 'orphaned' AND e.evidence ? 'prior_supply_hold'"
    exists = f"EXISTS (SELECT 1 FROM public.{spec.source} s WHERE s.transaction_hash = e.transaction_hash)"

    def update(keys, values, predicate, present):
        if not keys:
            return 0
        return conn.execute(text(f"""
            UPDATE public.{spec.table} e SET {values}
            FROM jsonb_array_elements_text(CAST(:keys AS jsonb)) k(transaction_hash)
            WHERE e.transaction_hash = k.transaction_hash::char(64)
              AND {predicate} AND {present}
        """), {"keys": json.dumps(sorted(keys))}).rowcount

    return (
        update(removed, mark, can_mark, f"NOT {exists}"),
        update(returned, restore, can_restore, exists),
    )


def _shift_month(month, delta):
    year, index = divmod(month.year * 12 + month.month - 1 + delta, 12)
    return date(year, index + 1, 1)


def coverage(conn, domain, stop):
    stop = date.fromisoformat(stop)
    start = _shift_month(stop, -4)
    params = {"start": start, "stop": stop}
    counts = {str(_shift_month(start, i))[:7]: [0, 0, 0] for i in range(4)}
    if domain == "land":
        from parcel_master.land_trait_link_materialize import exclusion_reason

        rows = conn.execute(text("""
            SELECT t.contract_date,t.transaction_hash,t.beopjungri_code,t.sigungu_code,t.land_category,t.zone_type,
                   t.area_sqm,t.is_partial_ownership,t.is_cancelled,t.is_valid,t.lot_display,l.link_status,l.orphaned
            FROM land_transactions t LEFT JOIN land_transaction_trait_link l USING(transaction_hash)
            WHERE t.contract_date >= :start AND t.contract_date < :stop
        """), params).mappings()
        for row in rows:
            key = str(row["contract_date"])[:7]
            month = counts[key]
            month[0] += 1
            if (not exclusion_reason(row) and len(str(row["beopjungri_code"] or "").strip()) == 10
                    and len(str(row["sigungu_code"] or "").strip()) == 5
                    and len(str(row["transaction_hash"] or "").strip()) == 64):
                month[1] += 1
                month[2] += int(row["link_status"] in ("exact", "label_normalized") and not row["orphaned"])
    elif domain == "built":
        from built.measure_link_quality_v1 import SIDOS

        rows = conn.execute(text("""
            SELECT to_char(t.contract_date, 'YYYY-MM'), count(*), count(*) FILTER (WHERE eligible),
                   count(e.transaction_hash) FILTER (WHERE eligible AND e.supply_hold IS NULL)
            FROM (
                SELECT t.*, (t.is_valid AND t.gross_area > 0 AND t.is_partial_ownership IS NOT TRUE
                       AND left(t.sigungu_code, 2) = ANY(:sidos)) AS eligible
                FROM built_transactions t WHERE t.contract_date >= :start AND t.contract_date < :stop
            ) t LEFT JOIN built_transaction_enrichment e USING(transaction_hash)
            GROUP BY 1
        """), {**params, "sidos": list(SIDOS)})
        for month, total, eligible, linked in rows:
            counts[month] = [total, eligible, linked]
    else:
        rows = conn.execute(text(f"""
            SELECT month, count(*), count(p.building_key)
            FROM (
                SELECT DISTINCT to_char(contract_date, 'YYYY-MM') AS month, building_key, asset_type
                FROM collective_transactions
                WHERE contract_date >= :start AND contract_date < :stop
                  AND building_key IS NOT NULL AND btrim(building_key) <> ''
                  AND asset_type IN {COLLECTIVE_TYPES}
            ) t LEFT JOIN collective_building_assessed_land_price p USING(building_key,asset_type)
            GROUP BY 1
        """), params)
        for month, eligible, linked in rows:
            counts[month] = [eligible, eligible, linked]
    return [
        {"month": month, "total": total, "eligible": eligible, "linked": linked,
         "rate": round(linked * 100 / eligible, 2) if eligible else None}
        for month, (total, eligible, linked) in counts.items()
    ]


def rate_warning(months):
    prior = [row["rate"] for row in months[:-1] if row["rate"] is not None]
    latest = months[-1]["rate"]
    if latest is None or len(prior) != 3:
        return None
    mean = sum(prior) / 3
    return round(mean - latest, 2) if mean - latest >= DROP_WARNING_PP else None


def publish(db, domain, start, stop, cycle, baseline, report_path):
    before = read_baseline(baseline, domain, start, stop)
    with db.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        after = window_keys(conn, domain, start, stop)
    new_keys, removed = after - before, before - after
    records, states = prepare(db, domain, start, stop, cycle, new_keys)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = report_path.with_suffix(".tmp")
    with db.begin() as conn:
        conn.execute(text("SET LOCAL lock_timeout='5s'"))
        conn.execute(text("SET LOCAL statement_timeout='480s'"))
        inserted = append(conn, domain, records, window=(start, stop))
        orphaned, returned = reconcile_orphans(conn, domain, removed, new_keys)
        months = coverage(conn, domain, stop)
        drop = rate_warning(months)
        result = {"domain": domain, "cycle": cycle, "new_keys": len(new_keys), "inserted": inserted,
                  "orphaned": orphaned, "returned": returned, "states": states, "months": months,
                  "warn_drop_pp": drop}
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(report_path)
    for row in months:
        LOG.info("%s %s 연결 %d/%d 전체 %d 비율 %s", domain, row["month"], row["linked"],
                 row["eligible"], row["total"], row["rate"])
    if drop is not None:
        LOG.warning("%s 연결률이 직전 3개월 평균보다 %.2f%%p 낮음", domain, drop)
    LOG.info("%s 신규 공급 %d건, 고아 표시 %d건", domain, inserted, orphaned)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("capture", "apply"))
    parser.add_argument("domain", choices=SUPPLY)
    parser.add_argument("--cycle-id", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--stop", required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    start, stop = (date.fromisoformat(value) for value in (args.start, args.stop))
    if start.day != 1 or stop.day != 1 or start >= stop:
        parser.error("start and stop must bound whole months")
    try:
        db = engine_for(args.domain)
        if args.phase == "capture":
            capture(db, args.domain, args.start, args.stop, args.baseline)
        else:
            publish(db, args.domain, args.start, args.stop, args.cycle_id, args.baseline, args.report)
    except Exception as exc:
        LOG.warning("대장 공급 %s 실패 (%s)", args.phase, type(exc).__name__)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
