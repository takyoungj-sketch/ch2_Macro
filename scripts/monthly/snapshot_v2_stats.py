"""land_basic_stats_v2 특정 as_of_month 행수·용량 로그 스냅샷(JSON)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import sys

_ROOT = Path(__file__).resolve().parents[2]
_PIPELINE = _ROOT / "pipeline"
if str(_PIPELINE) not in sys.path:
    sys.path.insert(0, str(_PIPELINE))

from sqlalchemy import text  # noqa: E402

from db_utils import get_engine  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="land_basic_stats_v2 as-of 스냅샷 요약 JSON")
    p.add_argument("--as-of", required=True, metavar="YYYY-MM-DD", help="as_of_month(해당 달 1일)")
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()

    engine = get_engine()
    as_of = args.as_of
    q_rows = text(
        """
        SELECT window_years, COUNT(*)::bigint AS n
        FROM land_basic_stats_v2
        WHERE as_of_month = CAST(:as_of AS date)
        GROUP BY window_years
        ORDER BY window_years
        """
    )
    q_sz = text(
        """
        SELECT pg_total_relation_size('land_basic_stats_v2'::regclass)::bigint AS total_bytes
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(q_rows, {"as_of": as_of}).mappings().all()
        sz = conn.execute(q_sz).scalar()

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "as_of_month": as_of,
        "windows": {int(r["window_years"]): int(r["n"]) for r in rows},
        "land_basic_stats_v2_total_relation_bytes": int(sz or 0),
    }
    out = args.output.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {out}")


if __name__ == "__main__":
    main()
