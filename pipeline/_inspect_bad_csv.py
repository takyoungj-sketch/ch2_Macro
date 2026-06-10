# -*- coding: utf-8 -*-
"""Inspect suspicious CSV: metadata, columns, sample rows."""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "raw" / "토지_2010_2020"

FILES = [
    "전북특별자치도_토지_매매_2014.csv",
    "전라남도_토지_매매_2017.csv",
    "경상남도_토지_매매_2011.csv",
    "전북특별자치도_토지_매매_2016.csv",
    "전북특별자치도_토지_매매_2020.csv",
]


def decode(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("cp949", "utf-8-sig", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp949", errors="replace")


def inspect(path: Path) -> None:
    text = decode(path)
    lines = text.splitlines()
    print("=" * 70)
    print(path.name)
    print("-" * 70)
    meta_keys = ("시도", "실거래구분", "계약일자", "주소구분")
    for ln in lines[:20]:
        for k in meta_keys:
            if k in ln:
                print(f"  {ln.strip()[:100]}")
                break
    hdr_idx = next(
        (i for i, ln in enumerate(lines) if "시군구" in ln and ("NO" in ln or ln.startswith('"NO"'))),
        None,
    )
    if hdr_idx is None:
        hdr_idx = next((i for i, ln in enumerate(lines) if "시군구" in ln), None)
    if hdr_idx is not None:
        hdr = lines[hdr_idx]
        print(f"\n  HEADER: {hdr[:200]}")
        # land vs apt column hints
        land_hints = ("지목", "용도지역", "계약면적", "거래금액(만원)")
        apt_hints = ("단지명", "전용면적", "층", "건축년도", "아파트")
        cols = hdr
        is_land = any(h in cols for h in land_hints)
        is_apt = any(h in cols for h in apt_hints)
        print(f"  type guess: land={is_land} apt={is_apt}")
        for j in range(1, 4):
            if hdr_idx + j < len(lines):
                print(f"  row{j}: {lines[hdr_idx + j][:120]}")
    else:
        print("  (header not found)")


def main() -> None:
    targets = sys.argv[1:] or FILES
    for name in targets:
        p = RAW / name
        if p.is_file():
            inspect(p)
        else:
            print(f"MISSING: {name}")


if __name__ == "__main__":
    main()
