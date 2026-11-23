"""Audit same-parcel shop matches, then summarize the verified research sample."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from math import log
from pathlib import Path
from statistics import correlation, mean, median, quantiles

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from parcel_master.paths import TITLE_COLS

LOG = ROOT / "logs" / "insight-q14"
SNAPSHOTS = ("2024-09", "2025-07")
MIN_COMPLEXES = 10
COMMERCIAL = re.compile("근린생활|판매|상가|점포|업무|위락|숙박|공장|창고|시장")
SHOP_SUFFIX = re.compile(r"(?:단지내)?(?:상가(?:동)?|근린생활시설(?:동)?|점포)$")
APARTMENT = re.compile("아파트|공동주택")


def normalize(value: str) -> str:
    return re.sub(r"[\W_]", "", unicodedata.normalize("NFKC", value).casefold())


def complex_name(value: str) -> str:
    return re.sub("아파트$", "", normalize(value))


@dataclass(frozen=True)
class Title:
    pk: str
    name: str
    dong: str
    role: str
    purpose: str
    detail: str
    households: int
    above: int | None
    below: int | None
    approved: date | None


def integer(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def parse_title(pk: str, raw: bytes) -> Title:
    parts = raw.rstrip(b"\r\n").decode("utf-8-sig").split("|")
    if len(parts) not in (76, 77):
        raise ValueError("Unexpected register title format")
    approval = parts[TITLE_COLS["approve_date"]].strip()
    try:
        approved = date.fromisoformat(approval) if len(approval) == 8 else None
    except ValueError:
        approved = None
    return Title(
        pk=pk,
        name=parts[TITLE_COLS["building_name"]].strip(),
        dong=parts[TITLE_COLS["dong_name"]].strip(),
        role=parts[24].strip(),
        purpose=parts[TITLE_COLS["main_purpose"]].strip(),
        detail=parts[TITLE_COLS["purpose_detail"]].strip(),
        households=integer(parts[TITLE_COLS["households"]]) or 0,
        above=integer(parts[TITLE_COLS["floors_above"]]),
        below=integer(parts[TITLE_COLS["floors_below"]]),
        approved=approved,
    )


def ledger_rows(db: sqlite3.Connection, kind: str, pnu: str) -> list[tuple]:
    if kind == "title":
        sql = """
            SELECT o.snapshot, o.pk, v.raw
            FROM title_observation o JOIN title_version v USING(pk, raw_hash)
            WHERE o.pnu = ? AND o.snapshot IN (?, ?)
        """
    else:
        sql = """
            SELECT o.snapshot, o.pk, v.raw
            FROM summary_observation o JOIN summary_version v USING(pk, raw_hash)
            WHERE o.pnu = ? AND o.snapshot IN (?, ?)
        """
    return db.execute(sql, (pnu, *SNAPSHOTS)).fetchall()


def compatible_floor(title: Title, floor: float) -> bool:
    if floor > 0:
        return title.above is None or floor <= title.above
    return title.below is None or -floor <= title.below


def explicit_shop_title(title: Title, name: str) -> bool:
    title_name = normalize(title.name)
    suffix_in_name = SHOP_SUFFIX.search(title_name)
    separate_title = bool(COMMERCIAL.search(title.purpose)) and title.households == 0
    if not separate_title:
        return False
    if suffix_in_name and complex_name(title_name[:suffix_in_name.start()]) == name:
        return True
    return complex_name(title.name) == name and (
        title.role == "부속건축물" or bool(SHOP_SUFFIX.search(normalize(title.dong)))
    )


def audit_shop(row: dict, titles: tuple[Title, ...]) -> tuple[str, str]:
    if not titles:
        return "held_no_title", ""
    name = complex_name(row["danji_name"])
    if not name:
        return "held_no_complex_name", ""
    if not row["contract_date"] or not row["building_year"]:
        return "held_missing_trade_fields", ""
    contract = date.fromisoformat(row["contract_date"])
    trade_year = int(row["building_year"])
    floor = float(row["floor"]) if row["floor"] else None
    if floor == 0:
        floor = None

    commercial = [
        t for t in titles
        if COMMERCIAL.search(t.purpose + " " + t.detail + " " + t.dong)
        or not t.purpose
    ]
    plausible = [
        t for t in commercial
        if (t.approved is None or (t.approved <= contract and t.approved.year == trade_year))
        and (floor is None or compatible_floor(t, floor))
    ]
    named_shop = {
        t.pk for t in plausible
        if t.approved is not None and explicit_shop_title(t, name)
    }
    apartment = any(
        t.households > 0 and APARTMENT.search(t.purpose)
        and complex_name(t.name) == name
        and t.approved is not None and t.approved <= contract
        for t in titles
    )
    if not named_shop:
        return "held_no_named_compatible_shop", ""
    if not apartment:
        return "held_no_exact_apartment_title", ""
    if len(named_shop) != 1 or {t.pk for t in plausible} != named_shop:
        return "held_competing_title", ""
    status = "verified_building" if floor is not None else "verified_building_floor_unknown"
    return status, next(iter(named_shop))


def compute_sample(groups: dict, shop_field: str, apt_min: int, shop_min: int) -> dict:
    rows = {}
    exclusions = Counter()
    for key, group in groups.items():
        apt, shops = group["apt"], group[shop_field]
        if len(apt) < apt_min:
            exclusions["apartments_below_minimum"] += 1
        elif len(shops) < shop_min:
            exclusions["shops_below_minimum"] += 1
        else:
            rows[key] = (median(apt), median(shops))
    return {"rows": rows, "excluded": dict(exclusions)}


def pearson(x: list[float], y: list[float]) -> float | None:
    if len(x) < 2 or len(set(x)) < 2 or len(set(y)) < 2:
        return None
    return round(correlation(x, y), 4)


def summarize(rows: dict, *, include_small_diagnostic: bool = False) -> dict:
    result = {"n": len(rows)}
    small = len(rows) < MIN_COMPLEXES
    if small and not (include_small_diagnostic and len(rows) >= 4):
        return {**result, "status": "insufficient_complexes"}
    apt, shop = map(list, zip(*rows.values()))
    ratios = [100 * b / a for a, b in zip(apt, shop)]
    q25, _, q75 = quantiles(ratios, n=4, method="inclusive")
    result = {
        **result,
        "status": "small_sample_diagnostic" if small else "exploratory",
        "pearson": pearson(apt, shop),
        "apt_unit_median": round(median(apt), 2),
        "shop_unit_median": round(median(shop), 2),
        "difference_median": round(median(b - a for a, b in zip(apt, shop)), 2),
        "ratio_pct_median": round(median(ratios), 2),
        "ratio_pct_p25": round(q25, 2),
        "ratio_pct_p75": round(q75, 2),
    }
    if small:
        leave_one_out = [
            pearson(apt[:i] + apt[i+1:], shop[:i] + shop[i+1:]) for i in range(len(apt))
        ]
        defined = [r for r in leave_one_out if r is not None]
        result["leave_one_out_pearson_range"] = [min(defined), max(defined)] if defined else None
    return result


def adjusted(rows: dict, groups: dict) -> dict:
    by_region = defaultdict(list)
    for key, (apt, shop) in rows.items():
        group = groups[key]
        if group["region"] and group["households"] > 0:
            by_region[group["region"]].append((log(apt), log(shop), log(group["households"])))

    kept = [group for group in by_region.values() if len(group) >= 5]
    n = sum(map(len, kept))
    result = {"n": n, "regions": len(kept), "excluded": len(rows) - n}
    if n < 20 or len(kept) < 2:
        return {**result, "status": "insufficient_region_sample"}

    raw_a, raw_s, apt, shop, size = [], [], [], [], []
    for group in kept:
        a, s, h = map(list, zip(*group))
        raw_a.extend(a)
        raw_s.extend(s)
        for values, destination in ((a, apt), (s, shop), (h, size)):
            center = mean(values)
            destination.extend(value - center for value in values)
    size_ss = sum(value ** 2 for value in size)
    if not size_ss:
        return {**result, "status": "no_household_variation"}

    def residual(values: list[float]) -> list[float]:
        slope = sum(value * h for value, h in zip(values, size)) / size_ss
        return [value - slope * h for value, h in zip(values, size)]

    return {
        **result,
        "status": "exploratory",
        "raw_log_pearson_same_sample": pearson(raw_a, raw_s),
        "region_adjusted_log_pearson": pearson(apt, shop),
        "region_and_households_adjusted_log_pearson": pearson(residual(apt), residual(shop)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()
    groups = {}
    shops = []
    with (LOG / "candidates.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            key = (int(row["year"]), row["danji_code"])
            group = groups.setdefault(key, {
                "apt": [], "parcel": [], "all": [], "known_floor": [], "first": [],
                "region": row["kapt_pnu"][:2], "households": int(row["households"]),
            })
            value = float(row["unit_price"])
            if row["kind"] == "apt":
                group["apt"].append(value)
            else:
                group["parcel"].append(value)
                shops.append((key, row, value))
    if not shops or any(not g["apt"] or not g["parcel"] for g in groups.values()):
        raise ValueError("Incomplete candidate extract")
    if len({row["shop_id"] for _, row, _ in shops}) != len(shops):
        raise ValueError("A shop transaction was matched more than once")

    registers = {}
    audit_counts = defaultdict(Counter)
    with sqlite3.connect(args.ledger.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        sources = db.execute("""
            SELECT kind, snapshot, loaded_rows, sha256 FROM source_file
            WHERE snapshot IN (?, ?) ORDER BY snapshot, kind
        """, SNAPSHOTS).fetchall()
        if len(sources) != 4:
            raise ValueError("Missing research register editions")
        for pnu in sorted({row["pnu"] for _, row, _ in shops}):
            title_rows = ledger_rows(db, "title", pnu)
            summary_rows = ledger_rows(db, "summary", pnu)
            registers[pnu] = (
                tuple({parse_title(pk, raw) for _, pk, raw in title_rows}),
                tuple(sorted({snap for snap, _, _ in summary_rows})),
            )

    with (LOG / "membership_review.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        columns = ("year", "danji_code", "shop_id", "pnu", "status", "title_pk", "summary_editions")
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for key, row, value in shops:
            titles, summaries = registers[row["pnu"]]
            status, pk = audit_shop(row, titles)
            audit_counts[key[0]][status] += 1
            writer.writerow({
                **{k: row[k] for k in ("year", "danji_code", "shop_id", "pnu")},
                "status": status, "title_pk": pk, "summary_editions": ",".join(summaries),
            })
            if status in {"verified_building", "verified_building_floor_unknown"}:
                groups[key]["all"].append(value)
                if status == "verified_building":
                    groups[key]["known_floor"].append(value)
                    if float(row["floor"]) == 1:
                        groups[key]["first"].append(value)

    candidates = compute_sample(groups, "parcel", 5, 3)["rows"]
    output = {
        "register_sources": sources,
        "min_complexes_for_summary": MIN_COMPLEXES,
        "candidate_complexes": len({key[1] for key in candidates}),
        "candidate_complex_years": len(candidates),
        "candidate_shop_transactions": len(shops),
        "basic_candidates_with_any_verified_trade": sum(bool(groups[key]["all"]) for key in candidates),
        "verified_complexes_any_trade": len({key[1] for key, g in groups.items() if g["all"]}),
        "verified_complex_years_any_trade": sum(bool(g["all"]) for g in groups.values()),
        "parcels": len(registers),
        "parcels_with_title": sum(bool(t) for t, _ in registers.values()),
        "parcels_with_summary": sum(bool(s) for _, s in registers.values()),
        "years": {},
    }
    scatter = []
    for year in (2024, 2025):
        by_year = {k: g for k, g in groups.items() if k[0] == year}
        candidate = compute_sample(by_year, "parcel", 5, 3)
        year_output = {
            "parcel_complex_years": len(by_year),
            "parcel_excluded": candidate["excluded"],
            "parcel_basic": len(candidate["rows"]),
            "parcel_basic_with_any_verified_trade": sum(bool(by_year[key]["all"]) for key in candidate["rows"]),
            "audit_transactions": dict(sorted(audit_counts[year].items())),
            "verified_complex_years_any_trade": sum(bool(g["all"]) for g in by_year.values()),
            "verified_first_floor_transactions": sum(len(g["first"]) for g in by_year.values()),
            "samples": {},
        }
        for label, apt_min, shop_min in (("basic", 5, 3), ("strict", 10, 5)):
            overall = compute_sample(by_year, "all", apt_min, shop_min)
            known_floor = compute_sample(by_year, "known_floor", apt_min, shop_min)
            first = compute_sample(by_year, "first", apt_min, shop_min)
            paired = {key: overall["rows"][key] for key in first["rows"]}
            year_output["samples"][label] = {
                "all": summarize(overall["rows"], include_small_diagnostic=True),
                "all_known_floor_only": summarize(known_floor["rows"]),
                "first": summarize(first["rows"]),
                "all_same_complexes_as_first": summarize(paired),
                "all_excluded": overall["excluded"],
                "first_excluded": first["excluded"],
                "all_adjusted": adjusted(overall["rows"], by_year),
                "first_adjusted": adjusted(first["rows"], by_year),
            }
            for floor_group, sample in (("all", overall), ("first", first)):
                scatter.extend((year, label, floor_group, key[1], a, s)
                               for key, (a, s) in sorted(sample["rows"].items()))
        output["years"][year] = year_output

    with (LOG / "scatter_points.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("year", "threshold", "floor_group", "danji_code", "apt_unit", "shop_unit"))
        writer.writerows(scatter)
    print(json.dumps(output, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
