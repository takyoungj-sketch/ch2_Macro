"""Measure one national land-trait plate. Does not load the full history.

Cheongju 2026 slim sqlite is about 92MB for 480,633 parcels. Storing every
national source row at that density is hundreds of gigabytes, past the
10-20GB planning band. This loader stores only as-of 2026-05-12 so the
national byte density can be measured, then stops.
"""
from __future__ import annotations

import json
import sqlite3
import zipfile
from datetime import date
from pathlib import Path

from parcel_master.attribute_ledger import parcel_hold

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "raw" / "raw addition" / "토지특성정보CSV(브이월드)"
INVENTORY = ROOT / "docs" / "lab" / "land_characteristic_csv_internal_dates_20261010.json"
OUT_DIR = ROOT / "data" / "research" / "land_trait_slim"
DB_PATH = OUT_DIR / "gauge_asof_2026-05-12.sqlite"
REPORT = ROOT / "docs" / "lab" / "land_trait_slim_gauge_20261010.json"
TARGET_ASOF = "2026-05-12"
CHEONGJU_2026_ROWS = 480_633
CHEONGJU_2026_BYTES = 96_489_472

ALIASES = {
    "pnu": ("고유번호",),
    "year": ("기준연도", "기준년도"),
    "month": ("기준월",),
    "jimok_code": ("지목코드",),
    "jimok_label": ("지목명",),
    "area": ("토지면적",),
    "zone1_code": ("용도지역코드1",),
    "zone1_label": ("용도지역명1",),
    "zone2_code": ("용도지역코드2",),
    "zone2_label": ("용도지역명2",),
    "use_code": ("토지이용상황코드",),
    "use_label": ("토지이용상황", "토지이동상황"),
    "height_code": ("지형높이코드",),
    "height_label": ("지형높이",),
    "shape_code": ("지형형상코드",),
    "shape_label": ("지형형상",),
    "road_code": ("도로접면코드",),
    "road_label": ("도로접면",),
    "price": ("공시지가",),
    "asof": ("데이터기준일자",),
}

DDL = """
CREATE TABLE parcel_observation (
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
    PRIMARY KEY (pnu, asof)
);
"""


def column_indexes(header: list[str]) -> dict[str, int]:
    indexes = {}
    for key, names in ALIASES.items():
        found = next((header.index(name) for name in names if name in header), None)
        if found is None:
            raise ValueError(f"missing column for {key}")
        indexes[key] = found
    return indexes


def parse_row(parts: list[str], indexes: dict[str, int]) -> tuple[str, ...] | None:
    asof = parts[indexes["asof"]].strip()[:10]
    if asof != TARGET_ASOF:
        return None
    return tuple(parts[indexes[key]].strip() for key in (
        "pnu",
        "asof",
        "year",
        "month",
        "jimok_code",
        "jimok_label",
        "area",
        "zone1_code",
        "zone1_label",
        "zone2_code",
        "zone2_label",
        "use_code",
        "use_label",
        "height_code",
        "height_label",
        "shape_code",
        "shape_label",
        "road_code",
        "road_label",
        "price",
    ))


def source_files() -> list[str]:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    names = []
    for item in inventory["files"]:
        dates = item.get("internal_dates") or {}
        if TARGET_ASOF in dates:
            names.append(item["file"])
    return sorted(names)


def projected_bytes(rows: int) -> int:
    return rows * CHEONGJU_2026_BYTES // CHEONGJU_2026_ROWS


def load(db_path: Path = DB_PATH) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    db = sqlite3.connect(db_path)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.executescript(DDL)
    stats = {
        "asof": TARGET_ASOF,
        "rows_in": 0,
        "stored": 0,
        "skipped_other_asof": 0,
        "collapsed_identical": 0,
        "held": {},
        "files": [],
    }
    insert_sql = """INSERT INTO parcel_observation (
        pnu, asof, price_year, price_month, jimok_code, jimok_label, area,
        zone1_code, zone1_label, zone2_code, zone2_label, use_code, use_label,
        height_code, height_label, shape_code, shape_label, road_code, road_label,
        price, source_file
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    try:
        for name in source_files():
            path = SRC / name
            file_rows = 0
            with zipfile.ZipFile(path) as zf:
                csv_names = [item for item in zf.namelist() if item.lower().endswith(".csv")]
                if len(csv_names) != 1:
                    raise ValueError(f"{name} csv entries {len(csv_names)}")
                with zf.open(csv_names[0]) as handle:
                    header = handle.readline().decode("cp949").strip().split(",")
                    indexes = column_indexes(header)
                    width = len(header)
                    batch = []
                    for line in handle:
                        parts = line.decode("cp949").rstrip("\r\n").split(",")
                        if len(parts) != width:
                            raise ValueError(f"{name} field width {len(parts)} != {width}")
                        parsed = parse_row(parts, indexes)
                        if parsed is None:
                            stats["skipped_other_asof"] += 1
                            continue
                        file_rows += 1
                        reason = parcel_hold(parsed[0])
                        if reason:
                            stats["held"][reason] = stats["held"].get(reason, 0) + 1
                            continue
                        batch.append((*parsed, name))
                        if len(batch) >= 20000:
                            _insert_batch(db, insert_sql, batch, stats)
                            batch.clear()
                    if batch:
                        _insert_batch(db, insert_sql, batch, stats)
            stats["rows_in"] += file_rows
            stats["files"].append({"file": name, "rows": file_rows})
            print(f"{name} rows={file_rows} stored={stats['stored']}", flush=True)
        db.commit()
        db.execute("VACUUM")
    finally:
        db.close()
    size = db_path.stat().st_size
    raw_rows = json.loads(INVENTORY.read_text(encoding="utf-8"))["row_count"]
    report = {
        "run_date": date.today().isoformat(),
        "database": str(db_path.relative_to(ROOT)).replace("\\", "/"),
        "cheongju_2026_rows": CHEONGJU_2026_ROWS,
        "cheongju_2026_sqlite_bytes": CHEONGJU_2026_BYTES,
        "target_asof": TARGET_ASOF,
        "stats": stats,
        "sqlite_bytes": size,
        "bytes_per_stored_row": round(size / stats["stored"], 2) if stats["stored"] else None,
        "projected_sqlite_bytes_if_all_source_rows": projected_bytes(raw_rows),
        "planning_band_bytes": [10 * 1024**3, 20 * 1024**3],
        "stopped": True,
        "stop_reason": "all source rows at the measured density exceed the 10-20GB band",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {REPORT} bytes={size} stored={stats['stored']}", flush=True)
    return report


def _insert_batch(db: sqlite3.Connection, sql: str, batch: list[tuple], stats: dict) -> None:
    try:
        db.executemany(sql, batch)
        stats["stored"] += len(batch)
    except sqlite3.IntegrityError:
        db.rollback()
        for row in batch:
            _insert_one(db, sql, row, stats)
        db.commit()
    else:
        db.commit()


def _insert_one(db: sqlite3.Connection, sql: str, row: tuple, stats: dict) -> None:
    try:
        db.execute(sql, row)
        stats["stored"] += 1
    except sqlite3.IntegrityError:
        existing = db.execute(
            "SELECT * FROM parcel_observation WHERE pnu = ? AND asof = ?",
            (row[0], row[1]),
        ).fetchone()
        if tuple(existing[:-1]) == tuple(row[:-1]):
            stats["collapsed_identical"] += 1
            return
        raise ValueError(f"Conflicting trait rows for {row[0]} at {row[1]}") from None


if __name__ == "__main__":
    load()
