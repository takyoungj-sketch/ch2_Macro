"""Plan step 6 (adopted design): rent link shadow supply. Read only; writes one SQLite outside the repo.

  apartment / rowhouse / officetel  transaction → building_key (same key as collective) → key layer
      key on the collective sale side: collective attribute tier (contract mapping A·B·C confirmed, D·F aggregated,
                                       E·P·T weak_match, Z unlinked) and the collective slim price shadow
      rent-only key:                   representative lot = lot of the latest rent contract of the key, same price
                                       rule as the collective shadow (slim latest year, earliest month); building
                                       identity unverified
  detached (단독다가구)               not_applicable — masked lot and no gross area; analysed by 법정동·road

No rent / collective DB writes. Per-key rows stay outside the repo; the report has counts only.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from built.replay_honam_bridge import load_bridge  # noqa: E402
from collective.build_assessed_land_price_shadow_v1 import OUT as COLL_SHADOW, year_price  # noqa: E402
from collective.compare_rep_parcel_supply_v1 import SLIM, code_variants, ro, slim_lookup  # noqa: E402
from collective.db_utils import get_collective_engine  # noqa: E402
from collective.import_assessed_land_price import _load_reform_bjd_maps  # noqa: E402
from parcel_master.pnu import pnu_from_tx  # noqa: E402
from rent.db_utils import get_rent_engine  # noqa: E402

OUT = Path(r"C:\CH2\parcel_master\shadow\rent_link_shadow_v1.sqlite")
RULE = "rent_link_v1"
COLLECTIVE_TYPES = ("apartment", "rowhouse", "officetel")
TIER_STATE = {"A": "confirmed", "B": "confirmed", "C": "confirmed", "D": "aggregated", "F": "aggregated",
              "E": "weak_match", "P": "weak_match", "T": "weak_match", "Z": "unlinked"}

DDL = """
CREATE TABLE rent_link_key_v1 (
    asset_type TEXT NOT NULL, building_key TEXT NOT NULL, key_source TEXT NOT NULL,
    collective_tier TEXT, building_id_state TEXT NOT NULL, multi_bjd INTEGER NOT NULL, rent_rows INTEGER NOT NULL,
    representative_pnu TEXT, price_state TEXT NOT NULL, price_use_approved INTEGER NOT NULL,
    assessed_land_price REAL, assessed_land_price_year INTEGER, slim_via TEXT,
    rule_version TEXT NOT NULL, PRIMARY KEY (asset_type, building_key)
);
CREATE TABLE rent_link_header_v1 (
    transaction_hash TEXT NOT NULL, asset_type TEXT NOT NULL, link_state TEXT NOT NULL, reason TEXT,
    building_key TEXT, contract_year INTEGER, sido TEXT
);
CREATE TABLE info (key TEXT PRIMARY KEY, value TEXT);
"""

KEY_SQL = """
SELECT DISTINCT ON (asset_type, building_key) asset_type, building_key, beopjungri_code, lot_number
FROM rent_transactions
WHERE is_valid AND contract_year >= 2019 AND asset_type IN ('apartment','rowhouse','officetel')
  AND coalesce(building_key, '') <> ''
ORDER BY asset_type, building_key, contract_date DESC NULLS LAST, id DESC
"""
KEY_STATS_SQL = """
SELECT asset_type, building_key, count(*) n, count(DISTINCT beopjungri_code) n_bjd
FROM rent_transactions
WHERE is_valid AND contract_year >= 2019 AND asset_type IN ('apartment','rowhouse','officetel')
  AND coalesce(building_key, '') <> ''
GROUP BY 1, 2
"""
TX_SQL = """
SELECT transaction_hash, asset_type, coalesce(building_key, '') AS building_key, contract_year,
       left(coalesce(beopjungri_code, ''), 2) AS sido
FROM rent_transactions WHERE is_valid AND contract_year >= 2019
"""


def collective_layer() -> tuple[set, dict, dict]:
    eng = get_collective_engine()
    with eng.connect() as c:
        c.execute(text("SET TRANSACTION READ ONLY"))
        sale = {(r[0].strip(), r[1].strip()) for r in c.execute(text(
            "SELECT DISTINCT asset_type, building_key FROM collective_transactions"
            " WHERE asset_type IN ('apartment','rowhouse','officetel')"))}
        tier = {(r[0].strip(), r[1].strip()): (r[2] or "").strip() for r in c.execute(text(
            "SELECT DISTINCT ON (asset_type, building_key) asset_type, building_key, match_tier"
            " FROM collective_building_attributes ORDER BY asset_type, building_key, snapshot_ym DESC"))}
    db = sqlite3.connect(COLL_SHADOW.resolve().as_uri() + "?mode=ro", uri=True)
    price = {(a, k): (p, st, ua, v, y, via) for k, a, p, st, ua, v, y, via in db.execute(
        "SELECT building_key, asset_type, representative_pnu, state, use_approved, assessed_land_price,"
        " assessed_land_price_year, slim_via FROM collective_building_assessed_land_price_shadow")}
    db.close()
    return sale, tier, price


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    t0 = time.time()
    sale, tier, cprice = collective_layer()
    old_to_current, current_to_old = _load_reform_bjd_maps(get_collective_engine())
    incheon_new = {k: v for k, v in old_to_current.items() if k[:2] == "28"}
    bridge = load_bridge()
    slim = ro(SLIM)
    rent = get_rent_engine()

    with rent.connect() as c:
        c.execute(text("SET TRANSACTION READ ONLY"))
        lots = {(r.asset_type.strip(), r.building_key.strip()): (r.beopjungri_code, r.lot_number)
                for r in c.execute(text(KEY_SQL))}
        kstats = {(r.asset_type.strip(), r.building_key.strip()): (int(r.n), int(r.n_bjd))
                  for r in c.execute(text(KEY_STATS_SQL))}
    print("keys", len(kstats), round(time.time() - t0, 1), flush=True)

    keys_out = []
    kc: dict = defaultdict(Counter)
    latest_year = max(v[4] for v in cprice.values() if v[4])
    for key in sorted(kstats):
        a = key[0]
        n, nb = kstats[key]
        c = kc[a]
        if key in sale:
            src = "collective_sale"
            t = tier.get(key)
            state = TIER_STATE.get(t, "no_attribute_row") if t else "no_attribute_row"
            cp = cprice.get(key)
            if cp:
                pnu, pst, pua, pv, py, via = cp
            else:
                pnu, pst, pua, pv, py, via = None, "no_collective_price_row", 0, None, None, None
        else:
            src, t, state = "rent_only", None, "rent_only_unverified"
            bjd, lot = lots.get(key, (None, None))
            pnu = pnu_from_tx(bjd, lot) if lot and "*" not in str(lot) else None
            if not pnu:
                pst, pua, pv, py, via = "no_pnu", 0, None, None, None
            else:
                via, rows = slim_lookup(slim, code_variants(pnu, bridge, current_to_old, incheon_new))
                yp = year_price(rows) if rows else {"state": "pnu_not_in_slim"}
                pst = yp["state"]
                if pst == "single":
                    pst = "supplied" if yp["year"] == latest_year else "held_stale"
                pua, pv, py = int(pst == "supplied"), yp.get("price"), yp.get("year")
        keys_out.append((a, key[1], src, t, state, int(nb > 1), n, pnu, pst, pua, pv, py, via, RULE))
        c[f"keys_{src}"] += 1
        c[f"rows_{src}"] += n
        c[f"rows_{src}_state_{state}"] += n
        c[f"rows_{src}_price_{pst}"] += n
        c[f"rows_price_use_approved"] += n * pua
        c["rows_multi_bjd"] += n * (nb > 1)
    print("key layer", round(time.time() - t0, 1), flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".partial")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(DDL)
    db.executemany(f"INSERT INTO rent_link_key_v1 VALUES ({','.join('?' * 14)})", keys_out)
    hc: dict = defaultdict(Counter)
    with rent.connect() as c:
        c.execute(text("SET TRANSACTION READ ONLY"))
        batch = []
        for h, a, k, cy, sido in c.execute(text(TX_SQL).execution_options(stream_results=True, yield_per=200_000)):
            a = a.strip()
            k = k.strip()
            if a == "detached":
                st, why, k = "not_applicable", "detached_masked_lot_no_gross_area", None
            elif a in COLLECTIVE_TYPES and k:
                st, why = "linked", ("collective_sale" if (a, k) in sale else "rent_only")
            elif a in COLLECTIVE_TYPES:
                st, why, k = "unlinked", "no_building_key", None
            else:
                st, why, k = "not_applicable", f"asset_{a}", None
            batch.append((h, a, st, why, k, cy, sido or None))
            hc[a][f"{st}:{why}"] += 1
            if len(batch) >= 200_000:
                db.executemany("INSERT INTO rent_link_header_v1 VALUES (?,?,?,?,?,?,?)", batch)
                batch.clear()
        if batch:
            db.executemany("INSERT INTO rent_link_header_v1 VALUES (?,?,?,?,?,?,?)", batch)
    print("headers", round(time.time() - t0, 1), flush=True)
    db.execute("CREATE INDEX ix_rent_header_hash ON rent_link_header_v1(transaction_hash)")
    dup = db.execute("SELECT count(*) FROM (SELECT transaction_hash FROM rent_link_header_v1"
                     " GROUP BY transaction_hash HAVING count(*) > 1)").fetchone()[0]
    db.executemany("INSERT INTO info VALUES (?,?)", [("rule_version", RULE), ("price_latest_year", str(latest_year)),
                                                     ("built_on", time.strftime("%Y-%m-%d"))])
    db.commit()
    db.close()
    OUT.unlink(missing_ok=True)
    tmp.rename(OUT)

    rep = {
        "plan_step": "6 (rent) — adopted design, shadow supply, product untouched",
        "rule": RULE, "window": "contract_year >= 2019, is_valid", "shadow_file": "outside repo (C:\\CH2\\parcel_master\\shadow)",
        "headers": sum(sum(c.values()) for c in hc.values()), "duplicate_transaction_hashes": dup,
        "header_by_asset": {a: dict(sorted(c.items())) for a, c in sorted(hc.items())},
        "key_layer_by_asset": {a: dict(sorted(c.items())) for a, c in sorted(kc.items())},
        "seconds": round(time.time() - t0, 1),
    }
    args.out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
