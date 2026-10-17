"""National land-trait ledger.

One row is one parcel, one 데이터기준일자, and one 기준연도·기준월.
A file often repeats the same data date for several official-price years.
Those years stay as separate observations. Identical repeats collapse.
The same parcel, date, year, and month with different attributes is left
out of the ledger and stored in observation_conflict.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import struct
import time
import zipfile
from datetime import date
from pathlib import Path

import numpy as np

from parcel_master.attribute_ledger import parcel_hold
from parcel_master.slim_national_gauge import ALIASES, column_indexes

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "raw" / "raw addition" / "토지특성정보CSV(브이월드)"
SSD_ROOT = Path(r"C:\CH2\parcel_master")
DB_PATH = SSD_ROOT / "land_trait_observations.sqlite"
WORK_DIR = SSD_ROOT / "work"
REPORT = ROOT / "docs" / "lab" / "land_trait_national_slim_20261010.json"

SHARD_COUNT = 64
GRAIN = "pnu x asof x price_year x price_month"
RECORD = struct.Struct("<QIHB16s")
RECORD_DTYPE = np.dtype(
    [
        ("pnu", "<u8"),
        ("asof", "<u4"),
        ("year", "<u2"),
        ("month", "<u1"),
        ("hx", "<u8"),
        ("hy", "<u8"),
    ],
    align=False,
)
KEY_DTYPE = np.dtype(
    [("pnu", "<u8"), ("year", "<u2"), ("month", "<u1")],
    align=False,
)
VALUE_KEYS = (
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
)

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
    PRIMARY KEY (pnu, asof, price_year, price_month)
) WITHOUT ROWID;

CREATE TABLE observation_conflict (
    pnu TEXT NOT NULL,
    asof TEXT NOT NULL,
    attr_hash TEXT NOT NULL,
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
    PRIMARY KEY (pnu, asof, price_year, price_month, attr_hash)
) WITHOUT ROWID;
"""

INSERT_CLEAN = """INSERT INTO parcel_observation (
    pnu, asof, price_year, price_month, jimok_code, jimok_label, area,
    zone1_code, zone1_label, zone2_code, zone2_label, use_code, use_label,
    height_code, height_label, shape_code, shape_label, road_code, road_label,
    price, source_file
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""

INSERT_CLEAN_IGNORE = INSERT_CLEAN.replace("INSERT INTO", "INSERT OR IGNORE INTO", 1)

INSERT_CONFLICT = """INSERT OR IGNORE INTO observation_conflict (
    pnu, asof, attr_hash, price_year, price_month, jimok_code, jimok_label, area,
    zone1_code, zone1_label, zone2_code, zone2_label, use_code, use_label,
    height_code, height_label, shape_code, shape_label, road_code, road_label,
    price, source_file
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""


def asof_ordinal(value: str) -> int | None:
    day = value.strip()[:10]
    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        return None
    return parsed.year * 10000 + parsed.month * 100 + parsed.day


def ordinal_text(value: int) -> str:
    return f"{value // 10000:04d}-{(value // 100) % 100:02d}-{value % 100:02d}"


def attribute_hash(attrs: tuple[str, ...]) -> bytes:
    return hashlib.blake2s("\x1f".join(attrs).encode("utf-8"), digest_size=16).digest()


def classify_records(arr: np.ndarray) -> dict:
    """Split one shard into clean keys, conflict keys, and the duplicate count."""
    empty: dict[int, np.ndarray] = {}
    if arr.size == 0:
        return {
            "rows": 0,
            "identical": 0,
            "clean": empty,
            "conflict": empty,
            "clean_keys": 0,
            "conflict_keys": 0,
            "conflict_variants": 0,
        }
    if arr.size > 1:
        arr.sort(order=["pnu", "asof", "year", "month", "hx", "hy"])
    n = int(arr.size)
    change = np.empty(n, dtype=np.bool_)
    change[0] = True
    if n > 1:
        change[1:] = (
            (arr["pnu"][1:] != arr["pnu"][:-1])
            | (arr["asof"][1:] != arr["asof"][:-1])
            | (arr["year"][1:] != arr["year"][:-1])
            | (arr["month"][1:] != arr["month"][:-1])
        )
    hchange = np.empty(n, dtype=np.bool_)
    hchange[0] = True
    if n > 1:
        hchange[1:] = (
            change[1:]
            | (arr["hx"][1:] != arr["hx"][:-1])
            | (arr["hy"][1:] != arr["hy"][:-1])
        )
    key_idx = np.flatnonzero(change)
    hash_idx = np.flatnonzero(hchange)
    key_of_hash = np.searchsorted(key_idx, hash_idx, side="right") - 1
    hashes_per_key = np.bincount(key_of_hash, minlength=int(key_idx.size))
    clean_at = hashes_per_key == 1
    conflict_at = hashes_per_key > 1
    return {
        "rows": n,
        "identical": n - int(hash_idx.size),
        "clean": _group_keys(arr, key_idx[clean_at]),
        "conflict": _group_keys(arr, key_idx[conflict_at]),
        "clean_keys": int(clean_at.sum()),
        "conflict_keys": int(conflict_at.sum()),
        "conflict_variants": int(hashes_per_key[conflict_at].sum()),
    }


def _group_keys(arr: np.ndarray, key_idx: np.ndarray) -> dict[int, np.ndarray]:
    grouped: dict[int, np.ndarray] = {}
    if key_idx.size == 0:
        return grouped
    asofs = arr["asof"][key_idx]
    packed = np.empty(key_idx.size, dtype=KEY_DTYPE)
    packed["pnu"] = arr["pnu"][key_idx]
    packed["year"] = arr["year"][key_idx]
    packed["month"] = arr["month"][key_idx]
    for asof in np.unique(asofs):
        chunk = packed[asofs == asof]
        order = np.lexsort((chunk["month"], chunk["year"], chunk["pnu"]))
        grouped[int(asof)] = chunk[order]
    return grouped


def merge_key_lists(parts: list[dict[int, np.ndarray]]) -> dict[int, np.ndarray]:
    merged: dict[int, list[np.ndarray]] = {}
    for part in parts:
        for asof, pnus in part.items():
            merged.setdefault(asof, []).append(pnus)
    out: dict[int, np.ndarray] = {}
    for asof, chunks in merged.items():
        stacked = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
        unique = np.unique(stacked)
        if unique.size != stacked.size:
            raise ValueError(f"shard overlap on {asof}")
        out[asof] = unique
    return out


def count_unique_pnu(by_asof: dict[int, np.ndarray]) -> int:
    acc: np.ndarray | None = None
    for keys in by_asof.values():
        pnus = np.unique(keys["pnu"])
        acc = pnus if acc is None else np.unique(np.concatenate((acc, pnus)))
    return 0 if acc is None else int(acc.size)


class ShardWriter:
    def __init__(self, directory: Path, shard_count: int) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.handles = [
            (directory / f"{i:03d}.bin").open("wb") for i in range(shard_count)
        ]
        self.buffers = [bytearray() for _ in range(shard_count)]
        self.shard_count = shard_count

    def add(self, pnu: int, asof: int, year: int, month: int, digest: bytes) -> None:
        shard = pnu % self.shard_count
        self.buffers[shard] += RECORD.pack(pnu, asof, year, month, digest)
        if len(self.buffers[shard]) >= 8 * 1024 * 1024:
            self._flush(shard)

    def close(self) -> None:
        for shard in range(self.shard_count):
            self._flush(shard)
            self.handles[shard].close()

    def _flush(self, shard: int) -> None:
        if self.buffers[shard]:
            self.handles[shard].write(self.buffers[shard])
            self.buffers[shard].clear()


def _zip_rows(path: Path):
    with zipfile.ZipFile(path) as archive:
        names = [item for item in archive.namelist() if item.lower().endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"{path.name} csv entries {len(names)}")
        with archive.open(names[0]) as handle:
            header = handle.readline().decode("cp949").strip().split(",")
            if "데이터기준일자" not in header:
                raise ValueError(f"{path.name} missing 데이터기준일자")
            indexes = column_indexes(header)
            width = len(header)
            for line in handle:
                parts = line.decode("cp949").rstrip("\r\n").split(",")
                if len(parts) != width:
                    raise ValueError(f"{path.name} field width {len(parts)} != {width}")
                yield parts, indexes


def price_year_month(year: str, month: str) -> tuple[int, int, str, str] | str:
    year_text = year.strip()
    month_text = month.strip()
    if len(year_text) != 4 or not year_text.isdigit():
        return "bad_price_year"
    if not month_text.isdigit():
        return "bad_price_month"
    month_number = int(month_text)
    if not 1 <= month_number <= 12:
        return "bad_price_month"
    return int(year_text), month_number, year_text, f"{month_number:02d}"


def _parsed(parts: list[str], indexes: dict[str, int]):
    pnu = parts[indexes["pnu"]].strip()
    reason = parcel_hold(pnu)
    if reason:
        return reason
    ordinal = asof_ordinal(parts[indexes["asof"]])
    if ordinal is None:
        return "bad_asof"
    priced = price_year_month(parts[indexes["year"]], parts[indexes["month"]])
    if isinstance(priced, str):
        return priced
    year_i, month_i, year_text, month_text = priced
    attrs = tuple(parts[indexes[key]].strip() for key in VALUE_KEYS)
    return pnu, ordinal, year_i, month_i, year_text, month_text, attrs


def scan_keys(src: Path, work_dir: Path, shard_count: int) -> dict:
    shard_dir = work_dir / "shards"
    if shard_dir.exists():
        for child in shard_dir.glob("*"):
            child.unlink()
    writer = ShardWriter(shard_dir, shard_count)
    held: dict[str, int] = {}
    rows_in = 0
    files = sorted(path.name for path in src.glob("*.zip"))
    try:
        for name in files:
            file_rows = 0
            for parts, indexes in _zip_rows(src / name):
                parsed = _parsed(parts, indexes)
                if isinstance(parsed, str):
                    held[parsed] = held.get(parsed, 0) + 1
                    continue
                pnu, ordinal, year_i, month_i, _year_text, _month_text, attrs = parsed
                writer.add(int(pnu), ordinal, year_i, month_i, attribute_hash(attrs))
                file_rows += 1
                rows_in += 1
                if file_rows % 5_000_000 == 0:
                    print(f"keys {name} rows={file_rows} total={rows_in}", flush=True)
            print(f"keys {name} rows={file_rows} total={rows_in}", flush=True)
    finally:
        writer.close()
    return {"rows_in": rows_in, "held": held, "files": len(files)}


def classify_shards(work_dir: Path, shard_count: int) -> dict:
    clean_parts: list[dict[int, np.ndarray]] = []
    conflict_parts: list[dict[int, np.ndarray]] = []
    totals = {
        "rows": 0,
        "identical": 0,
        "clean_keys": 0,
        "conflict_keys": 0,
        "conflict_variants": 0,
    }
    for shard in range(shard_count):
        path = work_dir / "shards" / f"{shard:03d}.bin"
        if not path.exists() or path.stat().st_size == 0:
            continue
        if path.stat().st_size % RECORD.size != 0:
            raise ValueError(f"{path.name} truncated")
        arr = np.fromfile(path, dtype=RECORD_DTYPE)
        classified = classify_records(arr)
        totals["rows"] += classified["rows"]
        totals["identical"] += classified["identical"]
        totals["clean_keys"] += classified["clean_keys"]
        totals["conflict_keys"] += classified["conflict_keys"]
        totals["conflict_variants"] += classified["conflict_variants"]
        clean_parts.append(classified["clean"])
        conflict_parts.append(classified["conflict"])
        print(
            f"classified shard {shard} rows={classified['rows']} "
            f"clean={classified['clean_keys']} conflict={classified['conflict_keys']}",
            flush=True,
        )
    clean = merge_key_lists(clean_parts)
    conflict = merge_key_lists(conflict_parts)
    totals["unique_pnu"] = count_unique_pnu(clean)
    totals["asofs"] = sorted(ordinal_text(asof) for asof in clean)
    return {"clean": clean, "conflict": conflict, "totals": totals}


def _save_keys(directory: Path, by_asof: dict[int, np.ndarray]) -> None:
    if directory.exists():
        for child in directory.glob("*.npy"):
            child.unlink()
    directory.mkdir(parents=True, exist_ok=True)
    for asof, pnus in by_asof.items():
        np.save(directory / f"{asof}.npy", pnus)


def _load_keys(directory: Path) -> dict[int, np.ndarray]:
    loaded = {}
    for path in sorted(directory.glob("*.npy")):
        loaded[int(path.stem)] = np.load(path)
    return loaded


_LOAD_LINE = re.compile(r"^load (\S+) rows=(\d+) stored=(\d+)$")


def _parse_load_log(path: Path) -> list[tuple[str, int, int]]:
    if not path.exists():
        return []
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw.decode("utf-16")
    else:
        text = raw.decode("utf-8")
    parsed: list[tuple[str, int, int]] = []
    for line in text.splitlines():
        match = _LOAD_LINE.match(line.strip())
        if match:
            parsed.append((match.group(1), int(match.group(2)), int(match.group(3))))
    return parsed


def _write_loaded(path: Path, files: list[str], stored: int) -> None:
    path.write_text(
        json.dumps({"files": files, "stored": stored}, ensure_ascii=False),
        encoding="utf-8",
    )


def _completed_from_bootstrap(log_path: Path, zip_names: list[str]) -> tuple[list[str], int]:
    """Files finished before the reboot. The last line counts only when it is a file end."""
    entries = _parse_load_log(log_path)
    if not entries:
        raise RuntimeError(f"resume log has no load lines: {log_path}")
    order: list[str] = []
    last: dict[str, tuple[int, int]] = {}
    for name, rows, stored in entries:
        if name not in last:
            order.append(name)
        last[name] = (rows, stored)
    done = list(order)
    final_rows, _final_stored = last[order[-1]]
    if final_rows % 5_000_000 == 0:
        done.pop()
    if done != zip_names[: len(done)]:
        raise RuntimeError("resume log is not a prefix of the zip files")
    stored = last[done[-1]][1] if done else 0
    return done, stored


def resume_plan(
    src: Path,
    progress_dir: Path,
    bootstrap_log: Path,
) -> tuple[list[str], int]:
    """Completed zip names and the stored count to carry into the next write."""
    files = sorted(path.name for path in src.glob("*.zip"))
    state_path = progress_dir / "loaded_files.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        done = list(state["files"])
        stored = int(state["stored"])
        if done != files[: len(done)]:
            raise RuntimeError("loaded_files.json is not a prefix of the zip files")
        return done, stored
    done, stored = _completed_from_bootstrap(bootstrap_log, files)
    progress_dir.mkdir(parents=True, exist_ok=True)
    _write_loaded(state_path, done, stored)
    return done, stored


def _flush_clean(
    db: sqlite3.Connection,
    batch: list[tuple],
    keys: np.ndarray,
    seen: np.ndarray,
    stats: dict,
    insert_sql: str = INSERT_CLEAN,
) -> None:
    if not batch:
        return
    pnus = np.fromiter((int(row[0]) for row in batch), dtype=np.uint64, count=len(batch))
    years = np.fromiter((int(row[2]) for row in batch), dtype=np.uint16, count=len(batch))
    months = np.fromiter((int(row[3]) for row in batch), dtype=np.uint8, count=len(batch))
    located = _locate(keys, pnus, years, months)
    positions = np.flatnonzero(located >= 0)
    if positions.size == 0:
        return
    key_index = located[positions]
    already = seen[key_index]
    new_positions = positions[~already]
    new_keys = key_index[~already]
    chosen: list[int] = []
    if new_keys.size:
        order = np.argsort(new_keys, kind="mergesort")
        sorted_keys = new_keys[order]
        keep = np.empty(sorted_keys.size, dtype=np.bool_)
        keep[0] = True
        if sorted_keys.size > 1:
            keep[1:] = sorted_keys[1:] != sorted_keys[:-1]
        picked = order[keep]
        seen[sorted_keys[keep]] = True
        chosen = new_positions[picked].tolist()
    stats["collapsed_identical"] += int(positions.size - len(chosen))
    if chosen:
        db.executemany(insert_sql, [batch[pos] for pos in chosen])
        stats["stored"] += len(chosen)


def _locate(keys: np.ndarray, pnus: np.ndarray, years: np.ndarray, months: np.ndarray) -> np.ndarray:
    found = np.full(pnus.size, -1, dtype=np.int64)
    if keys.size == 0 or pnus.size == 0:
        return found
    left = np.searchsorted(keys["pnu"], pnus, side="left")
    right = np.searchsorted(keys["pnu"], pnus, side="right")
    span = right - left
    for offset in range(8):
        selected = (span > offset) & (found < 0)
        if not np.any(selected):
            break
        pos = left[selected] + offset
        matched = (keys["year"][pos] == years[selected]) & (keys["month"][pos] == months[selected])
        found[np.flatnonzero(selected)[matched]] = pos[matched]
    for index in np.flatnonzero((span > 8) & (found < 0)):
        start = int(left[index])
        stop = int(right[index])
        sl = keys[start:stop]
        hit = np.flatnonzero((sl["year"] == years[index]) & (sl["month"] == months[index]))
        if hit.size:
            found[index] = start + int(hit[0])
    return found


def load_observations(
    src: Path,
    db_path: Path,
    clean: dict[int, np.ndarray],
    conflict: dict[int, np.ndarray],
    progress_dir: Path | None = None,
    completed: list[str] | None = None,
    base_stored: int = 0,
) -> dict:
    resume = completed is not None
    if resume:
        insert_sql = INSERT_CLEAN_IGNORE
        skip = set(completed)
        done_files = list(completed)
    else:
        insert_sql = INSERT_CLEAN
        skip = set()
        done_files = []
        if db_path.exists():
            db_path.unlink()
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(db_path) + suffix)
            if sidecar.exists():
                sidecar.unlink()
        if progress_dir is not None:
            loaded_path = progress_dir / "loaded_files.json"
            if loaded_path.exists():
                loaded_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("PRAGMA cache_size=-262144")
    if not resume:
        db.executescript(DDL)
    seen = {asof: np.zeros(pnus.size, dtype=np.bool_) for asof, pnus in clean.items()}
    stats = {"stored": base_stored if resume else 0, "collapsed_identical": 0}
    try:
        for name in sorted(path.name for path in src.glob("*.zip")):
            if name in skip:
                continue
            batch: list[tuple] = []
            file_rows = 0
            for parts, indexes in _zip_rows(src / name):
                parsed = _parsed(parts, indexes)
                if isinstance(parsed, str):
                    continue
                batch.append(parsed)
                file_rows += 1
                if len(batch) >= 20000:
                    _flush_rows(db, batch, name, clean, conflict, seen, stats, insert_sql)
                    batch.clear()
                    db.commit()
                if file_rows % 5_000_000 == 0:
                    print(f"load {name} rows={file_rows} stored={stats['stored']}", flush=True)
            if batch:
                _flush_rows(db, batch, name, clean, conflict, seen, stats, insert_sql)
            db.commit()
            done_files.append(name)
            if progress_dir is not None:
                _write_loaded(progress_dir / "loaded_files.json", done_files, stats["stored"])
            print(f"load {name} rows={file_rows} stored={stats['stored']}", flush=True)
        if not resume:
            missing = sum(int((~flags).sum()) for flags in seen.values())
            if missing:
                raise RuntimeError(f"clean observations missing from source: {missing}")
        else:
            expected = sum(int(flags.size) for flags in seen.values())
            found = db.execute("SELECT COUNT(*) FROM parcel_observation").fetchone()[0]
            if found != expected:
                raise RuntimeError(
                    f"clean observations missing from database: found={found} expected={expected}"
                )
        db.commit()
        db.execute("VACUUM")
        stats["conflict_stored"] = db.execute(
            "SELECT COUNT(*) FROM observation_conflict"
        ).fetchone()[0]
        stats["stored"] = db.execute("SELECT COUNT(*) FROM parcel_observation").fetchone()[0]
    finally:
        db.close()
    return stats


def _flush_rows(db, batch, name, clean, conflict, seen, stats, insert_sql=INSERT_CLEAN) -> None:
    grouped: dict[int, list[tuple]] = {}
    for pnu, ordinal, _year_i, _month_i, year_text, month_text, attrs in batch:
        grouped.setdefault(ordinal, []).append((pnu, year_text, month_text, attrs))
    for ordinal, rows in grouped.items():
        asof = ordinal_text(ordinal)
        pnus = np.fromiter((int(row[0]) for row in rows), dtype=np.uint64, count=len(rows))
        years = np.fromiter((int(row[1]) for row in rows), dtype=np.uint16, count=len(rows))
        months = np.fromiter((int(row[2]) for row in rows), dtype=np.uint8, count=len(rows))
        if ordinal in clean:
            _flush_clean(
                db,
                [
                    (pnu, asof, year_text, month_text, *attrs, name)
                    for pnu, year_text, month_text, attrs in rows
                ],
                clean[ordinal],
                seen[ordinal],
                stats,
                insert_sql,
            )
        if ordinal in conflict:
            located = _locate(conflict[ordinal], pnus, years, months)
            queued = [
                (pnu, asof, attribute_hash(attrs).hex(), year_text, month_text, *attrs, name)
                for (pnu, year_text, month_text, attrs), key_index in zip(rows, located)
                if key_index >= 0
            ]
            if queued:
                db.executemany(INSERT_CONFLICT, queued)


def load(
    src: Path = SRC,
    db_path: Path = DB_PATH,
    work_dir: Path = WORK_DIR,
    shard_count: int = SHARD_COUNT,
    report_path: Path | None = REPORT,
) -> dict:
    started = time.perf_counter()
    work_dir.mkdir(parents=True, exist_ok=True)
    classified_path = work_dir / "classified.json"
    if not classified_path.exists():
        scanned = scan_keys(src, work_dir, shard_count)
        classified = classify_shards(work_dir, shard_count)
        _save_keys(work_dir / "clean", classified["clean"])
        _save_keys(work_dir / "conflict", classified["conflict"])
        payload = {"grain": GRAIN, "scan": scanned, "totals": classified["totals"]}
        classified_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        for child in (work_dir / "shards").glob("*.bin"):
            child.unlink()
    else:
        payload = json.loads(classified_path.read_text(encoding="utf-8"))
        if payload.get("grain") != GRAIN:
            raise RuntimeError(f"classified.json grain is {payload.get('grain')}, expected {GRAIN}")
    completed: list[str] | None = None
    base_stored = 0
    if db_path.exists() and db_path.stat().st_size > 0:
        completed, base_stored = resume_plan(
            src,
            work_dir,
            db_path.parent / "build_year_month.log",
        )
        files = sorted(path.name for path in src.glob("*.zip"))
        nxt = files[len(completed)] if len(completed) < len(files) else "none"
        print(
            f"resume done={len(completed)} next={nxt} stored_base={base_stored}",
            flush=True,
        )
    print("loading classified keys", flush=True)
    clean = _load_keys(work_dir / "clean")
    conflict = _load_keys(work_dir / "conflict")
    print(
        f"loaded clean_asofs={len(clean)} conflict_asofs={len(conflict)}",
        flush=True,
    )
    stored = load_observations(
        src,
        db_path,
        clean,
        conflict,
        progress_dir=work_dir,
        completed=completed,
        base_stored=base_stored,
    )
    elapsed = round(time.perf_counter() - started, 1)
    size = db_path.stat().st_size
    report = {
        "run_date": date.today().isoformat(),
        "grain": GRAIN,
        "database": str(db_path),
        "source_zip_dir": str(src),
        "unique_pnu": payload["totals"]["unique_pnu"],
        "stored_observations": stored["stored"],
        "collapsed_identical": payload["totals"]["identical"],
        "conflict_keys": payload["totals"]["conflict_keys"],
        "conflict_variants": payload["totals"]["conflict_variants"],
        "conflict_stored": stored["conflict_stored"],
        "sqlite_bytes_including_primary_key": size,
        "elapsed_seconds": elapsed,
        "rows_in": payload["scan"]["rows_in"],
        "held": payload["scan"]["held"],
        "asofs": payload["totals"]["asofs"],
        "source_files": payload["scan"]["files"],
        "ok": (
            stored["stored"] == payload["totals"]["clean_keys"]
            and stored["conflict_stored"] == payload["totals"]["conflict_variants"]
        ),
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {report_path} bytes={size} stored={stored['stored']} seconds={elapsed}", flush=True)
    if report["ok"] is not True:
        raise RuntimeError(
            f"ledger counts do not match classified keys: stored={stored['stored']} "
            f"clean={payload['totals']['clean_keys']} "
            f"conflict_stored={stored['conflict_stored']} "
            f"variants={payload['totals']['conflict_variants']}"
        )
    return report


if __name__ == "__main__":
    load()
