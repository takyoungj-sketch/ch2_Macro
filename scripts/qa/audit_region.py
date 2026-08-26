#!/usr/bin/env python3
"""지역 단위 QA 검증 CLI (관리자 전용 · 수동).

  py scripts/qa/audit_region.py --region 나성동 --year 2025
  py scripts/qa/audit_region.py --domain built_enriched --region-code 43113 --year 2025 --asset-type commercial
  py scripts/qa/audit_region.py --region "세종특별자치시 나성동" --year 2025 --save
  py scripts/qa/audit_region.py --region-code 36110107 --year 2025
  py scripts/qa/audit_region.py --random --year 2025 --n 2

원장·마트는 변경하지 않는다. 숫자는 SQL/빌더가 만들고, 보고는 템플릿이다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def main() -> int:
    _configure_stdio()
    p = argparse.ArgumentParser(description="CH2 Macro 지역 QA 검증 (L1·L2·L3)")
    p.add_argument("--year", type=int, default=None, help="달력 연도 (랜덤은 생략 시 함께 추첨)")
    p.add_argument(
        "--domain",
        type=str,
        default="collective_apt",
        help="collective_apt | built_enriched",
    )
    p.add_argument("--asset-type", type=str, default=None, help="집합: apartment|rowhouse|officetel / 복합: commercial|factory|detached")
    p.add_argument("--region", type=str, default=None, help="지역명 (예: 나성동)")
    p.add_argument("--region-code", type=str, default=None, help="8자리 읍면동 등")
    p.add_argument("--region-level", type=str, default=None, help="eupmyeondong|sigungu|sido")
    p.add_argument("--random", action="store_true", help="층화 랜덤 표본 (지역·유형·연도)")
    p.add_argument("--n", type=int, default=1, help="랜덤 표본 수 1~3")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--save", action="store_true", help="qa_audit_run 테이블에 저장")
    p.add_argument("--json", action="store_true", help="JSON만 stdout")
    args = p.parse_args()

    if not args.random and not args.region and not args.region_code:
        p.error("--region / --region-code 또는 --random 이 필요합니다")
    if not args.random and args.year is None:
        p.error("지정 검증은 --year 가 필요합니다")

    from app.qa_audit.engine import _normalize_domain, run_random, run_specified

    try:
        domain = _normalize_domain(args.domain)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    if domain == "built_enriched":
        from app.built.db import get_built_engine

        engine = get_built_engine()
        if engine is None:
            print("BUILT_DATABASE_URL 이 없습니다.", file=sys.stderr)
            return 2
    else:
        from app.collective.db import get_collective_engine

        engine = get_collective_engine()
        if engine is None:
            print("COLLECTIVE_DATABASE_URL 이 없습니다.", file=sys.stderr)
            return 2

    try:
        if args.random:
            runs = run_random(
                engine,
                calendar_year=args.year,
                asset_type=args.asset_type,
                n=args.n,
                save_db=args.save,
                seed=args.seed,
                domain=domain,
            )
        else:
            runs = [
                run_specified(
                    engine,
                    calendar_year=args.year,
                    region_code=args.region_code,
                    region_name=args.region,
                    region_level=args.region_level,
                    asset_type=args.asset_type,
                    save_db=args.save,
                    domain=domain,
                )
            ]
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(runs, ensure_ascii=False, indent=2, default=str))
    else:
        for i, run in enumerate(runs):
            if i:
                print()
            print(run.get("ai_report") or "")
            if run.get("log_path"):
                print(f"로그: {run['log_path']}")
            if run.get("id") is not None:
                print(f"qa_audit_run.id={run['id']}")

    worst = "PASS"
    rank = {"SKIP": -1, "PASS": 0, "REVIEW": 1, "ERROR": 2, "BLOCK": 3}
    for run in runs:
        v = str(run.get("verdict") or "REVIEW")
        if rank.get(v, 1) > rank.get(worst, 0):
            worst = v
    if worst in ("ERROR", "BLOCK"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
