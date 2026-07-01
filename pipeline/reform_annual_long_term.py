"""Purge stale annual marts for admin-reform sidos, then rebuild 12·28."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from sqlalchemy import text

from db_utils import get_engine

SIDO_PREFIXES = ("12", "28", "29", "46")
ROOT = Path(__file__).resolve().parent
PY = sys.executable


def purge_annual() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        for table, col in (
            ("land_annual_stats", "beopjungri_code"),
            ("land_annual_upper_stats", "region_code"),
        ):
            total = 0
            for p in SIDO_PREFIXES:
                n = conn.execute(
                    text(f"DELETE FROM {table} WHERE {col} LIKE :pat"),
                    {"pat": f"{p}%"},
                ).rowcount or 0
                total += n
                print(f"  {table} sido {p}: deleted {n}")
            print(f"{table} total deleted: {total}")


def main() -> None:
    print("=== purge annual (12,28,29,46) ===")
    purge_annual()
    print("=== build annual 2010-2026 sido 12,28 ===")
    subprocess.run(
        [
            PY,
            str(ROOT / "build_annual_stats.py"),
            "--years",
            "2010-2026",
            "--sido-code",
            "12",
            "--sido-code",
            "28",
            "--with-upper",
        ],
        check=True,
        cwd=str(ROOT),
    )


if __name__ == "__main__":
    main()
