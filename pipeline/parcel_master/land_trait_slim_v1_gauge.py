"""Size gauge for the land trait slim layer (plan step 2).

Reads the frozen national ledger read-only for a set of sigungu prefixes.
Counts how many rows each slim table would hold. Writes counts only.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from parcel_master.cheongju_land_link_probe import LEDGER, compact_jimok, compact_zones  # noqa: E402
from parcel_master.trait_link_helpers import area_key  # noqa: E402

LEDGER_ROWS = 970_577_839
CODE_FIELDS = ("jimok", "zone1", "zone2", "use", "height", "shape", "road")


def _bounds(code: str) -> tuple[str, str]:
    return code + "0" * 14, f"{int(code) + 1:05d}" + "0" * 14


def _connect() -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{LEDGER.as_posix()}?mode=ro", uri=True)
    db.execute("PRAGMA query_only=ON")
    return db


def _runs(per_asof: list[tuple[str, object]]) -> int:
    runs = 0
    last = object()
    for _, attr in per_asof:
        if attr != last:
            runs += 1
            last = attr
    return runs


class Gauge:
    def __init__(self) -> None:
        self.rows = 0
        self.pnus = 0
        self.asofs = Counter()
        self.v1_runs = 0
        self.code_runs = 0
        self.asof_rows = 0
        self.asof_inconsistent_v1 = 0
        self.price_rows = 0
        self.price_year_multi = 0
        self.max_asofs_per_pnu = 0
        self.dictionary: dict[str, dict[str, Counter]] = {f: defaultdict(Counter) for f in CODE_FIELDS}

    def add_pnu(self, rows: list[tuple]) -> None:
        self.pnus += 1
        by_asof: dict[str, list[tuple]] = defaultdict(list)
        prices: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            by_asof[row[1]].append(row)
            prices[row[2]].add(row[21])
        v1_seq = []
        code_seq = []
        for asof in sorted(by_asof):
            group = by_asof[asof]
            self.asofs[asof] += 1
            v1_attrs = {(compact_jimok(r[5]), area_key(r[6]), compact_zones(r[8], r[10])) for r in group}
            if len(v1_attrs) != 1:
                self.asof_inconsistent_v1 += 1
            v1_seq.append((asof, frozenset(v1_attrs)))
            code_attrs = {(r[4], r[6], r[7], r[9], r[11], r[13], r[15], r[17]) for r in group}
            code_seq.append((asof, frozenset(code_attrs)))
        self.asof_rows += len(by_asof)
        self.max_asofs_per_pnu = max(self.max_asofs_per_pnu, len(by_asof))
        self.v1_runs += _runs(v1_seq)
        self.code_runs += _runs(code_seq)
        for values in prices.values():
            self.price_rows += len(values)
            if len(values) > 1:
                self.price_year_multi += 1

    def add_labels(self, row: tuple) -> None:
        pairs = ((row[4], row[5]), (row[7], row[8]), (row[9], row[10]), (row[11], row[12]),
                 (row[13], row[14]), (row[15], row[16]), (row[17], row[18]))
        for field, (code, label) in zip(CODE_FIELDS, pairs):
            self.dictionary[field][str(code or "")][str(label or "").strip()] += 1


SELECT_CLEAN = """
SELECT pnu, asof, price_year, price_month,
       jimok_code, jimok_label, area,
       zone1_code, zone1_label, zone2_code, zone2_label,
       use_code, use_label, height_code, height_label,
       shape_code, shape_label, road_code, road_label,
       '' AS source_file, '' AS pad, price
FROM parcel_observation WHERE pnu >= ? AND pnu < ?
"""

SELECT_CONFLICT = """
SELECT pnu, asof, price_year, price_month,
       jimok_code, jimok_label, area,
       zone1_code, zone1_label, zone2_code, zone2_label,
       use_code, use_label, height_code, height_label,
       shape_code, shape_label, road_code, road_label, price
FROM observation_conflict WHERE pnu >= ? AND pnu < ?
"""

SEMANTIC_FIELDS = {
    "jimok_code": 4, "area": 6, "zone1_code": 7, "zone2_code": 9, "use_code": 11,
    "height_code": 13, "shape_code": 15, "road_code": 17, "price": 19,
}


def scan_clean(gauge: Gauge, prefixes: list[str]) -> None:
    db = _connect()
    try:
        for prefix in prefixes:
            current = None
            buffer: list[tuple] = []
            cursor = db.execute(SELECT_CLEAN, _bounds(prefix))
            while True:
                chunk = cursor.fetchmany(100_000)
                if not chunk:
                    break
                for row in chunk:
                    gauge.rows += 1
                    gauge.add_labels(row)
                    if row[0] != current:
                        if buffer:
                            gauge.add_pnu(buffer)
                        current = row[0]
                        buffer = []
                    buffer.append(row)
            if buffer:
                gauge.add_pnu(buffer)
            print(f"clean {prefix} rows={gauge.rows} pnus={gauge.pnus}", flush=True)
    finally:
        db.close()


def scan_conflict(ranges: list[tuple[str, str]], gauge: Gauge | None) -> dict:
    rows = 0
    keys = 0
    label_only = 0
    semantic = 0
    differing = Counter()
    semantic_by_sido = Counter()

    def close(variants: list[tuple]) -> None:
        nonlocal keys, label_only, semantic
        keys += 1
        diff = [name for name, i in SEMANTIC_FIELDS.items() if len({v[i] for v in variants}) > 1]
        if diff:
            semantic += 1
            semantic_by_sido[variants[0][0][:2]] += 1
            for name in diff:
                differing[name] += 1
        else:
            label_only += 1

    db = _connect()
    try:
        for lo, hi in ranges:
            current = None
            variants: list[tuple] = []
            cursor = db.execute(SELECT_CONFLICT, (lo, hi))
            while True:
                chunk = cursor.fetchmany(100_000)
                if not chunk:
                    break
                for row in chunk:
                    rows += 1
                    if gauge is not None:
                        gauge.add_labels(row)
                    key = (row[0], row[1], row[2], row[3])
                    if key != current:
                        if variants:
                            close(variants)
                        current = key
                        variants = []
                    variants.append(row)
                if gauge is None and rows % 5_000_000 < 100_000:
                    print(f"conflict rows={rows} keys={keys}", flush=True)
            if variants:
                close(variants)
    finally:
        db.close()
    return {
        "variant_rows": rows,
        "keys": keys,
        "label_only_keys": label_only,
        "semantic_keys": semantic,
        "semantic_by_field": dict(differing.most_common()),
        "semantic_by_sido": dict(sorted(semantic_by_sido.items())),
    }


def dictionary_summary(gauge: Gauge) -> dict:
    out = {}
    for field, codes in gauge.dictionary.items():
        multi = 0
        blank_rows = 0
        total_rows = 0
        for labels in codes.values():
            nonblank = [label for label in labels if label]
            if len(nonblank) > 1:
                multi += 1
            blank_rows += labels.get("", 0)
            total_rows += sum(labels.values())
        out[field] = {
            "codes": len(codes),
            "codes_with_multiple_labels": multi,
            "blank_label_rows": blank_rows,
            "rows": total_rows,
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefixes", help="comma separated sigungu codes")
    ap.add_argument("--conflict-national", action="store_true", help="classify the whole conflict table only")
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    started = time.time()
    if args.conflict_national:
        report = {
            "label": args.label,
            "ledger": "LAND_TRAIT_LEDGER_V1 (read-only)",
            "conflict": scan_conflict([("", "9" * 20)], None),
            "elapsed_seconds": round(time.time() - started, 1),
        }
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.out} seconds={report['elapsed_seconds']}", flush=True)
        return
    prefixes = [p.strip() for p in (args.prefixes or "").split(",") if p.strip()]
    if not prefixes:
        raise SystemExit("--prefixes is required unless --conflict-national")
    gauge = Gauge()
    scan_clean(gauge, prefixes)
    conflict = scan_conflict([_bounds(p) for p in prefixes], gauge)
    scale = LEDGER_ROWS / gauge.rows if gauge.rows else 0.0
    report = {
        "label": args.label,
        "prefixes": prefixes,
        "ledger": "LAND_TRAIT_LEDGER_V1 (read-only)",
        "clean_rows": gauge.rows,
        "pnus": gauge.pnus,
        "pnu_asof_rows": gauge.asof_rows,
        "asof_inconsistent_v1": gauge.asof_inconsistent_v1,
        "max_asofs_per_pnu": gauge.max_asofs_per_pnu,
        "asofs_seen": dict(sorted(gauge.asofs.items())),
        "slim": {
            "v1_intervals": gauge.v1_runs,
            "code_intervals": gauge.code_runs,
            "price_rows": gauge.price_rows,
            "price_year_with_multiple_prices": gauge.price_year_multi,
        },
        "ratios_to_clean_rows": {
            "pnu_asof_rows": round(gauge.asof_rows / gauge.rows, 4),
            "v1_intervals": round(gauge.v1_runs / gauge.rows, 4),
            "code_intervals": round(gauge.code_runs / gauge.rows, 4),
            "price_rows": round(gauge.price_rows / gauge.rows, 4),
        },
        "national_estimate_by_row_ratio": {
            "scale": round(scale, 2),
            "pnu_asof_rows": round(gauge.asof_rows * scale),
            "v1_intervals": round(gauge.v1_runs * scale),
            "code_intervals": round(gauge.code_runs * scale),
            "price_rows": round(gauge.price_rows * scale),
        },
        "conflict": conflict,
        "dictionary": dictionary_summary(gauge),
        "elapsed_seconds": round(time.time() - started, 1),
    }
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.out} seconds={report['elapsed_seconds']}", flush=True)


if __name__ == "__main__":
    main()
