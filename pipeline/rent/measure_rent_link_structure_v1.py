"""Plan step 6: what is masked in rent transactions and what could link them. Read only; counts only.

  A  apartment / rowhouse / officetel: building_key reuse with the collective sale side, the representative-parcel
     mart, lot masking, PNU convertibility and attribute columns.
  B  detached (단독다가구): the lot is masked (e.g. '1**') and only the leased area (계약면적) is published, so the
     composite rule (gross-area exact match) does not apply as is. For each distinct rent signature
     (법정동, masked lot, road, building year) count 2026-07 title candidates step by step:
       lot range → 단독·다가구·다중 use → approval year = building year → road token = rent road
     and whether the leased area equals a candidate's gross area (whole-building lease).
     A unique candidate is unverified, not a link.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from built.recover_address import CACHE, GROSS_TOL, mask_range, road_token, to_f, to_i  # noqa: E402
from built.replay_honam_bridge import BRIDGED  # noqa: E402
from collective.db_utils import get_collective_engine  # noqa: E402
from parcel_master.pnu import pnu_from_tx  # noqa: E402
from rent.db_utils import get_rent_engine  # noqa: E402

EDITION = "2026-07"
DETACHED_USES = ("단독", "다가구", "다중")


def ro(eng):
    c = eng.connect()
    c.execute(text("SET TRANSACTION READ ONLY"))
    return c


def part_a(rent, coll) -> dict:
    prof = rent.execute(text("""
        SELECT asset_type, count(*) n,
               count(*) FILTER (WHERE building_key IS NOT NULL AND building_key <> '') with_key,
               count(*) FILTER (WHERE lot_number LIKE '%*%') lot_masked,
               count(*) FILTER (WHERE coalesce(lot_number, '') = '') lot_empty,
               count(*) FILTER (WHERE coalesce(road_name, '') <> '') with_road,
               count(*) FILTER (WHERE exclusive_area > 0) with_exclusive_area,
               count(*) FILTER (WHERE contract_area > 0) with_contract_area,
               count(*) FILTER (WHERE building_year > 0) with_building_year,
               count(*) FILTER (WHERE floor IS NOT NULL) with_floor,
               count(*) FILTER (WHERE coalesce(building_name, '') <> '') with_building_name
        FROM rent_transactions WHERE is_valid AND contract_year >= 2019 GROUP BY asset_type""")).mappings().all()
    keys = rent.execute(text("""
        SELECT asset_type, building_key, count(*) n FROM rent_transactions
        WHERE is_valid AND contract_year >= 2019 AND asset_type IN ('apartment','rowhouse','officetel')
          AND building_key IS NOT NULL AND building_key <> '' GROUP BY 1, 2""")).fetchall()
    lots = rent.execute(text("""
        SELECT asset_type, beopjungri_code, lot_number, count(*) n FROM rent_transactions
        WHERE is_valid AND contract_year >= 2019 GROUP BY 1, 2, 3""")).fetchall()
    sale = {(r[0].strip(), r[1].strip()) for r in coll.execute(text(
        "SELECT DISTINCT asset_type, building_key FROM collective_transactions"
        " WHERE asset_type IN ('apartment','rowhouse','officetel')")).fetchall()}
    mart = {(r[0].strip(), r[1].strip()) for r in coll.execute(text(
        "SELECT asset_type, building_key FROM collective_building_assessed_land_price")).fetchall()}
    attrs = {(r[0].strip(), r[1].strip()): r[2] for r in coll.execute(text(
        "SELECT DISTINCT ON (asset_type, building_key) asset_type, building_key, match_tier"
        " FROM collective_building_attributes ORDER BY asset_type, building_key, snapshot_ym DESC")).fetchall()}
    out: dict = {a["asset_type"]: {k: int(v) for k, v in a.items() if k != "asset_type"} for a in prof}
    kc: dict = defaultdict(Counter)
    for a, k, n in keys:
        key = (a.strip(), k.strip())
        c = kc[key[0]]
        c["keys"] += 1
        c["rows"] += n
        for name, hit in (("sale_key", key in sale), ("mart_price", key in mart), ("attribute_row", key in attrs)):
            c[f"keys_with_{name}"] += hit
            c[f"rows_with_{name}"] += n * hit
        tier = attrs.get(key)
        if tier:
            c[f"rows_tier_{tier}"] += n
    pc: dict = defaultdict(Counter)
    for a, bjd, lot, n in lots:
        c = pc[a.strip()]
        if lot and "*" in lot:
            c["rows_masked"] += n
        elif pnu_from_tx(bjd, lot):
            c["rows_pnu_ok"] += n
        else:
            c["rows_pnu_fail"] += n
    for a in out:
        out[a]["building_key_reuse"] = dict(kc.get(a, {}))
        out[a]["pnu_from_lot"] = dict(pc.get(a, {}))
    return out


def load_titles(sido: str) -> dict:
    folder = BRIDGED if sido == "12" else CACHE
    p = folder / f"title_{sido}_{EDITION}.csv"
    if not p.exists():
        p = CACHE / f"title_{sido}_{EDITION}.csv"
    t = pd.read_csv(p, dtype=str, keep_default_na=False,
                    usecols=["sigungu_code", "bjd_code", "bun", "ji", "addr_road", "gross_area", "use_name", "approve_date"])
    idx: dict = defaultdict(list)
    for r in t.itertuples(index=False):
        bun = to_i(r.bun)
        if bun is None:
            continue
        idx[r.sigungu_code.strip() + r.bjd_code.strip()].append((
            bun, any(u in r.use_name for u in DETACHED_USES), to_i(r.approve_date[:4]) if r.approve_date else None,
            re.sub(r"\s+", "", road_token(r.addr_road)), to_f(r.gross_area)))
    return idx


def bucket(n: int) -> str:
    return "0" if n == 0 else "1" if n == 1 else "2-5" if n <= 5 else "6+"


def part_b(rent) -> dict:
    sig = pd.read_sql(text("""
        SELECT left(beopjungri_code, 2) sido, beopjungri_code bjd, lot_number lot, coalesce(road_name, '') road,
               building_year, contract_area, count(*) n
        FROM rent_transactions WHERE is_valid AND contract_year >= 2019 AND asset_type = 'detached'
        GROUP BY 1, 2, 3, 4, 5, 6"""), rent)
    rows_total = int(sig["n"].sum())
    steps = {s: Counter() for s in ("range", "use", "year", "road")}
    steps_rows = {s: Counter() for s in steps}
    area = Counter()
    fails = Counter()
    lot_shape = Counter()
    for sido, g in sig.groupby("sido"):
        idx = load_titles(sido)
        # one candidate count per building signature; the leased area only adds the whole-building check
        for (bjd, lot, road, by), gg in g.groupby(["bjd", "lot", "road", "building_year"], dropna=False):
            n = int(gg["n"].sum())
            s = str(lot or "")
            lot_shape["masked_" + str(s.count("*")) + "stars" if "*" in s else "unmasked" if s else "empty"] += n
            rng = mask_range(lot)
            if rng is None:
                fails["lot_not_parsable"] += n
                continue
            lo, hi = rng
            cand = [c for c in idx.get(str(bjd).strip(), ()) if lo <= c[0] <= hi]
            road_k = re.sub(r"\s+", "", str(road))
            by_i = to_i(by)
            stage = {"range": cand}
            stage["use"] = [c for c in stage["range"] if c[1]]
            stage["year"] = [c for c in stage["use"] if by_i and c[2] == by_i]
            stage["road"] = [c for c in stage["year"] if road_k and c[3] and c[3] in road_k]
            for k, v in stage.items():
                steps[k][bucket(len(v))] += 1
                steps_rows[k][bucket(len(v))] += n
            for a, m in zip(gg["contract_area"], gg["n"]):
                ca = to_f(a)
                if math.isnan(ca):
                    area["no_contract_area"] += int(m)
                elif any(not math.isnan(c[4]) and abs(c[4] - ca) <= GROSS_TOL for c in stage["year"]):
                    area["leased_area_equals_gross_of_year_candidate"] += int(m)
                else:
                    area["leased_area_not_equal"] += int(m)
    return {"rows": rows_total, "signatures": int(len(sig)), "lot_shape_rows": dict(lot_shape), "fails_rows": dict(fails),
            "candidate_buckets_signatures": {k: dict(v) for k, v in steps.items()},
            "candidate_buckets_rows": {k: dict(v) for k, v in steps_rows.items()},
            "leased_area_rows": dict(area)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    t0 = time.time()
    rent, coll = ro(get_rent_engine()), ro(get_collective_engine())
    try:
        a = part_a(rent, coll)
        print("A done", round(time.time() - t0, 1), flush=True)
        b = part_b(rent)
    finally:
        rent.close()
        coll.close()
    rep = {"plan_step": "6 (rent) — measurement only, read only", "window": "contract_year >= 2019, is_valid",
           "title_edition": EDITION, "A_collective_types": a, "B_detached": b, "seconds": round(time.time() - t0, 1)}
    args.out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
