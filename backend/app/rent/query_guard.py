"""임대 원장 무거운 조회의 DB 시간 제한.

계산된 단지 키(`building_key_sql`)로 거르는 조회는 인덱스를 못 타 원장 전체를 훑을 수 있다.
nginx(120초)가 먼저 끊으면 화면은 504를 받고 DB 쿼리는 끝까지 돈다.
그래서 그 경로만 트랜잭션 범위 `statement_timeout`을 걸고, 초과하면 503 + 구체적 안내로 돌려준다.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Union

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

# nginx proxy_read_timeout(120초)보다 짧게.
DEFAULT_TIMEOUT_MS = 90_000
QUERY_CANCELED = "57014"  # PostgreSQL query_canceled (statement_timeout 포함)

REGRESSION_TIMEOUT_MESSAGE = (
    "이 단지는 거래가 많아 지금은 분석할 수 없습니다. 잠시 뒤 다시 시도해 주세요."
)
TRANSACTIONS_TIMEOUT_MESSAGE = (
    "거래 목록을 찾는 데 시간이 너무 오래 걸려 중단했습니다. 잠시 뒤 다시 시도해 주세요."
)


def heavy_timeout_ms() -> int:
    raw = (os.getenv("RENT_HEAVY_STATEMENT_TIMEOUT_MS") or "").strip()
    try:
        ms = int(raw) if raw else DEFAULT_TIMEOUT_MS
    except ValueError:
        ms = DEFAULT_TIMEOUT_MS
    return max(1, ms)


def is_statement_timeout(exc: BaseException) -> bool:
    orig = getattr(exc, "orig", None)
    return getattr(orig, "pgcode", None) == QUERY_CANCELED


@contextmanager
def heavy_query(db: Union[Session, Connection], *, message: str, timeout_ms: int | None = None) -> Iterator[None]:
    """블록 안의 쿼리에 시간 제한을 걸고, 초과는 503(message)으로 바꾼다.

    `set_config(..., true)` = SET LOCAL: 현재 트랜잭션에만 적용. 블록이 정상 종료되면 원래 값으로 되돌린다.
    """
    ms = timeout_ms if timeout_ms is not None else heavy_timeout_ms()
    prev = db.execute(text("SELECT current_setting('statement_timeout')")).scalar()
    db.execute(text("SELECT set_config('statement_timeout', :v, true)"), {"v": f"{int(ms)}ms"})
    try:
        yield
    except DBAPIError as exc:
        if is_statement_timeout(exc):
            # 트랜잭션은 이미 중단 상태 — 되돌리고 연결을 깨끗하게 둔다.
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
            raise HTTPException(503, message) from exc
        raise
    else:
        db.execute(text("SELECT set_config('statement_timeout', :v, true)"), {"v": str(prev)})
