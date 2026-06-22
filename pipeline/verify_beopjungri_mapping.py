#!/usr/bin/env python3
"""
beopjungri_code 매칭 품질 검증 — attach_beopjungri_codes() 회귀 게이트.

월간 DB 갱신 후 실행:
  - 전체·유형별(토지/집합/복합) 매칭률 (목표 ≥ 99.7%)
  - needs_review 건수
  - 전월 대비 매칭률 변화
  - 새로 미매칭된 주소 Top 100

사용:
    cd pipeline
    python verify_beopjungri_mapping.py --cycle-id 202606
    python verify_beopjungri_mapping.py --cycle-id 202606 --previous ../clean_snapshots/202605/beopjungri_mapping_report.json
    python verify_beopjungri_mapping.py --cycle-id 202606 --min-pct 99.5 --warn-only

exit 0 = 게이트 통과, 1 = 실패.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent

for _stream in (sys.stdout, sys.stderr):
    try:
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

from beopjungri_mapping_report import (  # noqa: E402
    DEFAULT_MIN_MAPPED_PCT,
    build_report,
    find_previous_report,
    format_summary_lines,
    load_previous_report,
    save_report,
)
from db_utils import get_engine  # noqa: E402


def _load_built_engine():
    import importlib.util

    spec = importlib.util.spec_from_file_location("built_db_utils", ROOT / "built" / "db_utils.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("built db_utils load failed")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.get_built_engine()


def _load_collective_engine():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "collective_db_utils", ROOT / "collective" / "db_utils.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("collective db_utils load failed")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.get_collective_engine()


def main() -> None:
    p = argparse.ArgumentParser(description="beopjungri 매칭 품질 회귀 검증")
    p.add_argument("--cycle-id", help="작업 번들 ID (YYYYMM) — 스냅샷 경로·메타")
    p.add_argument(
        "--output",
        type=Path,
        help="JSON 리포트 저장 (기본: clean_snapshots/{cycle}/beopjungri_mapping_report.json)",
    )
    p.add_argument(
        "--previous",
        type=Path,
        help="이전 리포트 JSON (미지정 시 clean_snapshots 에서 자동 탐색)",
    )
    p.add_argument(
        "--repo-root",
        type=Path,
        default=REPO,
        help="저장소 루트",
    )
    p.add_argument(
        "--min-pct",
        type=float,
        default=DEFAULT_MIN_MAPPED_PCT,
        help=f"전체·핵심 유형 매칭률 하한 (기본 {DEFAULT_MIN_MAPPED_PCT})",
    )
    p.add_argument(
        "--max-drop-pp",
        type=float,
        default=0.5,
        help="전월 대비 mapped_pct 하락 경고 임계 (percentage points)",
    )
    p.add_argument("--skip-land", action="store_true")
    p.add_argument("--skip-collective", action="store_true")
    p.add_argument("--skip-built", action="store_true")
    p.add_argument(
        "--warn-only",
        action="store_true",
        help="게이트 실패해도 exit 0 (경고만)",
    )
    p.add_argument(
        "--artifact",
        type=Path,
        default=REPO / "logs" / "verify_beopjungri_mapping.txt",
        help="요약 텍스트 로그",
    )
    args = p.parse_args()

    repo = args.repo_root.expanduser().resolve()
    cycle = (args.cycle_id or "").strip() or None

    out_path = args.output
    if out_path is None:
        if not cycle:
            raise SystemExit("--output 또는 --cycle-id 필요")
        out_path = repo / "clean_snapshots" / cycle / "beopjungri_mapping_report.json"
    else:
        out_path = out_path.expanduser().resolve()

    prev_path = args.previous.expanduser().resolve() if args.previous else None
    if prev_path is None and cycle:
        auto = find_previous_report(repo, cycle)
        if auto:
            prev_path = auto
    previous = load_previous_report(prev_path)

    land_eng = None if args.skip_land else get_engine()
    coll_eng = None if args.skip_collective else _load_collective_engine()
    built_eng = None if args.skip_built else _load_built_engine()

    land_conn = land_eng.connect() if land_eng else None
    coll_conn = coll_eng.connect() if coll_eng else None
    built_conn = built_eng.connect() if built_eng else None

    try:
        report = build_report(
            land_conn=land_conn,
            collective_conn=coll_conn,
            built_conn=built_conn,
            cycle_id=cycle,
            previous_report=previous,
            min_mapped_pct=args.min_pct,
            max_drop_pp=args.max_drop_pp,
        )
    finally:
        if land_conn is not None:
            land_conn.close()
        if coll_conn is not None:
            coll_conn.close()
        if built_conn is not None:
            built_conn.close()

    if prev_path:
        report.setdefault("delta_vs_previous", {})["previous_path"] = str(prev_path)

    save_report(out_path, report)
    lines = ["=== verify_beopjungri_mapping ===", *format_summary_lines(report), f"report: {out_path}"]
    text = "\n".join(lines)
    print(text)
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(text + "\n", encoding="utf-8")

    passed = bool((report.get("gate") or {}).get("passed"))
    if passed or args.warn_only:
        raise SystemExit(0)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
