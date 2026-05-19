"""
배치 파이프라인 오케스트레이션

- 초기 적재: 최근 N년 전체 수집 → 정제 → 사전집계
- 정기 갱신(매월 1일 등 스케줄러에서 호출): 최근 M개월 재수집 → 정제 → 사전집계

개별 단계만 실행하려면 collect.py / clean.py / build_stats.py 를 직접 호출한다.

사용 예:
    python run_pipeline.py --initial --years 5
    python run_pipeline.py --refresh --months 3
    python run_pipeline.py --excel-dir "C:/원본/토지"   # 폴더 내 xlsx 전부 → raw → clean → build_stats
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text

from db_utils import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def _run(script: str, *args: str) -> None:
    cmd = [PY, str(ROOT / script), *args]
    log.info("실행: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def _truncate_paid_caches() -> None:
    """
    파이프라인이 원장·사전집계를 갱신하면 두 캐시 모두 stale 이 된다.

    - `analysis_cache` (응답 캐시, 24h TTL): 같은 페이로드의 옛 매트릭스를 그대로 반환할 수 있음.
    - `analysis_base_cache` (row_ids 캐시, 4h TTL): `clean.py --reprocess-all` 등으로 transaction_hash
      가 바뀌면 land_transactions.id 가 달라져 옛 row_ids 가 다른 거래를 가리킬 위험.

    DECISIONS.md D-003 — 파이프라인이 끝나는 시점에 두 테이블 모두 비운다.
    실패해도 파이프라인 종료를 막지는 않는다(로그만).
    """

    targets = ("analysis_cache", "analysis_base_cache")
    try:
        engine = get_engine()
        with engine.begin() as conn:
            for name in targets:
                exists = conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.tables WHERE table_name = :n"
                    ),
                    {"n": name},
                ).fetchone()
                if not exists:
                    log.info("%s 테이블 없음 — 캐시 정리 생략", name)
                    continue
                before = conn.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar() or 0
                conn.execute(text(f"TRUNCATE {name}"))
                log.info("%s 비움 (이전 %d건)", name, int(before))
    except Exception as exc:
        log.warning("paid 캐시 비우기 실패(파이프라인 결과는 정상): %s", exc)


# 하위 호환 별칭 — 외부에서 부르는 곳이 있으면 영향이 없도록.
_truncate_paid_analysis_cache = _truncate_paid_caches


def main() -> None:
    parser = argparse.ArgumentParser(description="토지 실거래 수집·정제·사전집계 파이프라인")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--initial", action="store_true", help="최근 N년 전체 수집 (api 모드)")
    g.add_argument("--refresh", action="store_true", help="최근 M개월 재수집·정제 (해제 반영용)")
    g.add_argument(
        "--excel-dir",
        metavar="DIR",
        help="폴더 내 .xlsx 일괄 수집 후 정제·사전집계 (국토부 원본/통합은 collect --format 참고)",
    )
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--months", type=int, default=3)
    parser.add_argument(
        "--skip-collect",
        action="store_true",
        help="수집 생략 (이미 raw에 적재된 경우 정제·집계만)",
    )
    parser.add_argument(
        "--skip-build-stats",
        action="store_true",
        help=(
            "build_stats.py(V1) · build_stats_v2.py 를 모두 건너뛴다. "
            "여러 시도 폴더를 순서대로 정제만 끝낸 뒤 마지막에 한 번만 사전집계를 돌릴 때 사용 "
            "(DECISIONS D-008 / V2_OPERATOR_CHECKLIST §B 권장 흐름)."
        ),
    )
    parser.add_argument(
        "--excel-format",
        choices=["raw", "merged", "auto"],
        default="auto",
        help="--excel-dir 사용 시 collect.py 의 --format (국토부 원본=raw·통합·auto)",
    )
    parser.add_argument(
        "--with-v2",
        action="store_true",
        help=(
            "build_stats.py(V1) 후 build_stats_v2.py 도 실행 — 무료 V2 화면 stale 방지. "
            "windows=3,5, --as-of 는 STATS_V2_DEFAULT_AS_OF_MONTH 가 있으면 그대로 사용. "
            "--skip-build-stats 가 있으면 무시된다."
        ),
    )
    parser.add_argument(
        "--v2-windows",
        default="3,5",
        help="--with-v2 사용 시 build_stats_v2.py 의 --windows (기본 3,5)",
    )
    parser.add_argument(
        "--with-upper-v2",
        action="store_true",
        help="--with-v2 와 함께 build_upper_stats_v2.py (시도·시군구·읍면동 사전집계)",
    )
    args = parser.parse_args()

    if not args.skip_collect:
        if getattr(args, "excel_dir", None):
            _run(
                "collect.py",
                "--mode",
                "excel",
                "--directory",
                str(Path(args.excel_dir).resolve()),
                "--format",
                str(args.excel_format),
            )
        elif args.initial:
            _run("collect.py", "--mode", "api", "--years", str(args.years))
        else:
            _run("collect.py", "--mode", "api", "--months", str(args.months))

    _run("clean.py")
    if args.skip_build_stats:
        log.info(
            "--skip-build-stats: build_stats(V1)·build_stats_v2 생략. "
            "여러 시도/엑셀 적재가 끝난 뒤 마지막에 한 번만 사전집계를 돌리세요."
        )
    else:
        _run("build_stats.py")
        if args.with_v2:
            v2_args: list[str] = ["--windows", str(args.v2_windows)]
            # STATS_V2_DEFAULT_AS_OF_MONTH 가 있으면 명시 — build_stats_v2 도 동일 로직으로 fallback 하지만
            # CLI 에 박아 두면 실행 로그(`실행: ...build_stats_v2.py --as-of ...`)에서 의도가 분명해진다.
            as_of_env = (os.environ.get("STATS_V2_DEFAULT_AS_OF_MONTH") or "").strip()
            if as_of_env:
                v2_args += ["--as-of", as_of_env]
            _run("build_stats_v2.py", *v2_args)
            if args.with_upper_v2:
                _run("build_upper_stats_v2.py", *v2_args)
    # 캐시는 정제만 한 경우에도 stale 이 될 수 있어 항상 비운다 (DECISIONS D-003).
    _truncate_paid_caches()
    log.info("파이프라인 완료")


if __name__ == "__main__":
    main()
