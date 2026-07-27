#!/usr/bin/env python3
"""Run land annual build without ensure_table (VPS: DDL pre-applied)."""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

PIPE = Path(__file__).resolve().parent
sys.path.insert(0, str(PIPE))

from build_annual_stats import build_for_sido, list_sido_codes, parse_col_axes, parse_year_range  # noqa: E402


def main() -> None:
    year_from, year_to = parse_year_range("2023-2025")
    col_axes = parse_col_axes("category")
    batch_id = f"annual_{year_from}_{year_to}_{uuid.uuid4().hex[:8]}"
    sidos = list_sido_codes()
    total = 0
    for axis in col_axes:
        for sc in sidos:
            total += build_for_sido(
                year_from=year_from,
                year_to=year_to,
                sido_code=sc,
                batch_id=batch_id,
                col_axis=axis,
            )
    print(f"land annual upsert total={total}")


if __name__ == "__main__":
    main()
