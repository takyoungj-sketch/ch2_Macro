#!/usr/bin/env python3
"""집합 매매 × 주거 임대 정확 키 맵. 보조 층 없음. 원장 UPDATE 없음."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipeline"))

from collective.db_utils import get_collective_engine  # noqa: E402
from rent.db_utils import get_rent_engine  # noqa: E402

KEYS_SQL = """
SELECT DISTINCT building_key, asset_type
FROM {table}
WHERE is_valid = true
  AND asset_type IN ('apartment', 'rowhouse', 'officetel')
  AND NULLIF(btrim(building_key::text), '') IS NOT NULL
"""


def _keys(engine, table: str) -> set[tuple[str, str]]:
    with engine.connect() as conn:
        rows = conn.execute(text(KEYS_SQL.format(table=table))).all()
    return {(str(r[1]), str(r[0]).strip()) for r in rows}


def main() -> None:
    sale = _keys(get_collective_engine(), "collective_transactions")
    rent = _keys(get_rent_engine(), "rent_transactions")
    exact = sale & rent
    today = date.today()
    rows = [
        {
            "sale_building_key": bk,
            "rent_building_key": bk,
            "asset_type": at,
            "tier": "exact",
            "built_on": today,
        }
        for at, bk in exact
    ]
    eng = get_rent_engine()
    with eng.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS rent_sale_building_map (
                    sale_building_key   CHAR(64)     NOT NULL,
                    rent_building_key   CHAR(64)     NOT NULL,
                    asset_type          VARCHAR(20)  NOT NULL,
                    tier                VARCHAR(16)  NOT NULL DEFAULT 'exact',
                    built_on            DATE         NOT NULL DEFAULT CURRENT_DATE,
                    PRIMARY KEY (sale_building_key, asset_type)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_rent_sale_map_rent
                    ON rent_sale_building_map (rent_building_key, asset_type)
                """
            )
        )
        conn.execute(text("TRUNCATE rent_sale_building_map"))
        if rows:
            conn.execute(
                text(
                    """
                    INSERT INTO rent_sale_building_map
                      (sale_building_key, rent_building_key, asset_type, tier, built_on)
                    VALUES
                      (:sale_building_key, :rent_building_key, :asset_type, :tier, :built_on)
                    """
                ),
                rows,
            )
        counts = conn.execute(
            text(
                """
                SELECT asset_type, count(*)::int
                FROM rent_sale_building_map
                GROUP BY 1
                ORDER BY 1
                """
            )
        ).all()
    print(f"exact={len(rows)}")
    for at, n in counts:
        print(f"  {at} {n}")


if __name__ == "__main__":
    main()
