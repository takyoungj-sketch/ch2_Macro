"""Complete hash update for sejong dong rows after partial remap run."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

_PIPELINE = Path(__file__).resolve().parent
if str(_PIPELINE) not in sys.path:
    sys.path.insert(0, str(_PIPELINE))

from transaction_hash import hash_from_series  # noqa: E402


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    _load_env(_PIPELINE / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL required")
    engine = create_engine(url)

    with engine.connect() as c:
        lt = pd.read_sql(
            text(
                """
                SELECT lt.*
                FROM land_transactions lt
                JOIN land_transactions_raw r ON r.id = lt.raw_id
                WHERE r.raw_data->>'sigungu_name' ~ '^세종특별자치시\\s+[가-힣]+동\\s*$'
                  AND LEFT(btrim(lt.beopjungri_code::text), 8) LIKE '361101%'
                """
            ),
            c,
        )

    deleted = updated = 0
    with engine.begin() as conn:
        for _, row in lt.iterrows():
            lt_id = int(row["id"])
            new_h = hash_from_series(row)
            conflict = conn.execute(
                text(
                    """
                    SELECT id FROM land_transactions
                    WHERE transaction_hash = :th AND id <> :id
                    LIMIT 1
                    """
                ),
                {"th": new_h, "id": lt_id},
            ).fetchone()
            if conflict:
                conn.execute(
                    text("DELETE FROM land_transactions WHERE id = :id"),
                    {"id": lt_id},
                )
                deleted += 1
            else:
                conn.execute(
                    text(
                        """
                        UPDATE land_transactions
                        SET transaction_hash = :th, updated_at = NOW()
                        WHERE id = :id
                        """
                    ),
                    {"th": new_h, "id": lt_id},
                )
                updated += 1

    print(f"hash fix: updated={updated}, deleted_duplicates={deleted}")


if __name__ == "__main__":
    main()
