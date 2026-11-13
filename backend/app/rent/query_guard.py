"""임대 회귀·거래목록 요청의 DB 마감 시간. 다른 API에는 적용하지 않는다."""
from __future__ import annotations

import logging
import math
import os
import time
from contextlib import contextmanager
from typing import Iterator, Union

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT_MS = 90_000
MAX_TIMEOUT_MS = 100_000
QUERY_CANCELED = "57014"
REGRESSION_TIMEOUT_MESSAGE = "이 단지는 거래가 많아 지금은 분석할 수 없습니다. 잠시 뒤 다시 시도해 주세요."
TRANSACTIONS_TIMEOUT_MESSAGE = "거래 목록을 찾는 데 시간이 너무 오래 걸려 중단했습니다. 잠시 뒤 다시 시도해 주세요."


def _bounded_timeout(ms: int) -> int:
    if ms > MAX_TIMEOUT_MS:
        logger.warning("임대 요청 제한이 상한을 초과해 100초로 제한합니다.")
    return max(1, min(ms, MAX_TIMEOUT_MS))


def heavy_timeout_ms() -> int:
    raw = (os.getenv("RENT_HEAVY_STATEMENT_TIMEOUT_MS") or "").strip()
    try:
        ms = int(raw) if raw else DEFAULT_TIMEOUT_MS
    except ValueError:
        ms = DEFAULT_TIMEOUT_MS
    return _bounded_timeout(ms)


class QueryDeadline:
    def __init__(self, timeout_ms: int | None = None):
        ms = heavy_timeout_ms() if timeout_ms is None else _bounded_timeout(timeout_ms)
        self.expires_at = time.monotonic() + ms / 1000

    def remaining_ms(self, message: str) -> int:
        # 0은 PostgreSQL에서 무제한이므로 절대로 보내지 않는다.
        ms = math.floor((self.expires_at - time.monotonic()) * 1000)
        if ms < 1:
            raise HTTPException(503, message)
        return ms


async def request_query_deadline() -> QueryDeadline:
    """동기 엔드포인트·DB 의존성의 스레드 대기 전 요청 예산을 시작한다."""
    return QueryDeadline()


def is_statement_timeout(exc: BaseException) -> bool:
    return getattr(getattr(exc, "orig", None), "pgcode", None) == QUERY_CANCELED


class DeadlineDB:
    def __init__(self, db, deadline: QueryDeadline, message: str):
        self.db, self.deadline, self.message = db, deadline, message

    def execute(self, statement, params=None):
        remaining = self.deadline.remaining_ms(self.message)
        self.db.execute(text("SELECT set_config('statement_timeout', :v, true)"), {"v": f"{remaining}ms"})
        result = self.db.execute(statement, params)
        self.deadline.remaining_ms(self.message)
        return result


@contextmanager
def heavy_query(
    db: Union[Session, Connection], *, message: str,
    timeout_ms: int | None = None, deadline: QueryDeadline | None = None,
) -> Iterator[DeadlineDB]:
    """각 SQL에 같은 요청의 남은 예산을 적용하고 트랜잭션 로컬 설정을 복원한다."""
    deadline = deadline if deadline is not None else QueryDeadline(timeout_ms)
    deadline.remaining_ms(message)
    prev = db.execute(text("SELECT current_setting('statement_timeout')")).scalar()
    try:
        yield DeadlineDB(db, deadline, message)
        deadline.remaining_ms(message)
        db.execute(text("SELECT set_config('statement_timeout', :v, true)"), {"v": str(prev)})
    except BaseException as exc:
        # 읽기 전용 경로: 예외 시 aborted 트랜잭션을 풀에 돌려보내지 않는다.
        try:
            db.rollback()
        except Exception:
            db.invalidate()
        if isinstance(exc, DBAPIError) and is_statement_timeout(exc):
            raise HTTPException(503, message) from exc
        raise
