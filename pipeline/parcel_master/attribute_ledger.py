"""청주 속성 대장 v1. 토지특성 필지 명단 + 건축대장 세 판.

제품 DB에 쓰지 않는다. 도형·토지이용계획은 넣지 않는다.
규칙: docs/LEDGER_ATTRIBUTE_DB_PLAN.md
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
import sqlite3
from datetime import date
from pathlib import Path

from parcel_master.ledger_identity_v2 import DISTRICTS, VERSION, identify

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "research" / "cheongju_ledger"
LAB = ROOT / "docs" / "lab"
CACHE = Path(__file__).resolve().parent / "_cache"
DB_PATH = OUT / "attribute_ledger_v1.sqlite"
SCHEMA_VERSION = "attribute-ledger-v1"

TRAIT_BODY = (
    "year",
    "month",
    "jimok_code",
    "area",
    "zone1_code",
    "zone2_code",
    "use_code",
    "height_code",
    "shape_code",
    "road_code",
    "price",
)
BUILDING_SNAPSHOTS = ("2024-09", "2025-07", "2026-07")
TITLE_FILES = (
    ("일반", "title_일반_national_{snapshot}.csv"),
    ("집합", "title_집합_30_43_{snapshot}.csv"),
)

DDL = """
CREATE TABLE ledger_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE parcel_observation (
    vintage_year INTEGER NOT NULL,
    pnu TEXT NOT NULL,
    asof TEXT NOT NULL,
    price_year TEXT NOT NULL,
    price_month TEXT NOT NULL,
    jimok_code TEXT NOT NULL,
    jimok_label TEXT NOT NULL,
    area TEXT NOT NULL,
    zone1_code TEXT NOT NULL,
    zone1_label TEXT NOT NULL,
    zone2_code TEXT NOT NULL,
    zone2_label TEXT NOT NULL,
    use_code TEXT NOT NULL,
    use_label TEXT NOT NULL,
    height_code TEXT NOT NULL,
    height_label TEXT NOT NULL,
    shape_code TEXT NOT NULL,
    shape_label TEXT NOT NULL,
    road_code TEXT NOT NULL,
    road_label TEXT NOT NULL,
    price TEXT NOT NULL,
    source_file TEXT NOT NULL,
    PRIMARY KEY (vintage_year, pnu)
);
CREATE TABLE building_observation (
    snapshot TEXT NOT NULL,
    mgmt_pk TEXT NOT NULL,
    ledger_kind TEXT NOT NULL,
    pnu TEXT,
    hold_reason TEXT,
    structure_name TEXT NOT NULL,
    floors_above TEXT NOT NULL,
    floors_below TEXT NOT NULL,
    gross_area TEXT NOT NULL,
    plat_area TEXT NOT NULL,
    approve_date TEXT NOT NULL,
    source_file TEXT NOT NULL,
    PRIMARY KEY (snapshot, mgmt_pk)
);
CREATE INDEX ix_building_pnu ON building_observation (pnu);
CREATE TABLE transaction_enrichment (
    domain TEXT NOT NULL,
    transaction_key TEXT NOT NULL,
    status TEXT NOT NULL,
    pnu TEXT,
    trait_asof TEXT,
    building_snapshot TEXT,
    note TEXT,
    PRIMARY KEY (domain, transaction_key)
);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def create(db: sqlite3.Connection) -> None:
    db.executescript(DDL)
    db.execute(
        "INSERT INTO ledger_meta(key, value) VALUES (?, ?)",
        ("schema_version", SCHEMA_VERSION),
    )
    db.execute(
        "INSERT INTO ledger_meta(key, value) VALUES (?, ?)",
        ("identity_rule", VERSION),
    )


def _cell(row: dict, name: str) -> str:
    return str(row.get(name) or "").strip()


def parcel_hold(pnu: str) -> str | None:
    """특성 파일의 19자리 필지번호. 산(구분 2)은 유효하다. 본번 0000만 제외한다."""
    if not re.fullmatch(r"\d{19}", pnu):
        return "invalid_pnu"
    if pnu[10] not in "12":
        return "invalid_land_type"
    if pnu[11:15] == "0000":
        return "noncanonical_zero_main_lot"
    return None


def parse_asof(value: str) -> str:
    day = value.strip()[:10]
    date.fromisoformat(day)
    return day


def _trait_values(raw: dict, asof: str) -> tuple[str, ...]:
    return (
        asof,
        _cell(raw, "year"),
        _cell(raw, "month"),
        _cell(raw, "jimok_code"),
        _cell(raw, "jimok_label"),
        _cell(raw, "area"),
        _cell(raw, "zone1_code"),
        _cell(raw, "zone1_label"),
        _cell(raw, "zone2_code"),
        _cell(raw, "zone2_label"),
        _cell(raw, "use_code"),
        _cell(raw, "use_label"),
        _cell(raw, "height_code"),
        _cell(raw, "height_label"),
        _cell(raw, "shape_code"),
        _cell(raw, "shape_label"),
        _cell(raw, "road_code"),
        _cell(raw, "road_label"),
        _cell(raw, "price"),
    )


def ingest_trait_rows(db: sqlite3.Connection, vintage_year: int, rows, source_file: str) -> dict:
    kept: dict[str, tuple[str, ...]] = {}
    collapsed = 0
    held: dict[str, int] = {}
    rows_in = 0
    for raw in rows:
        rows_in += 1
        pnu = _cell(raw, "pnu")
        reason = parcel_hold(pnu)
        if reason:
            held[reason] = held.get(reason, 0) + 1
            continue
        try:
            asof = parse_asof(_cell(raw, "trait_asof"))
        except ValueError:
            held["bad_asof"] = held.get("bad_asof", 0) + 1
            continue
        key = _trait_values(raw, asof)
        previous = kept.get(pnu)
        if previous is None:
            kept[pnu] = key
        elif previous == key:
            collapsed += 1
        else:
            raise ValueError(f"Conflicting trait rows for {pnu} in {vintage_year}")
    db.executemany(
        """INSERT INTO parcel_observation (
            vintage_year, pnu, asof, price_year, price_month,
            jimok_code, jimok_label, area, zone1_code, zone1_label,
            zone2_code, zone2_label, use_code, use_label, height_code, height_label,
            shape_code, shape_label, road_code, road_label, price, source_file
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [(vintage_year, pnu, *key, source_file) for pnu, key in kept.items()],
    )
    return {
        "rows_in": rows_in,
        "stored": len(kept),
        "collapsed_identical": collapsed,
        "held": held,
    }


def building_record(raw: dict, snapshot: str, source_file: str) -> dict | None:
    sigungu = _cell(raw, "sigungu_code")
    if sigungu not in DISTRICTS:
        return None
    ident = identify(
        [
            sigungu,
            _cell(raw, "bjd_code"),
            _cell(raw, "plat_gb"),
            _cell(raw, "bun"),
            _cell(raw, "ji"),
        ]
    )
    pk = _cell(raw, "pk") or _cell(raw, "mgmt_pk")
    if not pk:
        raise ValueError("Building row has no management PK")
    canonical = ident["status"] == "canonical_address"
    return {
        "snapshot": snapshot,
        "mgmt_pk": pk,
        "ledger_kind": _cell(raw, "ledger_kind"),
        "pnu": ident["pnu"] if canonical else None,
        "hold_reason": None if canonical else ident["status"],
        "structure_name": _cell(raw, "struct_name") or _cell(raw, "structure_name"),
        "floors_above": _cell(raw, "floors_above"),
        "floors_below": _cell(raw, "floors_below"),
        "gross_area": _cell(raw, "gross_area"),
        "plat_area": _cell(raw, "plat_area"),
        "approve_date": _cell(raw, "approve_date"),
        "source_file": source_file,
    }


def ingest_building_rows(db: sqlite3.Connection, snapshot: str, rows, source_file: str) -> dict:
    kept: dict[str, dict] = {}
    collapsed = 0
    held: dict[str, int] = {}
    rows_in = 0
    for raw in rows:
        rec = building_record(raw, snapshot, source_file)
        if rec is None:
            continue
        rows_in += 1
        if rec["hold_reason"]:
            held[rec["hold_reason"]] = held.get(rec["hold_reason"], 0) + 1
        previous = kept.get(rec["mgmt_pk"])
        if previous is None:
            kept[rec["mgmt_pk"]] = rec
        elif previous == rec:
            collapsed += 1
        else:
            raise ValueError(f"Conflicting building {rec['mgmt_pk']} in {snapshot}")
    db.executemany(
        """INSERT INTO building_observation (
            snapshot, mgmt_pk, ledger_kind, pnu, hold_reason, structure_name,
            floors_above, floors_below, gross_area, plat_area, approve_date, source_file
        ) VALUES (:snapshot,:mgmt_pk,:ledger_kind,:pnu,:hold_reason,:structure_name,
                  :floors_above,:floors_below,:gross_area,:plat_area,:approve_date,:source_file)""",
        list(kept.values()),
    )
    return {
        "rows_in": rows_in,
        "stored": len(kept),
        "with_pnu": sum(1 for rec in kept.values() if rec["pnu"]),
        "collapsed_identical": collapsed,
        "held": held,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_trait_gzip(db: sqlite3.Connection, path: Path, vintage_year: int) -> dict:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = [name for name in ("pnu", "trait_asof", *TRAIT_BODY) if name not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path.name} missing columns {missing}")
        stats = ingest_trait_rows(db, vintage_year, reader, path.name)
    stats["sha256"] = _sha256(path)
    stats["bytes"] = path.stat().st_size
    return stats


def iter_title_rows(path: Path):
    with path.open(encoding="utf-8", newline="") as stream:
        yield from csv.DictReader(stream)


def load_title_csv(db: sqlite3.Connection, path: Path, snapshot: str) -> dict:
    stats = ingest_building_rows(db, snapshot, iter_title_rows(path), path.name)
    stats["sha256"] = _sha256(path)
    stats["bytes"] = path.stat().st_size
    return stats


def summarize(db: sqlite3.Connection) -> dict:
    traits = []
    for row in db.execute(
        """SELECT vintage_year, COUNT(*) n, COUNT(DISTINCT asof) asofs,
                  MIN(asof) min_asof, MAX(asof) max_asof,
                  SUM(CASE WHEN zone1_code != '' AND zone1_label = '' THEN 1 ELSE 0 END) code_without_zone_label
           FROM parcel_observation GROUP BY vintage_year ORDER BY vintage_year"""
    ):
        traits.append({key: row[key] for key in row.keys()})
    buildings = []
    for row in db.execute(
        """SELECT snapshot, ledger_kind, COUNT(*) n,
                  SUM(CASE WHEN pnu IS NULL THEN 1 ELSE 0 END) held,
                  COUNT(DISTINCT pnu) parcels
           FROM building_observation GROUP BY snapshot, ledger_kind ORDER BY snapshot, ledger_kind"""
    ):
        buildings.append({key: row[key] for key in row.keys()})
    multi = db.execute(
        """SELECT COUNT(*) FROM (
               SELECT pnu FROM building_observation
               WHERE snapshot = '2026-07' AND pnu IS NOT NULL
               GROUP BY pnu HAVING COUNT(DISTINCT mgmt_pk) > 1
           )"""
    ).fetchone()[0]
    overlap = db.execute(
        """SELECT COUNT(DISTINCT b.pnu) FROM building_observation b
           JOIN parcel_observation p ON p.pnu = b.pnu AND p.vintage_year = 2026
           WHERE b.snapshot = '2026-07' AND b.pnu IS NOT NULL"""
    ).fetchone()[0]
    linked_buildings = db.execute(
        """SELECT COUNT(*) FROM building_observation
           WHERE snapshot = '2026-07' AND pnu IS NOT NULL"""
    ).fetchone()[0]
    zero_bun = db.execute(
        "SELECT COUNT(*) FROM parcel_observation WHERE substr(pnu, 12, 4) = '0000'"
    ).fetchone()[0]
    return {
        "traits": traits,
        "buildings": buildings,
        "multi_building_parcels_2026_07": multi,
        "building_pnu_2026_07": linked_buildings,
        "building_pnu_also_in_2026_traits": overlap,
        "zero_main_lot_parcels": zero_bun,
        "enrichment_rows": db.execute("SELECT COUNT(*) FROM transaction_enrichment").fetchone()[0],
    }


def load_cheongju(db_path: Path = DB_PATH) -> dict:
    if db_path.exists():
        db_path.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    db = connect(db_path)
    create(db)
    report = {
        "schema_version": SCHEMA_VERSION,
        "identity_rule": VERSION,
        "database": str(db_path.relative_to(ROOT)).replace("\\", "/"),
        "traits": {},
        "buildings": {},
    }
    try:
        for year in range(2019, 2027):
            path = OUT / f"traits_{year}.csv.gz"
            print(f"traits {year}", flush=True)
            stats = load_trait_gzip(db, path, year)
            db.commit()
            report["traits"][str(year)] = stats
            print(f"  stored {stats['stored']} collapsed {stats['collapsed_identical']}", flush=True)
        if report["traits"]["2019"]["collapsed_identical"] != 15:
            raise ValueError("2019 identical duplicate rows were not the known 15")
        for snapshot in BUILDING_SNAPSHOTS:
            report["buildings"][snapshot] = {}
            for kind, pattern in TITLE_FILES:
                path = CACHE / pattern.format(snapshot=snapshot)
                print(f"title {kind} {snapshot}", flush=True)
                stats = load_title_csv(db, path, snapshot)
                db.commit()
                report["buildings"][snapshot][kind] = stats
                print(f"  stored {stats['stored']} with_pnu {stats['with_pnu']}", flush=True)
        report["checks"] = summarize(db)
        if report["checks"]["zero_main_lot_parcels"] != 0:
            raise ValueError("본번 0000 parcel was stored")
        report["run_date"] = date.today().isoformat()
    finally:
        db.close()
    LAB.mkdir(parents=True, exist_ok=True)
    (LAB / "cheongju_attribute_ledger_v1.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> None:
    report = load_cheongju()
    print(json.dumps(report["checks"], ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
