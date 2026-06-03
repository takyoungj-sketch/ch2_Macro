"""collective 건수 스냅샷 diff."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--before", type=Path, required=True)
    p.add_argument("--after", type=Path, required=True)
    args = p.parse_args()
    before = _load(args.before)
    after = _load(args.after)
    print(f"total: {before.get('total')} -> {after.get('total')}")
    print(f"buildings: {before.get('distinct_buildings')} -> {after.get('distinct_buildings')}")
    bt = before.get("by_asset_type") or {}
    at = after.get("by_asset_type") or {}
    for k in sorted(set(bt) | set(at)):
        print(f"  {k}: {bt.get(k, 0)} -> {at.get(k, 0)}")


if __name__ == "__main__":
    main()
