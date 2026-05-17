"""유료 분석 응답 캐시 비우기 (수동 운영 도구).

`/paid/analyze` 가 24h TTL 로 결과를 보존하므로, 이전 요청과 동일한 본문이 들어오면
이미 저장된 결과(매트릭스 포함)를 그대로 반환한다. 데이터/필터 로직이 바뀐 직후
같은 요청이라도 옛 결과가 보일 수 있어, 검증·재현 시 한 번만 비워주면 된다.

DECISIONS D-003 — `pipeline/run_pipeline.py` 가 끝날 때 두 캐시 모두 자동 비움. 이 스크립트는
수동/즉시 호출 용도. 기본값은 `analysis_cache` 만 비우고, `--with-base-cache` 를 주면
`analysis_base_cache`(row_ids 캐시)도 함께 비운다 (transaction_hash 변경 등으로 stale 의심 시).

사용법:
    python backend/scripts/clear_analysis_cache.py
    python backend/scripts/clear_analysis_cache.py --with-base-cache
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_backend = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_backend))

from sqlalchemy import create_engine, text  # noqa: E402

from app.config import settings  # noqa: E402


def _truncate(engine, table: str) -> tuple[int, int]:
    """비우기 전후 행수 반환. 테이블이 없으면 (-1, -1)."""
    with engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM information_schema.tables WHERE table_name = :n"),
            {"n": table},
        ).fetchone()
    if not exists:
        return -1, -1
    with engine.begin() as conn:
        before = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
        conn.execute(text(f"TRUNCATE {table}"))
    with engine.connect() as conn:
        after = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
    return int(before), int(after)


def main() -> None:
    parser = argparse.ArgumentParser(description="유료 분석 캐시 비우기")
    parser.add_argument(
        "--with-base-cache",
        action="store_true",
        help="analysis_base_cache(row_ids)도 함께 비움 — transaction_hash 변경 등으로 stale 의심 시",
    )
    args = parser.parse_args()

    engine = create_engine(settings.database_url)
    targets = ["analysis_cache"]
    if args.with_base_cache:
        targets.append("analysis_base_cache")
    for table in targets:
        before, after = _truncate(engine, table)
        if before < 0:
            print(f"{table}: 테이블 없음 — 생략")
        else:
            print(f"{table}: {before} → {after} 건")


if __name__ == "__main__":
    main()
