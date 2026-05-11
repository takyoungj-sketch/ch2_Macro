"""
배치 파이프라인 오케스트레이션

- 초기 적재: 최근 N년 전체 수집 → 정제 → 사전집계
- 정기 갱신(매월 1일 등 스케줄러에서 호출): 최근 M개월 재수집 → 정제 → 사전집계

개별 단계만 실행하려면 collect.py / clean.py / build_stats.py 를 직접 호출한다.

사용 예:
    python run_pipeline.py --initial --years 5
    python run_pipeline.py --refresh --months 3
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def _run(script: str, *args: str) -> None:
    cmd = [PY, str(ROOT / script), *args]
    log.info("실행: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="토지 실거래 수집·정제·사전집계 파이프라인")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--initial", action="store_true", help="최근 N년 전체 수집 (api 모드)")
    g.add_argument("--refresh", action="store_true", help="최근 M개월 재수집·정제 (해제 반영용)")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--months", type=int, default=3)
    parser.add_argument(
        "--skip-collect",
        action="store_true",
        help="수집 생략 (이미 raw에 적재된 경우 정제·집계만)",
    )
    args = parser.parse_args()

    if not args.skip_collect:
        if args.initial:
            _run("collect.py", "--mode", "api", "--years", str(args.years))
        else:
            _run("collect.py", "--mode", "api", "--months", str(args.months))

    _run("clean.py")
    _run("build_stats.py")
    log.info("파이프라인 완료")


if __name__ == "__main__":
    main()
