"""Plan step 5: collective representative-parcel supply from the common ledgers, compared with the product mart.

Read only. Nothing is written to any DB.

  mart      collective_building_assessed_land_price (building_key × asset_type → representative_pnu, latest price)
  current   representative PNU the loader would choose now (latest collective_building_stats row)
  slim      land_trait_slim_v1: latest price of the representative PNU, and the price for the mart's year
  ledger    building_ledger_v1: titles / summaries on the representative PNU (2026-07 and any edition), register kind
  kapt      builder_master.pnu of the matched danji (latest attributes snapshot)
  mix       building_key spanning several 법정동 or lots in collective_transactions (name-key mixing signal; held)

Sido 12 (광주·전남 → 전남광주) PNUs are translated to the old codes for slim with the honam bridge; Incheon
reform PNUs fall back to the old 구 code. Per-key rows (with PNUs) go outside the repo; the report has counts only.
Non-residential collective has no representative-parcel mart (D-020); it is reported as not_applicable.
"""

from __future__ import annotations

import argparse
import csv
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
from collective.db_utils import get_collective_engine  # noqa: E402
from collective.import_assessed_land_price import _load_reform_bjd_maps  # noqa: E402
from parcel_master.pnu import pnu_from_tx, remap_pnu_bjd  # noqa: E402

SLIM = Path(r"C:\CH2\parcel_master\land_trait_slim_v1.sqlite")
LEDGER = Path(r"C:\CH2\parcel_master\building_ledger_v1.sqlite")
VERIFY = Path(r"C:\CH2\parcel_master\verification")
LATEST_EDITION = "2026-07"
ASSETS = ("apartment", "rowhouse", "officetel")


def ro(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    db.execute("PRAGMA query_only=ON")
    db.execute("PRAGMA cache_size=-500000")
    return db


def read_product() -> dict:
    eng = get_collective_engine()
    with eng.connect() as c:
        c.execute(text("SET TRANSACTION READ ONLY"))
        mart = c.execute(text(
            "SELECT building_key, asset_type, representative_pnu, assessed_land_price, assessed_land_price_year, source"
            " FROM collective_building_assessed_land_price")).fetchall()
        cur = c.execute(text("""
            WITH ranked AS (
                SELECT building_key, asset_type, beopjungri_code, lot_number,
                       ROW_NUMBER() OVER (PARTITION BY building_key, asset_type
                                          ORDER BY as_of_month DESC, window_years DESC) AS rn
                FROM collective_building_stats WHERE asset_type IN ('apartment','rowhouse','officetel'))
            SELECT building_key, asset_type, beopjungri_code, lot_number FROM ranked WHERE rn = 1""")).fetchall()
        mix = c.execute(text("""
            SELECT building_key, asset_type, count(DISTINCT beopjungri_code) AS n_bjd,
                   count(DISTINCT (beopjungri_code, lot_number)) AS n_lot
            FROM collective_transactions WHERE asset_type IN ('apartment','rowhouse','officetel')
            GROUP BY building_key, asset_type""")).fetchall()
        kapt = c.execute(text("""
            WITH a AS (
                SELECT DISTINCT ON (building_key, asset_type) building_key, asset_type, danji_code, match_tier
                FROM collective_building_attributes ORDER BY building_key, asset_type, snapshot_ym DESC),
            b AS (
                SELECT DISTINCT ON (danji_code) danji_code, pnu FROM builder_master
                ORDER BY danji_code, snapshot_ym DESC)
            SELECT a.building_key, a.asset_type, a.match_tier, b.pnu
            FROM a LEFT JOIN b ON b.danji_code = a.danji_code""")).fetchall()
        commercial = c.execute(text("SELECT asset_type, count(*) FROM commercial_clusters GROUP BY 1")).fetchall()
    old_to_current, current_to_old = _load_reform_bjd_maps(eng)
    return {"mart": mart, "current": cur, "mix": mix, "kapt": kapt, "commercial": commercial,
            "incheon_current_to_old": current_to_old,
            "incheon_old_to_current": {k: v for k, v in old_to_current.items() if k[:2] == "28"}}


def code_variants(pnu: str, bridge: dict, incheon: dict, incheon_new: dict) -> list[tuple[str, str]]:
    """The PNU under the codes the sources may use: as stored, sido-12 old code (bridge), Incheon old and new 구 code."""
    out = [("direct", pnu)]
    if pnu[:2] == "12" and bridge.get(pnu[:10]):
        out.append(("honam_bridge", bridge[pnu[:10]] + pnu[10:]))
    for how, m in (("incheon_old", incheon), ("incheon_new", incheon_new)):
        alt = remap_pnu_bjd(pnu, m) if m else None
        if alt and alt != pnu:
            out.append((how, alt))
    return out


def slim_lookup(slim: sqlite3.Connection, variants: list[tuple[str, str]]) -> tuple[str, list[tuple]]:
    """Rows from every code variant together; a reformed parcel can sit under old and new codes in different releases."""
    rows, hit = [], []
    for how, p in variants:
        got = slim.execute("SELECT price_year, price_month, asof_mask, price FROM observation WHERE pnu=?",
                           (int(p),)).fetchall()
        if got:
            hit.append(how)
            rows += got
    return ("+".join(hit) if hit else "absent"), rows


def num(v) -> float | None:
    try:
        x = float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return x if x > 0 else None


def slim_price(rows: list[tuple], year: int | None) -> dict:
    priced = [(int(y), int(m), num(p)) for y, m, _, p in rows if num(p) is not None]
    if not priced:
        return {"state": "no_price"}
    ly, lm = max((y, m) for y, m, _ in priced)
    latest = {p for y, m, p in priced if (y, m) == (ly, lm)}
    out = {"latest_year": ly, "latest_month": lm,
           "latest_price": next(iter(latest)) if len(latest) == 1 else None,
           "latest_state": "single" if len(latest) == 1 else "conflict"}
    if year is not None:
        same = {(m, p) for y, m, p in priced if y == year}
        if not same:
            out["year_state"] = "year_absent"
        else:
            m0 = min(m for m, _ in same)
            vals = {p for m, p in same if m == m0}
            out["year_state"] = "single" if len(vals) == 1 else "conflict"
            out["year_price"] = next(iter(vals)) if len(vals) == 1 else None
    return out


def ledger_on(led: sqlite3.Connection, variants: list[tuple[str, str]]) -> dict:
    """Titles and summaries on the PNU under every code variant (editions use the codes of their date)."""
    keys = {p for _, p in variants}
    t = []
    s = 0
    for p in keys:
        t += led.execute("SELECT o.snapshot, o.pk, v.raw FROM title_observation o JOIN title_version v"
                         " ON v.pk = o.pk AND v.raw_hash = o.raw_hash WHERE o.pnu = ?", (p,)).fetchall()
        s += led.execute("SELECT count(*) FROM summary_observation WHERE pnu = ?", (p,)).fetchone()[0]
    latest = {(pk, raw.split(b"|", 2)[1].strip()) for snap, pk, raw in t if snap == LATEST_EDITION}
    kinds = {k for _, k in latest}
    return {
        "title_latest": len(latest), "title_any": len({pk for _, pk, _ in t}), "summary_any": s,
        "kind_latest": ("집합포함" if b"2" in kinds else "일반만" if kinds else "없음"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--rows", type=Path, default=VERIFY / "collective_rep_parcel_supply_v1_rows.csv")
    args = ap.parse_args()
    t0 = time.time()
    prod = read_product()
    bridge = load_bridge()
    incheon = prod["incheon_current_to_old"]
    slim, led = ro(SLIM), ro(LEDGER)

    cur = {(r.building_key.strip(), r.asset_type.strip()): pnu_from_tx(r.beopjungri_code, r.lot_number)
           for r in prod["current"]}
    mix = {(r.building_key.strip(), r.asset_type.strip()): (r.n_bjd, r.n_lot) for r in prod["mix"]}
    kapt = {(r.building_key.strip(), r.asset_type.strip()): (r.match_tier, (r.pnu or "").strip() or None)
            for r in prod["kapt"]}

    rep: dict = defaultdict(Counter)
    by_sido: dict = defaultdict(Counter)
    VERIFY.mkdir(parents=True, exist_ok=True)
    with open(args.rows, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["building_key", "asset_type", "mart_pnu", "mart_price", "mart_year", "mart_source", "current_pnu",
                    "slim_via", "slim_latest_year", "slim_latest_price", "slim_year_state", "slim_year_price",
                    "price_compare", "title_latest", "title_any", "summary_any", "kind_latest", "kapt_tier", "kapt_pnu",
                    "kapt_compare", "n_bjd", "n_lot"])
        for r in prod["mart"]:
            key = (r.building_key.strip(), r.asset_type.strip())
            a = key[1]
            pnu = r.representative_pnu.strip()
            year = int(r.assessed_land_price_year)
            price = float(r.assessed_land_price)
            c = rep[a]
            c["mart_rows"] += 1
            cp = cur.get(key)
            c["current_pnu_" + ("same" if cp == pnu else "different" if cp else "no_current_stats_row")] += 1
            variants = code_variants(pnu, bridge, incheon, prod["incheon_old_to_current"])
            via, rows = slim_lookup(slim, variants)
            c["slim_via_" + via] += 1
            sp = slim_price(rows, year) if rows else {"state": "absent"}
            if via == "absent":
                cmpv = "pnu_not_in_slim"
            elif sp.get("state") == "no_price":
                cmpv = "slim_no_price"
            elif sp["year_state"] == "year_absent":
                cmpv = f"slim_year_absent_latest_{sp['latest_year']}"
            elif sp["year_state"] == "conflict":
                cmpv = "slim_year_conflict"
            elif abs(sp["year_price"] - price) < 0.5:
                cmpv = "same_price"
            else:
                cmpv = "different_price"
            c["price_" + cmpv] += 1
            if sp.get("latest_year") is not None:
                c[f"slim_latest_year_{sp['latest_year']}"] += 1
            lg = ledger_on(led, variants)
            c["ledger_title_latest_" + ("yes" if lg["title_latest"] else "no")] += 1
            c["ledger_title_any_" + ("yes" if lg["title_any"] else "no")] += 1
            c["ledger_summary_any_" + ("yes" if lg["summary_any"] else "no")] += 1
            c["ledger_kind_latest_" + lg["kind_latest"]] += 1
            tier, kp = kapt.get(key, (None, None))
            kc = ("no_attribute_row" if key not in kapt else "kapt_no_pnu" if not kp
                  else "same" if kp == pnu else "different")
            c["kapt_" + kc] += 1
            nb, nl = mix.get(key, (0, 0))
            c["mix_" + ("multi_bjd" if nb > 1 else "multi_lot_same_bjd" if nl > 1 else "single_lot"
                        if nl == 1 else "no_tx")] += 1
            s = by_sido[pnu[:2]]
            s["rows"] += 1
            s[cmpv if cmpv in ("same_price", "different_price", "pnu_not_in_slim") else "other"] += 1
            s["title_latest" if lg["title_latest"] else "no_title_latest"] += 1
            w.writerow([key[0], a, pnu, price, year, r.source, cp, via, sp.get("latest_year"), sp.get("latest_price"),
                        sp.get("year_state"), sp.get("year_price"), cmpv, lg["title_latest"], lg["title_any"],
                        lg["summary_any"], lg["kind_latest"], tier, kp, kc, nb, nl])

    mart_keys = {(r.building_key.strip(), r.asset_type.strip()) for r in prod["mart"]}
    no_mart = Counter(k[1] for k in cur if k not in mart_keys)
    no_mart_pnu = Counter(k[1] for k, p in cur.items() if k not in mart_keys and not p)
    # keys the mart lacks: could slim supply a latest price for their current representative PNU?
    gap: dict = defaultdict(Counter)
    for k, p in sorted((k, p) for k, p in cur.items() if k not in mart_keys and p):
        via, rows = slim_lookup(slim, code_variants(p, bridge, incheon, prod["incheon_old_to_current"]))
        sp = slim_price(rows, None) if rows else {"state": "absent"}
        if via == "absent":
            g = "pnu_not_in_slim"
        elif sp.get("state") == "no_price":
            g = "slim_no_price"
        elif sp["latest_state"] == "conflict":
            g = f"slim_latest_{sp['latest_year']}_conflict"
        else:
            g = f"slim_latest_{sp['latest_year']}"
        gap[k[1]][g] += 1
    total = Counter()
    for c in rep.values():
        total.update(c)
    report = {
        "plan_step": "5 (collective) — parallel comparison, read only",
        "edition_for_titles": LATEST_EDITION,
        "residential": {"all": dict(sorted(total.items())), "by_asset": {a: dict(sorted(c.items())) for a, c in rep.items()},
                        "by_sido": {s: dict(sorted(c.items())) for s, c in sorted(by_sido.items())},
                        "stats_keys_without_mart_row": dict(no_mart),
                        "stats_keys_without_mart_row_and_no_pnu": dict(no_mart_pnu),
                        "stats_keys_without_mart_row_slim_supply": {a: dict(sorted(c.items())) for a, c in gap.items()}},
        "non_residential": {"state": "not_applicable (D-020: masked lots, road clusters; no representative-parcel mart)",
                            "clusters": {r[0]: r[1] for r in prod["commercial"]}},
        "seconds": round(time.time() - t0, 1),
        "rows_file": "outside repo (verification folder)",
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report["residential"]["all"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
