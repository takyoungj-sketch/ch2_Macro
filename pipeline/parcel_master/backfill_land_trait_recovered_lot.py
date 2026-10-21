"""Fill recovered_lot on existing trait-link rows.

Does not update land_transactions. Writes counts only.
Resumes from the progress file outside the repository.
"""

from __future__ import annotations

import gc
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from sqlalchemy import text

from parcel_master.code_history_link_shadow import _merge, _prefixes_for, load_pairs
from parcel_master.land_trait_link_materialize import (
    _classify,
    _load_transactions,
    _sigungu_codes,
    ensure_table,
)
from parcel_master.national_land_link_shadow import _load_plates

PROGRESS = Path(r"C:\CH2\parcel_master\land_trait_recovered_lot_progress.json")
UPDATE = text(
    """
    UPDATE land_transaction_trait_link
    SET recovered_lot = :recovered_lot
    WHERE transaction_hash = :transaction_hash
      AND link_status = :link_status
      AND link_status IN ('exact', 'label_normalized')
      AND (recovered_lot IS NULL OR btrim(recovered_lot) = '')
    """
)


def _write(payload: dict) -> None:
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _update(engine, rows: list[dict]) -> None:
    if not rows:
        return
    with engine.begin() as connection:
        for start in range(0, len(rows), 2000):
            connection.execute(UPDATE, rows[start : start + 2000])


def run(only: list[str] | None = None) -> None:
    from db_utils import get_engine

    engine = get_engine()
    try:
        ensure_table(engine)
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            pairs = load_pairs(connection)
        codes = _sigungu_codes(engine)
        if only:
            wanted = set(only)
            codes = [code for code in codes if code in wanted]
        done = json.loads(PROGRESS.read_text(encoding="utf-8")) if PROGRESS.exists() else {}
        print(f"pairs={len(pairs)} sigungu={len(codes)} done={len(done)}", flush=True)
        for index, code in enumerate(codes, start=1):
            if code in done:
                continue
            started = time.perf_counter()
            plates: dict = defaultdict(list)
            plate_index: dict = defaultdict(set)
            for prefix in _prefixes_for(code, pairs):
                extra_plates, extra_index, _seen = _load_plates(prefix)
                _merge(plates, plate_index, extra_plates, extra_index)
                del extra_plates, extra_index
            for rows_for_pnu in plates.values():
                rows_for_pnu.sort()
            fetched = _load_transactions(engine, code)
            records, summary = _classify(code, plates, plate_index, pairs, fetched)
            updates = [
                {
                    "transaction_hash": row["transaction_hash"],
                    "link_status": row["link_status"],
                    "recovered_lot": row["recovered_lot"],
                }
                for row in records
                if row.get("recovered_lot")
            ]
            _update(engine, updates)
            done[code] = {
                "transactions": int(summary["transactions"]),
                "lots": len(updates),
            }
            _write(done)
            print(
                f"{index}/{len(codes)} {code} tx={summary['transactions']} lots={len(updates)} "
                f"seconds={time.perf_counter() - started:.0f}",
                flush=True,
            )
            del plates, plate_index, fetched, records, updates
            gc.collect()
    finally:
        engine.dispose()


if __name__ == "__main__":
    run(sys.argv[1:] or None)
