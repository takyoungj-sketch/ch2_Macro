#!/usr/bin/env python3
"""
월간 노트북형 엑셀 준비(통합→정제) 일괄 실행.

  1. notebook_land_merge.py — raw/토지/<cycle>/토지_매매 → 토지_매매_통합
  2. notebook_land_refine.py — 토지_매매_통합 → 토지_매매_정제

DB 적재 순서와의 관계: 웹/API용 정본은 여전히 `pipeline/collect.py` + `clean.py` 로
국토 원본(`토지_매매/` 평탄 파일) 또는 `flatten` 디렉터리를 통해 적재하고,
본 스크립트는 **통계 분석용 엑셀 템플릿과 동일 형식** 의 산출물만 추가로 만든다.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(
        description="참고/7 토지 통합·정제 노트북과 동등한 폴더 구조 만들기",
    )
    p.add_argument("--cycle-id", required=True, metavar="YYYYMM")
    p.add_argument(
        "--skip-merge",
        action="store_true",
        help="이미 토지_매매_통합 에 파일이 있을 때 통합 단계 건너뜀",
    )
    args = p.parse_args()
    repo = Path(__file__).resolve().parents[2]
    py = sys.executable
    here = Path(__file__).resolve().parent
    cid = args.cycle_id.strip()
    cmds: list[list[str]] = []
    if not args.skip_merge:
        cmds.append([py, str(here / "notebook_land_merge.py"), "--cycle-id", cid])
    cmds.append([py, str(here / "notebook_land_refine.py"), "--cycle-id", cid])
    for cmd in cmds:
        print("실행:", " ".join(cmd), flush=True)
        subprocess.run(cmd, check=True, cwd=str(repo))
    root = repo / "raw" / "토지" / cid
    print("완료. 산출:", root / "토지_매매_통합", "→", root / "토지_매매_정제")


if __name__ == "__main__":
    main()
