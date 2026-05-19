"""FastAPI 앱 진입점."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.routers import free, free_v2, paid, upper_stats

logging.basicConfig(level=logging.INFO)
_LOG = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """앱 시작/종료 훅 (FastAPI 0.93+ 권장 방식 — 구 `@app.on_event` 대체)."""
    from app.v2_stats_windows import default_as_of_month_for_service

    eff = settings.stats_v2_default_as_of_month or default_as_of_month_for_service(
        settings.stats_v2_assumed_today
    )
    _LOG.info(
        "V2 API 기본 as_of_month=%s (STATS_V2_DEFAULT_AS_OF_MONTH=%s, STATS_V2_ASSUMED_TODAY=%s)",
        eff,
        settings.stats_v2_default_as_of_month,
        settings.stats_v2_assumed_today,
    )
    if settings.api_token:
        _LOG.info("API_TOKEN 보호 활성: 비-/health 요청은 X-Api-Token 헤더 필요")
    else:
        _LOG.info("API_TOKEN 미설정 — 인증 미들웨어 비활성 (개발/로컬 모드)")
    yield


app = FastAPI(
    title="토지 실거래 통계 API",
    description="감정평가사용 토지 실거래 통계 웹서비스 MVP",
    version="0.1.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# DECISIONS D-007 — `API_TOKEN` 환경변수가 비어 있으면 통과(개발), 값이 있으면 검사.
@app.middleware("http")
async def _api_token_guard(request: Request, call_next):
    expected = (settings.api_token or "").strip()
    if not expected:
        return await call_next(request)
    # 헬스체크·OpenAPI 문서·preflight 는 보호 대상 아님.
    open_paths = {"/health", "/openapi.json", "/docs", "/redoc"}
    if request.url.path in open_paths or request.method == "OPTIONS":
        return await call_next(request)
    sent = request.headers.get("x-api-token", "")
    if sent != expected:
        return JSONResponse(
            status_code=401,
            content={"detail": "API 토큰이 없거나 잘못되었습니다 (X-Api-Token)."},
        )
    return await call_next(request)


# DECISIONS D-001 — V1 무료 라우터는 폐기 일정에 들어감. include 시 deprecated 마킹은 라우터 단위
# (모든 V1 엔드포인트 OpenAPI 에 deprecated 표기). 폐기 일정은 `docs/DECISIONS.md` D-001 참조.
app.include_router(free.router, prefix="/api", deprecated=True)
app.include_router(free_v2.router, prefix="/api")
app.include_router(paid.router, prefix="/api")
app.include_router(upper_stats.router, prefix="/api")


# 폐기 일정 헤더 — RFC 8594 Sunset.
_V1_SUNSET_HEADER = "Wed, 31 Mar 2026 23:59:59 GMT"


@app.middleware("http")
async def _v1_sunset_header(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    # 무료 V1 (`/api/free/...`) 만 대상. V2 (`/api/free/v2/...`) 는 제외.
    if path.startswith("/api/free/") and not path.startswith("/api/free/v2/"):
        response.headers.setdefault("Sunset", _V1_SUNSET_HEADER)
        response.headers.setdefault(
            "Deprecation",
            "version=\"v1\"; date=\"Wed, 31 Mar 2026 23:59:59 GMT\"",
        )
    return response


@app.exception_handler(Exception)
async def fallback_json_500_handler(request: Request, exc: Exception):
    """HTML 500 대신 JSON `detail`(axios가 파싱 가능) 반환 및 서버 로그에 스택 출력."""
    log = logging.getLogger("app.uncaught")
    log.exception("%s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": (
                "서버에서 예기치 않은 오류가 발생했습니다. "
                "백엔드 콘솔(uvicorn) 로그에 자세한 스택이 출력됩니다."
            )
        },
    )


def _safe_latest_as_of_month(db: Session) -> Optional[date]:
    """`/health` 에서 사용 — 테이블 누락·권한 오류 시 None."""
    try:
        row = db.execute(
            text("SELECT MAX(as_of_month) AS am FROM land_basic_stats_v2")
        ).fetchone()
        return row.am if row and row.am is not None else None
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("/health latest_as_of_month 조회 실패: %s", exc)
        return None


@app.get("/health", tags=["헬스체크"])
def health(db: Session = Depends(get_db)):
    """
    DECISIONS D-002 — 외부 모니터·UI 가 신선도 확인에 쓰도록 `latest_as_of_month` 노출.
    값이 비어 있으면 V2 사전집계가 적재되지 않은 상태.
    """
    latest = _safe_latest_as_of_month(db)
    return {
        "status": "ok",
        "latest_as_of_month": latest.isoformat() if latest else None,
    }
