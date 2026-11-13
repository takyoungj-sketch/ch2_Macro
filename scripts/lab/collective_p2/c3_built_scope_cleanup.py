"""리허설 단계 built_scope_legacy_cleanup — 복합 scope mart 의 이번 as_of 옛 시도명 행만 지운다.

복합 scope mart 는 addr1 칸으로 UPSERT 해서, 시도명을 바꿔 다시 만들면 이번 as_of 의 옛 시도명
(광주광역시·전라남도) 행이 남는다. 그 as_of 만 지우고 과거 as_of 는 그대로 둔다.
접속 DB 가 리허설 이름(*_p2r)이 아니면 쓰기 전에 멈춘다. 한 트랜잭션.

이전 한 줄 코드(`e.begin().__enter__()`)는 문맥 관리자가 바로 회수돼 첫 쿼리에서
「Connection is closed」로 실패했다(삭제 0).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "pipeline"))
from collective.migrate_p2_keys import REHEARSAL_RE  # noqa: E402

LEGACY_SIDO = ("광주광역시", "전라남도")


def cleanup(engine, as_of: str) -> int:
    with engine.begin() as c:
        db = c.execute(text("select current_database()")).scalar()
        if not REHEARSAL_RE.match(db or ""):
            raise SystemExit(f"리허설 DB가 아님 — 중단: {db}")
        return int(c.execute(
            text("DELETE FROM built_scope_stats WHERE as_of_month = :a AND addr1 IN :s"),
            {"a": as_of, "s": LEGACY_SIDO},
        ).rowcount or 0)


def main():
    as_of = sys.argv[1]
    eng = create_engine(os.environ["BUILT_DATABASE_URL"])
    try:
        print("deleted", cleanup(eng, as_of))
    finally:
        eng.dispose()


if __name__ == "__main__":
    main()
