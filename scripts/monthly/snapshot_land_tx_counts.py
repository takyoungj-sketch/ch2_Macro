"""
`land_transactions` 시도별 건수 스냅샷을 JSON 으로 저장 — 월간 검증·전월 대비 비교용.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

# pipeline 패키지의 db_utils 재사용
import sys

_ROOT = Path(__file__).resolve().parents[2]
_PIPELINE = _ROOT / "pipeline"
if str(_PIPELINE) not in sys.path:
    sys.path.insert(0, str(_PIPELINE))

from db_utils import get_engine  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="land_transactions 시도별 건수 스냅샷 JSON")
    p.add_argument("--output", required=True, type=Path, help="저장 경로 (.json)")
    args = p.parse_args()

    engine = get_engine()
    q = text(
        """
        SELECT TRIM(sido_code) AS sido_code, COUNT(*)::bigint AS n
        FROM land_transactions
        GROUP BY TRIM(sido_code)
        ORDER BY TRIM(sido_code)
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(q).mappings().all()

    out = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "by_sido": {r["sido_code"]: int(r["n"]) for r in rows},
        "total": int(sum(int(r["n"]) for r in rows)),
    }

    path = args.output.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {path} (total={out['total']}, sidos={len(out['by_sido'])})")


if __name__ == "__main__":
    main()
