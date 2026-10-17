"""Count 데이터기준일자 values inside each received land-characteristic CSV zip.

Streams every data row. Does not load a national ledger.
"""
from __future__ import annotations

import json
import re
import time
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "raw" / "raw addition" / "토지특성정보CSV(브이월드)"
OUT = ROOT / "docs" / "lab" / "land_characteristic_csv_internal_dates_20261010.json"
DATE_COL = "데이터기준일자"
SIDO_TAIL = re.compile(r"^AL_D195_(\d{2})_(\d{8})\.zip$", re.IGNORECASE)
SIDO_MID = re.compile(r"^AL_(\d{2})_D195_(\d{8})\.zip$", re.IGNORECASE)
SIGUNGU = re.compile(r"^AL_(\d{5})_D195_(\d{8})\.zip$", re.IGNORECASE)


def filename_parts(name: str) -> tuple[str, str]:
    matched = SIGUNGU.match(name) or SIDO_MID.match(name) or SIDO_TAIL.match(name)
    if not matched:
        return "", ""
    ymd = matched.group(2)
    return matched.group(1), f"{ymd[0:4]}-{ymd[4:6]}-{ymd[6:8]}"


def scan(path: Path) -> dict:
    region, filename_date = filename_parts(path.name)
    row: dict = {
        "file": path.name,
        "zip_bytes": path.stat().st_size,
        "region_code": region,
        "filename_date": filename_date,
    }
    counts: Counter[str] = Counter()
    with zipfile.ZipFile(path) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if len(names) != 1:
            row["error"] = f"csv_entries={len(names)}"
            return row
        with zf.open(names[0]) as handle:
            header = handle.readline().decode("cp949").strip().split(",")
            if not header or header[-1] != DATE_COL:
                row["error"] = "unexpected_header"
                row["last_column"] = header[-1] if header else ""
                return row
            for line in handle:
                comma = line.rfind(b",")
                if comma < 0:
                    row["error"] = "row_without_comma"
                    return row
                counts[line[comma + 1 :].strip().decode("ascii")] += 1
    dates = dict(sorted(counts.items()))
    row["rows"] = sum(counts.values())
    row["internal_dates"] = dates
    if dates:
        row["internal_date_min"] = min(dates)
        row["internal_date_max"] = max(dates)
    return row


def main() -> None:
    files = sorted(SRC.glob("*.zip"))
    rows = []
    started = time.perf_counter()
    read_bytes = 0
    for i, path in enumerate(files, start=1):
        item = scan(path)
        rows.append(item)
        read_bytes += item["zip_bytes"]
        if i % 25 == 0 or i == len(files):
            elapsed = int(time.perf_counter() - started)
            print(
                f"{i}/{len(files)} gb={read_bytes / 1e9:.1f} elapsed_s={elapsed} {path.name}",
                flush=True,
            )
    errors = [r["file"] for r in rows if r.get("error")]
    one_date = sum(1 for r in rows if len(r.get("internal_dates") or {}) == 1)
    many_dates = sum(1 for r in rows if len(r.get("internal_dates") or {}) > 1)
    global_dates: Counter[str] = Counter()
    total_rows = 0
    for item in rows:
        for day, n in (item.get("internal_dates") or {}).items():
            global_dates[day] += n
            total_rows += n
    report = {
        "source_dir": str(SRC),
        "method": "every data row; last CSV column after the header is confirmed as 데이터기준일자",
        "zip_count": len(rows),
        "row_count": total_rows,
        "error_count": len(errors),
        "errors": errors,
        "files_with_one_internal_date": one_date,
        "files_with_many_internal_dates": many_dates,
        "internal_date_row_counts": dict(sorted(global_dates.items())),
        "files": rows,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"wrote {OUT} zips={len(rows)} rows={total_rows} one={one_date} many={many_dates} errors={len(errors)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
