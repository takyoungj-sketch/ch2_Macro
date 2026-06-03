"""
`built_transactions` 유형·시도별 건수 스냅샷 — 월간 검증·전월 대비 비교용.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

_ROOT = Path(__file__).resolve().parents[2]
_PIPELINE_BUILT = _ROOT / "pipeline" / "built"
if str(_PIPELINE_BUILT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_BUILT))

from db_utils import get_built_engine  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="built_transactions 유형·시도별 건수 스냅샷 JSON")
    p.add_argument("--output", required=True, type=Path, help="저장 경로 (.json)")
    p.add_argument("--cycle-id", help="작업 번들 ID (YYYYMM, 메타용)")
    args = p.parse_args()

    engine = get_built_engine()
    q = text(
        """
        SELECT asset_type,
               TRIM(COALESCE(sido_code, '')) AS sido_code,
               COUNT(*)::bigint AS n
        FROM built_transactions
        GROUP BY asset_type, TRIM(COALESCE(sido_code, ''))
        ORDER BY asset_type, sido_code
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(q).mappings().all()

    by_asset: dict[str, dict[str, object]] = {}
    for r in rows:
        asset = str(r["asset_type"])
        sido = str(r["sido_code"] or "")
        n = int(r["n"])
        bucket = by_asset.setdefault(asset, {"total": 0, "by_sido": {}})
        bucket["by_sido"][sido] = n
        bucket["total"] = int(bucket["total"]) + n

    out: dict[str, object] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "by_asset_type": by_asset,
        "total": int(sum(int(v["total"]) for v in by_asset.values())),
    }
    if args.cycle_id:
        out["cycle_id"] = args.cycle_id.strip()

    path = args.output.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {path} (total={out['total']}, types={list(by_asset.keys())})")


if __name__ == "__main__":
    main()
