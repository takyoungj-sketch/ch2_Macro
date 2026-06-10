# -*- coding: utf-8 -*-
"""Verify Jeonbuk CSV file contents (sido in metadata + sample addresses)."""
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "raw" / "토지_2010_2020"

for year in range(2010, 2021):
    p = RAW / f"전북특별자치도_토지_매매_{year}.csv"
    if not p.is_file():
        print(year, "MISSING")
        continue
    raw = p.read_bytes()
    text = None
    for enc in ("cp949", "utf-8-sig", "utf-8", "euc-kr"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("cp949", errors="replace")
    lines = text.splitlines()
    sido_line = next((ln for ln in lines if "시도 :" in ln), "")
    # find first data row (after header with 시군구)
    hdr_idx = next((i for i, ln in enumerate(lines) if "시군구" in ln and "NO" in ln), None)
    sample = lines[hdr_idx + 1] if hdr_idx is not None and hdr_idx + 1 < len(lines) else ""
    print(f"{year}: sido={sido_line[:40]!r} sample={sample[:60]!r}")
