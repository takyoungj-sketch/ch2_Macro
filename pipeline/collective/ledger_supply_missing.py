"""New residential collective keys and their existing slim supply rule."""

from __future__ import annotations

from collections import Counter

from sqlalchemy import text

from collective.import_assessed_land_price import (
    _load_reform_bjd_maps,
    _representative_pnus,
    read_source_from_slim,
)

ASSET_TYPES = ("apartment", "rowhouse", "officetel")
NEW_KEYS = text("""
    WITH recent AS (
        SELECT building_key, asset_type, min(contract_date) AS first_date
        FROM collective_transactions
        WHERE contract_date >= :start AND contract_date < :stop
          AND asset_type IN ('apartment', 'rowhouse', 'officetel')
          AND building_key IS NOT NULL AND btrim(building_key) <> ''
        GROUP BY building_key, asset_type
    )
    SELECT r.building_key, r.asset_type, r.first_date, p.building_key IS NOT NULL AS supplied
    FROM recent r
    LEFT JOIN collective_building_assessed_land_price p USING (building_key, asset_type)
    WHERE NOT EXISTS (
        SELECT 1 FROM collective_transactions older
        WHERE older.building_key = r.building_key AND older.asset_type = r.asset_type
          AND older.contract_date < :start
    )
""")


def missing_records(db, start, stop):
    with db.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        keys = [dict(row) for row in conn.execute(NEW_KEYS, {"start": start, "stop": stop}).mappings()]
        missing = {(row["building_key"], row["asset_type"]) for row in keys if not row["supplied"]}
        if not missing:
            return keys, [], {}
        latest_year = conn.execute(text("""
            SELECT max(assessed_land_price_year)
            FROM collective_building_assessed_land_price WHERE source = 'land_trait_slim'
        """)).scalar_one()
        if latest_year is None:
            raise ValueError("Existing slim reference year is unavailable")
        candidates = _representative_pnus(conn, ASSET_TYPES, keys=missing)
    old_to_current, current_to_old = _load_reform_bjd_maps(db)
    source = read_source_from_slim(
        {row["pnu"] for row in candidates}, latest_year=latest_year,
        old_to_current_bjd=old_to_current, current_to_old_bjd=current_to_old,
    ).set_index("pnu").to_dict("index")
    records = [
        {"building_key": row["building_key"], "asset_type": row["asset_type"],
         "representative_pnu": row["pnu"],
         "assessed_land_price": source[row["pnu"]]["assessed_land_price"],
         "assessed_land_price_year": source[row["pnu"]]["assessed_land_price_year"],
         "source": "land_trait_slim"}
        for row in candidates if row["pnu"] in source
    ]
    return keys, records, Counter(
        missing=len(missing), candidate=len(candidates), supplied=len(records),
        no_representative=len(missing) - len(candidates),
        no_slim_price=len(candidates) - len(records),
    )
