"""집합상가·집합공장 commercial 데이터 품질 요약."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.collective.db import get_collective_engine  # noqa: E402


def _report(c, asset_type: str, label: str) -> None:
    t = c.execute(
        text("SELECT COUNT(*) FROM collective_commercial_transactions WHERE asset_type=:at"),
        {"at": asset_type},
    ).scalar()
    if not t:
        print(f"\n[{label}] transactions=0 (미적재)")
        return
    floor_n = c.execute(
        text(
            """
            SELECT COUNT(*) FROM collective_commercial_transactions
            WHERE asset_type=:at AND floor IS NOT NULL
            """
        ),
        {"at": asset_type},
    ).scalar()
    land_n = c.execute(
        text(
            """
            SELECT COUNT(*) FROM collective_commercial_transactions
            WHERE asset_type=:at AND land_area IS NOT NULL AND land_area > 0
            """
        ),
        {"at": asset_type},
    ).scalar()
    cl = c.execute(
        text("SELECT COUNT(*) FROM commercial_clusters WHERE asset_type=:at"),
        {"at": asset_type},
    ).scalar()
    n15 = c.execute(
        text("SELECT COUNT(*) FROM commercial_clusters WHERE asset_type=:at AND n_total >= 15"),
        {"at": asset_type},
    ).scalar()
    avg_n = c.execute(
        text("SELECT AVG(n_total) FROM commercial_clusters WHERE asset_type=:at"),
        {"at": asset_type},
    ).scalar()
    print(f"\n[{label}]")
    print(f"  transactions={t}")
    print(f"  floor_filled={floor_n} ({100 * floor_n / t:.1f}%)")
    print(f"  land_area>0={land_n} ({100 * land_n / t:.1f}%)")
    print(f"  clusters={cl} avg_n={float(avg_n or 0):.1f} n>=15={n15} ({100 * n15 / cl:.1f}%)" if cl else f"  clusters=0")


def main() -> None:
    e = get_collective_engine()
    with e.connect() as c:
        _report(c, "collective_shop", "집합상가")
        _report(c, "collective_factory", "집합공장")


if __name__ == "__main__":
    main()
