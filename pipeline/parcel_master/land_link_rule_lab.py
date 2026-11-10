"""Shadow lab for land link rules: V1 baseline, code generation V2, A–D, area-near.

Read only. Writes count-only JSON. No parcel, PNU or lot leaves the process.

Two modes share one set of rule functions.

``synthetic``: there is no public unmasked land lot to use as truth, so parcels
with a known PNU are turned into fake transactions. Jimok, area and zone come
from one plate. The main lot is masked the way the trade data masks it (first
digit kept, the rest ``*``, no sub lot). The contract date is the day after that
plate. Each rule is scored two ways:

- ``with_truth``: the true parcel is in the ledger. Linked to it = correct, to
  another parcel = wrong.
- ``truth_removed``: the true parcel is dropped from the candidate pool. This
  stands in for a report error, a split, or a ledger gap. Any link is wrong.

This catches confusion between parcels that look alike once the lot is masked.
It cannot catch errors in the trade report itself, or a parcel split around the
contract date, because the synthetic traits are copied from the ledger.

``real``: actual transactions. It counts how many extra links each rule would
add, and builds a cross table of the trade road condition against the ledger
road frontage for V1 exact links.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from contextlib import closing
from datetime import date, timedelta
from itertools import groupby
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from sqlalchemy import text  # noqa: E402

from db_utils import get_engine  # noqa: E402
from parcel_master import land_trait_link_materialize as v1  # noqa: E402
from parcel_master.cheongju_land_gap_probe import _split_candidates  # noqa: E402
from parcel_master.cheongju_land_label_rule_probe import attach_price_detail, classify_link_v1  # noqa: E402
from parcel_master.cheongju_land_link_probe import _add_plate, latest_consistent_plate  # noqa: E402
from parcel_master.land_link_rejudge_shadow import code_gen_pairs  # noqa: E402
from parcel_master.land_trait_link_missing import _ranges  # noqa: E402
from parcel_master.national_land_link_shadow import LEDGER  # noqa: E402
from parcel_master.trait_link_helpers import area_key, lot_matches  # noqa: E402

LINKED = ("exact", "label_normalized")
FROM_ASOF = "2019-01-01"
OBS_SQL = """
    SELECT pnu, asof, price_year, price_month, jimok_label, area, zone1_label, zone2_label, price,
           use_label, height_label, shape_label, road_label
    FROM parcel_observation WHERE pnu >= ? AND pnu < ?
"""
CONFLICT_SQL = """
    SELECT pnu, asof, price_year, price_month, source_file,
           jimok_code, jimok_label, area, zone1_code, zone1_label,
           zone2_code, zone2_label, use_code, use_label, height_code, height_label,
           shape_code, shape_label, road_code, road_label, price
    FROM observation_conflict WHERE pnu >= ? AND pnu < ?
    ORDER BY pnu, asof, attr_hash
"""
TRAIT_NAMES = ("zones", "use", "height", "shape", "road")

# Trade road condition -> ledger road frontage families. Corner lots count as the wider road.
ROAD_FAMILY = {
    "광대": "25이상",
    "중로": "25미만",
    "소로": "12미만",
    "세로": "8미만",
    "맹지": "-",
}
TRUSTED_ROAD_DEFAULT = ("25이상", "25미만", "12미만", "8미만", "-")


def road_family(label: str) -> str | None:
    text_value = (label or "").strip()
    for prefix, family in ROAD_FAMILY.items():
        if text_value.startswith(prefix):
            return family
    return None


def mask_lot(pnu: str) -> str:
    main = str(int(pnu[11:15]))
    masked = "*" * len(main) if len(main) == 1 else main[0] + "*" * (len(main) - 1)
    return ("산" if pnu[10] == "2" else "") + masked


# ---------------------------------------------------------------- ledger slice


class Slice:
    """Plates, index, extras and conflict views for a set of PNU ranges."""

    def __init__(self, db, ranges):
        self.plates = defaultdict(list)
        self.index = defaultdict(set)
        self.extras = {}
        grouped = defaultdict(list)
        for low, high in ranges:
            for row in db.execute(OBS_SQL, (low, high)):
                _add_plate(self.plates, self.index, row[:9], prefixes=(row[0][:5],))
                self.extras[(row[0], str(row[1])[:10])] = tuple(str(v or "").strip() for v in row[9:13])
            for item in db.execute(CONFLICT_SQL, (low, high)):
                grouped[(item[0], str(item[1])[:10], str(item[2]), str(item[3]))].append(item)
        for entries in self.plates.values():
            entries.sort()
        self.normalized, self.conflict_asofs, self.substantive = v1._conflict_views(grouped)
        self.by_bjd = defaultdict(list)
        for pnu in self.plates:
            self.by_bjd[pnu[:10]].append(pnu)

    def latest(self, pnu, day):
        group = latest_consistent_plate(self.plates[pnu], day)
        return group[0] if group else None

    def traits(self, pnu, day):
        plate = self.latest(pnu, day)
        if plate is None:
            return None
        use, height, shape, road = self.extras.get((pnu, plate[0]), ("", "", "", ""))
        return {"zones": plate[5], "use": use, "height": height, "shape": shape, "road": road}


# ---------------------------------------------------------------- rules


def _masked(slice_, bjd, mask, removed):
    return [
        pnu for pnu in slice_.by_bjd.get(bjd, ())
        if pnu != removed and lot_matches(mask, pnu, str(int(pnu[11:15])))
    ]


def judge_v1(slice_, tx, removed=None):
    """(status, pnu, prior) under V1. ``removed`` hides one parcel from the pool."""
    key = (tx["bjd"], tx["jimok"], tx["area"])
    index = {key: slice_.index.get(key, set()) - {removed}}
    prior, later = _split_candidates(
        tx["bjd"], tx["jimok"], tx["area"], tx["zone"], tx["mask"], tx["day"], index, slice_.plates
    )
    kind, pnu = classify_link_v1(
        day=tx["day"], jimok=tx["jimok"], area=tx["area"], zone=tx["zone"], prior=prior, later=later,
        plates=slice_.plates, normalized=slice_.normalized, conflict_asofs=slice_.conflict_asofs,
        substantive_asofs=slice_.substantive,
    )
    return kind, pnu, prior


def rule_area_near(slice_, tx, removed=None):
    """Same jimok, zone and mask; area within max(1 m2, 1%); exactly one parcel."""
    target = float(tx["area"])
    tolerance = max(1.0, target * 0.01)
    found = []
    for pnu in _masked(slice_, tx["bjd"], tx["mask"], removed):
        plate = slice_.latest(pnu, tx["day"])
        if plate and plate[3] == tx["jimok"] and tx["zone"] in plate[5] and abs(float(plate[4]) - target) <= tolerance:
            found.append(pnu)
    return found[0] if len(found) == 1 else None


def rule_zone_blank(slice_, tx, removed=None):
    """A: latest plate zone blank, everything else unique, no zone-filled look-alike in the dong."""
    blank = []
    for pnu in slice_.by_bjd.get(tx["bjd"], ()):
        if pnu == removed:
            continue
        plate = slice_.latest(pnu, tx["day"])
        if not plate or plate[3] != tx["jimok"] or plate[4] != tx["area"]:
            continue
        if plate[5]:
            return None
        if lot_matches(tx["mask"], pnu, str(int(pnu[11:15]))):
            blank.append(pnu)
    return blank[0] if len(blank) == 1 else None


def consensus(slice_, pnus, day, year):
    """B: per-item agreement over candidates. Price needs the same base year and amount."""
    prices = {attach_price_detail(slice_.plates[pnu] + slice_.normalized.get(pnu, []), year) for pnu in pnus}
    price = None
    if len(prices) == 1:
        status, amount, base_year = next(iter(prices))
        if status in ("same_year", "previous_year"):
            price = (amount, base_year)
    traits = [slice_.traits(pnu, day) for pnu in pnus]
    agreed = {}
    for name in TRAIT_NAMES:
        values = {t[name] if t else None for t in traits}
        if len(values) == 1:
            value = next(iter(values))
            if value:
                agreed[name] = value
    return price, agreed


def road_resolve(slice_, prior, day, road, trusted):
    if road not in trusted or len(prior) < 2:
        return None
    hits = [pnu for pnu in prior if road_family((slice_.traits(pnu, day) or {}).get("road", "")) == road]
    return hits[0] if len(hits) == 1 else None


def first_seen(slice_, tx, later):
    """D: one later-only candidate whose first matching plate is within 12 months."""
    if len(later) != 1:
        return None
    pnu = later[0]
    if any(plate[0] <= tx["day"] for plate in slice_.plates[pnu]):
        return None
    first = min(plate[0] for plate in slice_.plates[pnu])
    gap = (date.fromisoformat(first) - date.fromisoformat(tx["day"])).days
    return pnu if gap <= 365 else None


# ---------------------------------------------------------------- synthetic


def _sample_dongs(conn, sido, count, rng):
    rows = conn.execute(
        text("SELECT DISTINCT beopjungri_code FROM region_codes WHERE sido_code = :s"), {"s": sido}
    ).all()
    codes = sorted(str(code).strip() for (code,) in rows if len(str(code).strip()) == 10)
    rng.shuffle(codes)
    return codes[:count]


def _synthetic_rows(slice_, bjd, per_dong, rng, perturb):
    parcels = [pnu for pnu in slice_.by_bjd.get(bjd, ()) if pnu[11:15] != "0000"]
    rng.shuffle(parcels)
    made = []
    for pnu in parcels:
        asofs = sorted({plate[0] for plate in slice_.plates[pnu] if plate[0] >= FROM_ASOF})
        if not asofs:
            continue
        asof = rng.choice(asofs)
        day = (date.fromisoformat(asof) + timedelta(days=1)).isoformat()
        plate = slice_.latest(pnu, day)
        if plate is None or plate[0] != asof or not plate[5]:
            continue
        area = plate[4]
        if perturb:
            base = float(area)
            delta = rng.uniform(0.05, max(1.0, base * 0.01))
            area = area_key(base + rng.choice((-1, 1)) * delta)
            if area is None or area == plate[4]:
                continue
        made.append({
            "truth": pnu, "bjd": bjd, "jimok": plate[3], "area": area,
            "zone": sorted(plate[5])[0], "mask": mask_lot(pnu), "day": day, "year": int(day[:4]),
        })
        if len(made) >= per_dong:
            break
    return made


def _score(counter, prefix, pnu, truth):
    if pnu is None:
        counter[f"{prefix}:unlinked"] += 1
    elif pnu == truth:
        counter[f"{prefix}:correct"] += 1
    else:
        counter[f"{prefix}:wrong"] += 1


def synthetic(args):
    rng = random.Random(args.seed)
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        pairs = v1.load_pairs(conn)
        dongs = {sido: _sample_dongs(conn, sido, args.dongs, rng) for sido in args.sido}
    engine.dispose()
    reverse = {previous: current for current, (previous, _effective) in pairs.items()}
    trusted = tuple(args.trusted_road)
    results = defaultdict(Counter)
    by_year = defaultdict(Counter)
    b_items = defaultdict(Counter)
    started = time.perf_counter()
    uri = LEDGER.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        gen_pairs, missing = code_gen_pairs(pairs, db)
        road_table = json.loads(Path(args.road_table).read_text(encoding="utf-8")) if args.road_table else None
        for sido, codes in dongs.items():
            for bjd in codes:
                slice_ = Slice(db, [(bjd + "0" * 9, bjd + "9" * 9)])
                for perturb in (False, True):
                    for tx in _synthetic_rows(slice_, bjd, args.per_dong, rng, perturb):
                        group = sido if not perturb else f"{sido}:area_perturbed"
                        bucket = results[group]
                        bucket["n"] += 1
                        truth = tx["truth"]
                        kind, pnu, prior = judge_v1(slice_, tx)
                        linked = pnu if kind in LINKED else None
                        _score(bucket, "v1", linked, truth)
                        if not perturb:
                            by_year[f"{sido}:{tx['year']}"]["n"] += 1
                            by_year[f"{sido}:{tx['year']}"][f"v1:{'correct' if linked == truth else 'wrong' if linked else 'unlinked'}"] += 1
                        kind_out, pnu_out, prior_out = judge_v1(slice_, tx, removed=truth)
                        _score(bucket, "v1_truth_removed", pnu_out if kind_out in LINKED else None, truth)
                        if not perturb and kind_out == "multiple_candidates":
                            item = b_items[f"{sido}:truth_removed"]
                            item["multiple"] += 1
                            price, agreed = consensus(slice_, prior_out, tx["day"], tx["year"])
                            truth_price = attach_price_detail(slice_.plates[truth] + slice_.normalized.get(truth, []), tx["year"])
                            truth_traits = slice_.traits(truth, tx["day"]) or {}
                            if price is not None:
                                item["price:supplied"] += 1
                                item["price:correct" if (truth_price[1], truth_price[2]) == price else "price:wrong"] += 1
                            for name, value in agreed.items():
                                item[f"{name}:supplied"] += 1
                                item[f"{name}:correct" if truth_traits.get(name) == value else f"{name}:wrong"] += 1
                            if road_table:
                                family = road_family(truth_traits.get("road", ""))
                                weights = road_table.get(family or "", {})
                                if weights:
                                    options, probs = zip(*weights.items())
                                    road = rng.choices(options, probs)[0]
                                    _score(item, "c_road", road_resolve(slice_, prior_out, tx["day"], road, trusted), truth)
                        if linked is None:
                            _score(bucket, "area_near", rule_area_near(slice_, tx), truth)
                            _score(bucket, "area_near_truth_removed", rule_area_near(slice_, tx, removed=truth), truth)
                        if not perturb and kind == "multiple_candidates":
                            bucket["multiple"] += 1
                            price, agreed = consensus(slice_, prior, tx["day"], tx["year"])
                            truth_price = attach_price_detail(slice_.plates[truth] + slice_.normalized.get(truth, []), tx["year"])
                            truth_traits = slice_.traits(truth, tx["day"]) or {}
                            item = b_items[sido]
                            item["multiple"] += 1
                            if price is not None:
                                item["price:supplied"] += 1
                                item["price:correct" if (truth_price[1], truth_price[2]) == price else "price:wrong"] += 1
                            for name, value in agreed.items():
                                item[f"{name}:supplied"] += 1
                                item[f"{name}:correct" if truth_traits.get(name) == value else f"{name}:wrong"] += 1
                            if road_table:
                                family = road_family(truth_traits.get("road", ""))
                                weights = road_table.get(family or "", {})
                                if weights:
                                    options, probs = zip(*weights.items())
                                    road = rng.choices(options, probs)[0]
                                    _score(item, "c_road", road_resolve(slice_, prior, tx["day"], road, trusted), truth)
                        if not perturb:
                            # A: blank the true parcel's zone on its plate, then ask the rule.
                            plates = slice_.plates[truth]
                            saved = list(plates)
                            target = prior_asof(saved, tx["day"])
                            slice_.plates[truth] = [p[:5] + (frozenset(),) + p[6:] if p[0] == target else p for p in saved]
                            kind_a, pnu_a, _ = judge_v1(slice_, tx)
                            if kind_a not in LINKED:
                                bucket["zone_blank_cases"] += 1
                                _score(bucket, "zone_blank", rule_zone_blank(slice_, tx), truth)
                                _score(bucket, "zone_blank_truth_removed", rule_zone_blank(slice_, tx, removed=truth), truth)
                            slice_.plates[truth] = saved
                        if not perturb and tx["bjd"] in reverse and reverse[tx["bjd"]][:2] in missing:
                            coded = dict(tx, day=max(tx["day"], "2026-07-21"))
                            new_code = reverse[tx["bjd"]]
                            kind_o, pnu_o, _ = judge_v1(slice_, coded)
                            _score(bucket, "old_code_same_day", pnu_o if kind_o in LINKED else None, truth)
                            for label, use_pairs in (("v1_new_code", pairs), ("v2_new_code", gen_pairs)):
                                resolved, _ = v1.resolve_beopjungri(new_code, coded["day"], use_pairs)
                                probe = dict(coded, bjd=resolved)
                                kind_c, pnu_c, _ = judge_v1(slice_, probe)
                                _score(bucket, label, pnu_c if kind_c in LINKED else None, truth)
                print(f"{sido} {len(codes)} dongs {time.perf_counter() - started:.0f}s", flush=True)
    report = {
        "mode": "synthetic_mask_test",
        "seed": args.seed,
        "dongs_per_sido": args.dongs,
        "per_dong": args.per_dong,
        "trusted_road": list(trusted),
        "results": {k: dict(v) for k, v in sorted(results.items())},
        "v1_by_sido_year": {k: dict(v) for k, v in sorted(by_year.items())},
        "multiple_consensus": {k: dict(v) for k, v in sorted(b_items.items())},
        "seconds": round(time.perf_counter() - started),
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def prior_asof(plates, day):
    chosen = None
    for plate in plates:
        if plate[0] <= day:
            chosen = plate[0]
    return chosen


# ---------------------------------------------------------------- real


REAL_FETCH = text(
    """
    SELECT t.transaction_hash, t.contract_date, t.beopjungri_code, t.sigungu_code,
           t.land_category, t.zone_type, t.area_sqm, t.is_partial_ownership,
           t.is_cancelled, t.is_valid, t.lot_display, t.road_condition
    FROM land_transactions t
    WHERE t.contract_date >= :start AND t.contract_date < :stop
      AND left(t.sigungu_code, 2) = ANY(:sidos)
    ORDER BY t.sigungu_code
    """
)


def real(args):
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        pairs = v1.load_pairs(conn)
        fetched = [dict(r) for r in conn.execute(REAL_FETCH, {"start": args.start, "stop": args.stop, "sidos": list(args.sido)}).mappings()]
    engine.dispose()
    trusted = tuple(args.trusted_road)
    counts = defaultdict(Counter)
    road_cross = defaultdict(Counter)
    started = time.perf_counter()
    uri = LEDGER.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        for number, (code, group) in enumerate(groupby(fetched, lambda r: str(r["sigungu_code"] or "").strip()), start=1):
            batch = list(group)
            if len(code) != 5 or not code.isdigit():
                continue
            slice_ = Slice(db, list(_ranges(code, batch, pairs)))
            for row in batch:
                if v1.exclusion_reason(row) or len(str(row["beopjungri_code"]).strip()) != 10:
                    continue
                day = str(row["contract_date"])[:10]
                bjd, _ = v1.resolve_beopjungri(str(row["beopjungri_code"]).strip(), day, pairs)
                tx = {
                    "bjd": bjd, "jimok": str(row["land_category"] or "").strip(),
                    "area": area_key(row["area_sqm"]) or "", "zone": str(row["zone_type"]),
                    "mask": row["lot_display"], "day": day, "year": int(day[:4]),
                }
                key = f"{code[:2]}:{day[:4]}"
                bucket = counts[key]
                bucket["judged"] += 1
                kind, pnu, prior = judge_v1(slice_, tx)
                bucket[f"v1:{kind}"] += 1
                road = str(row["road_condition"] or "").strip()
                if kind in LINKED and pnu:
                    family = road_family((slice_.traits(pnu, day) or {}).get("road", ""))
                    road_cross[family or "(none)"][road or "(blank)"] += 1
                    continue
                if kind == "multiple_candidates":
                    price, agreed = consensus(slice_, prior, day, tx["year"])
                    bucket["b:price_consensus"] += int(price is not None)
                    for name in agreed:
                        bucket[f"b:{name}_consensus"] += 1
                    bucket["c:road_resolved"] += int(road_resolve(slice_, prior, day, road, trusted) is not None)
                    continue
                if rule_zone_blank(slice_, tx):
                    bucket["a:zone_blank_linked"] += 1
                if rule_area_near(slice_, tx):
                    bucket["near:linked"] += 1
                key_index = {(bjd, tx["jimok"], tx["area"]): slice_.index.get((bjd, tx["jimok"], tx["area"]), set())}
                _prior, later = _split_candidates(bjd, tx["jimok"], tx["area"], tx["zone"], tx["mask"], day, key_index, slice_.plates)
                if first_seen(slice_, tx, later):
                    bucket["d:first_seen_12m"] += 1
            if number % 10 == 0:
                print(f"{number} sigungu {time.perf_counter() - started:.0f}s", flush=True)
    report = {
        "mode": "real_rule_counts",
        "window": [args.start, args.stop],
        "sido": list(args.sido),
        "trusted_road": list(trusted),
        "by_sido_year": {k: dict(v) for k, v in sorted(counts.items())},
        "road_cross_v1_linked": {k: dict(v) for k, v in sorted(road_cross.items())},
        "seconds": round(time.perf_counter() - started),
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("synthetic", "real"))
    parser.add_argument("--sido", nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261110)
    parser.add_argument("--dongs", type=int, default=40)
    parser.add_argument("--per-dong", type=int, default=50)
    parser.add_argument("--start", default="2019-01-01")
    parser.add_argument("--stop", default="2024-01-01")
    parser.add_argument("--road-table", help="JSON {ledger_family: {trade_road: weight}} from a real run")
    parser.add_argument("--trusted-road", nargs="*", default=list(TRUSTED_ROAD_DEFAULT))
    args = parser.parse_args()
    report = synthetic(args) if args.mode == "synthetic" else real(args)
    print(json.dumps({k: report[k] for k in report if k in ("results", "seconds")}, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
