"""
이전 `snapshot_land_tx_counts.py` JSON 과 비교 — 시도 누락·급변 경고(휴리스틱).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(description="시도별 건수 스냅샷 비교")
    p.add_argument("--before", required=True, type=Path)
    p.add_argument("--after", required=True, type=Path)
    p.add_argument(
        "--ratio-warn",
        type=float,
        default=0.35,
        help="전월 대비 증감 비율이 이 값을 넘기면 경고 (기본 0.35 = 35%%)",
    )
    args = p.parse_args()

    b = json.loads(args.before.read_text(encoding="utf-8"))
    a = json.loads(args.after.read_text(encoding="utf-8"))
    bs = b.get("by_sido") or {}
    aa = a.get("by_sido") or {}

    issues: list[str] = []
    all_keys = sorted(set(bs) | set(aa))
    for k in all_keys:
        nb = int(bs.get(k, 0))
        na = int(aa.get(k, 0))
        if na == 0 and nb > 0:
            issues.append(f"[누락?] sido={k!r}: before={nb} → after=0")
        if nb > 0 and na > 0:
            ch = abs(na - nb) / nb
            if ch >= args.ratio_warn:
                issues.append(
                    f"[급변] sido={k!r}: before={nb} after={na} (|Δ|/before={ch:.2%})"
                )

    print(f"before total={b.get('total')} after total={a.get('total')}")
    if not issues:
        print("특이사항 없음(휴리스틱 기준).")
        raise SystemExit(0)
    print("--- 경고 ---")
    for line in issues:
        print(line)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
