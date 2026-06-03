"""collective_transactions 건수 스냅샷."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "pipeline" / "collective"))
from db_utils import get_collective_engine  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--cycle-id", required=True)
    p.add_argument("--repo-root", type=Path, default=_REPO)
    args = p.parse_args()

    eng = get_collective_engine()
    with eng.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM collective_transactions")).scalar()
        by_type = conn.execute(
            text(
                """
                SELECT asset_type, COUNT(*)::int AS n
                FROM collective_transactions GROUP BY asset_type ORDER BY 1
                """
            )
        ).mappings().all()
        by_addr1 = conn.execute(
            text(
                """
                SELECT addr1, COUNT(*)::int AS n
                FROM collective_transactions
                WHERE addr1 IS NOT NULL
                GROUP BY addr1 ORDER BY n DESC
                """
            )
        ).mappings().all()
        buildings = conn.execute(
            text("SELECT COUNT(DISTINCT building_key) FROM collective_transactions")
        ).scalar()

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "cycle_id": args.cycle_id,
        "total": int(total or 0),
        "distinct_buildings": int(buildings or 0),
        "by_asset_type": {r["asset_type"]: r["n"] for r in by_type},
        "by_addr1": {r["addr1"]: r["n"] for r in by_addr1},
    }
    out_dir = args.repo_root / "clean_snapshots" / args.cycle_id / "collective"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "collective_tx_counts_after.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
