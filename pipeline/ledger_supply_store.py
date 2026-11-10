"""Append-only publication of calculated ledger supply candidates."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from sqlalchemy import text


@dataclass(frozen=True)
class Supply:
    table: str
    keys: tuple[str, ...]
    columns: tuple[str, ...]
    source: str

    @property
    def predicate(self):
        return " AND ".join(f"s.{key}=r.{key}" for key in self.keys)


SUPPLY = {
    "land": Supply(
        "land_transaction_trait_link", ("transaction_hash",),
        ("transaction_hash", "link_status", "price_status", "official_price_won", "price_year",
         "trait_asof", "ledger_beopjungri_code", "code_resolution", "rule_version", "recovered_lot"),
        "land_transactions",
    ),
    "built": Supply(
        "built_transaction_enrichment", ("transaction_hash",),
        ("transaction_hash", "recovered_lot", "bldrgst_pk", "structure_raw", "structure_group",
         "max_floor", "approve_year", "match_tier", "match_rule", "n_exact", "snapshots_matched",
         "coverage_scope", "matched_cycle", "evidence", "zone_contract_year", "zone_latest",
         "assessed_land_price", "assessed_land_price_year", "assessed_land_price_basis"),
        "built_transactions",
    ),
    "collective": Supply(
        "collective_building_assessed_land_price", ("building_key", "asset_type"),
        ("building_key", "asset_type", "representative_pnu", "assessed_land_price",
         "assessed_land_price_year", "source"),
        "collective_building_stats",
    ),
}


def insert_sql(domain, payload, *, window=None):
    spec = SUPPLY[domain]
    columns = ", ".join(spec.columns)
    select = ", ".join(f"r.{name}" for name in spec.columns)
    order = ", ".join(f"r.{name}" for name in spec.keys)
    keys = ", ".join(spec.keys)
    source = f"SELECT {keys} FROM public.{spec.source}"
    condition = spec.predicate
    if domain == "built":
        from built.build_link_contract_shadow_v1 import DIGEST_SQL

        source = DIGEST_SQL.strip()
        condition += " AND s.digest = r.evidence->>'source_digest'"
    where = ""
    live = ""
    if window is not None and domain != "collective":
        start, stop = (date.fromisoformat(d).isoformat() for d in window)
        source += " AND " if domain == "built" else " WHERE "
        source += f"contract_date >= DATE '{start}' AND contract_date < DATE '{stop}'"
        live = f"WITH ch2_live AS MATERIALIZED ({source})"
        where = f"WHERE EXISTS (SELECT 1 FROM ch2_live s WHERE {condition})"
        guard = ""
    else:
        guard = f"CROSS JOIN LATERAL (SELECT 1 FROM ({source}) s WHERE {condition} LIMIT 1) present"
    return f"""
        {live}
        INSERT INTO public.{spec.table} ({columns})
        SELECT {select}
        FROM jsonb_populate_recordset(NULL::public.{spec.table}, {payload}) AS r
        {guard}
        {where}
        ORDER BY {order}
        ON CONFLICT ({keys}) DO NOTHING
    """


def append(conn, domain, records, *, window=None):
    """One caller-owned transaction. Existing rows retain their published values."""
    if not records:
        return 0
    statement = text(insert_sql(domain, "CAST(:payload AS jsonb)", window=window))
    inserted = conn.execute(statement, {"payload": json.dumps(records, default=str)}).rowcount
    if inserted != len(records):
        raise RuntimeError(f"Expected {len(records)} {domain} inserts, got {inserted}; no supply committed")
    return inserted
