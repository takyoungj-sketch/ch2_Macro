"""Project new ENGINE_V2 contract results into the existing composite supply shape."""

from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import closing
from decimal import Decimal, InvalidOperation
import sqlite3

import pandas as pd
from sqlalchemy import text

from built import link_engine_v1 as engine
from built.build_link_contract_shadow_v1 import DIGEST_SQL
from built.enrichment_rows import MATCH_RULE, structure_group


def missing_inputs(db, start, stop, since=None):
    statement = text(DIGEST_SQL + """
        AND contract_date >= :start AND contract_date < :stop
        AND (:since IS NULL OR created_at >= CAST(:since AS timestamptz))
        AND NOT EXISTS (SELECT 1 FROM built_transaction_enrichment e
                        WHERE e.transaction_hash = built_transactions.transaction_hash)
    """)
    with db.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        rows = pd.read_sql(statement, conn, params={"start": start, "stop": stop, "since": since})
    rows["sido"] = rows["sigungu_code"].fillna("").str[:2].replace("", engine.NO_SIDO)
    return rows


def assessed_price(db, pnu_keys, contract_year):
    """Contract year first. When amounts disagree, leave the price empty."""
    amounts = defaultdict(set)
    for pnu in pnu_keys:
        for year, raw in db.execute(
            "SELECT price_year, price FROM observation WHERE pnu=? AND price_year IN (?,?)",
            (int(pnu), str(contract_year), str(contract_year - 1)),
        ):
            try:
                value = Decimal(raw)
            except (InvalidOperation, TypeError):
                continue
            if value.is_finite() and value > 0:
                amounts[int(year)].add(value)
    for year, basis in ((contract_year, "same_year"), (contract_year - 1, "prior_year")):
        found = amounts[year]
        if len(found) > 1:
            return None, None, None, "price_conflict"
        if found:
            value = next(iter(found))
            if value != value.to_integral_value():
                return None, None, None, "non_integer_price"
            return int(value), year, basis, basis
    return None, None, None, "price_missing" if pnu_keys else "no_parcel"


def project(headers, values, dependencies, cycle):
    dep = {row[0]: dict(zip(engine.DEPS_COLS, row)) for row in dependencies}
    val = defaultdict(dict)
    for row in values:
        val[row[0]][row[1]] = dict(zip(engine.VALUE_COLS, row))
    records = []
    statuses = defaultdict(Counter)
    with closing(sqlite3.connect(engine.SLIM.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        for header in headers:
            h = dict(zip(engine.HEADER_COLS, header))
            key = h["target_key"]
            d = dep[key]
            month = f"{d['contract_year']}-{int(d['contract_month'] or 0):02}"
            counts = statuses[month]
            if h["link_state"] != "linked":
                counts[h["link_state"]] += 1
                counts[f"reason/{h['link_reason']}"] += 1
                continue
            if "collective_apartment_d079" in h["hold_flags"].split(","):
                counts["collective_apartment_d079"] += 1
                continue
            if h["rule_version"] != engine.ENGINE_RULE or d["tier"] not in MATCH_RULE or not d["parcel"]:
                raise ValueError("Unexpected ENGINE_V2 linked result")
            a = val[key]
            structure = a["structure"]["value_text"] if a["structure"]["use_approved"] else None
            floors = a["floors_above"]["value_num"] if a["floors_above"]["use_approved"] else None
            approve = a["approve_year"]["value_num"] if a["approve_year"]["use_approved"] else None
            contract_zone = a["zone_contract_year"]
            zone = contract_zone["value_text"] if contract_zone["timing"] != "adjacent_after" else None
            price, year, basis, price_state = assessed_price(
                db, [p for p in (d["pnus"] or "").split(",") if p], int(d["contract_year"])
            )
            counts["supplied"] += 1
            counts[f"price/{price_state}"] += 1
            records.append({
                "transaction_hash": key,
                "recovered_lot": d["parcel"],
                "bldrgst_pk": h["bldrgst_pk"],
                "structure_raw": structure,
                "structure_group": structure_group(structure),
                "max_floor": int(floors) if floors is not None else None,
                "approve_year": int(approve) if approve is not None else None,
                "match_tier": d["tier"],
                "match_rule": MATCH_RULE[d["tier"]],
                "n_exact": d["n_exact"],
                "snapshots_matched": [h["register_snapshot"]] if h["register_snapshot"] else [],
                "coverage_scope": "national",
                "matched_cycle": cycle,
                "evidence": {"rule_version": engine.ENGINE_RULE, "source_digest": h["source_digest"],
                             "register_snapshot": h["register_snapshot"], "building_id_state": h["building_id_state"],
                             "hold_flags": h["hold_flags"]},
                "zone_contract_year": zone,
                "zone_latest": a["zone_latest"]["value_text"],
                "assessed_land_price": price,
                "assessed_land_price_year": year,
                "assessed_land_price_basis": basis,
            })
    return records, statuses


def missing_records(db, start, stop, cycle, *, since=None, cache=None, workers=3):
    rows = missing_inputs(db, start, stop, since)
    if rows.empty:
        return rows, [], {}
    heads, vals, deps, _ = engine.compute(rows, engine.Defn(cycle=cycle), workers=workers, cache=cache)
    records, statuses = project(heads, vals, deps, cycle)
    return rows, records, statuses
