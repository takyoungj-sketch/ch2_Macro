"""분양권 적재 요약."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.collective.db import get_collective_engine  # noqa: E402

e = get_collective_engine()
with e.connect() as c:
    n = c.execute(
        text("SELECT COUNT(*) FROM collective_transactions WHERE asset_type='presale'")
    ).scalar()
    b = c.execute(
        text("SELECT COUNT(DISTINCT building_key) FROM collective_transactions WHERE asset_type='presale'")
    ).scalar()
    yrs = c.execute(
        text(
            """
            SELECT contract_year, COUNT(*) FROM collective_transactions
            WHERE asset_type='presale' GROUP BY 1 ORDER BY 1
            """
        )
    ).fetchall()
    sub = c.execute(
        text(
            """
            SELECT housing_subtype, COUNT(*) FROM collective_transactions
            WHERE asset_type='presale' GROUP BY 1 ORDER BY 2 DESC
            """
        )
    ).fetchall()

print(f"presale transactions={n}")
print(f"distinct buildings={b}")
print("by year:", dict(yrs))
print("housing_subtype:", dict(sub))
