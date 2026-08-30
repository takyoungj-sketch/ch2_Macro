"""FastAPI 앱 진입점."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.gzip import GZipMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.routers import free, free_v2, geocode, paid, upper_stats
from app.map.router import router as map_router

if (settings.built_database_url or "").strip():
    from app.built.router import router as built_router
else:
    built_router = None

if (settings.collective_database_url or "").strip():
    from app.collective.router import router as collective_router
else:
    collective_router = None

try:
    from app.rent.db import resolved_rent_database_url

    rent_router = None
    if resolved_rent_database_url():
        from app.rent.router import router as rent_router
except Exception:  # noqa: BLE001
    rent_router = None

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
app.add_middleware(GZipMiddleware, minimum_size=1500)


# DECISIONS D-007 — `API_TOKEN` 환경변수가 비어 있으면 통과(개발), 값이 있으면 검사.
@app.middleware("http")
async def _api_token_guard(request: Request, call_next):
    expected = (settings.api_token or "").strip()
    if not expected:
        return await call_next(request)
    # 헬스체크·OpenAPI 문서·preflight 는 보호 대상 아님.
    open_paths = {"/health", "/openapi.json", "/docs", "/redoc"}
    path = request.url.path
    if request.url.path in open_paths or request.method == "OPTIONS":
        return await call_next(request)
    # 플랫폼 — 사용자 JWT·웹훅 시크릿으로 보호 (X-Api-Token 과 분리)
    if path.startswith("/api/auth/") or path.startswith("/api/board/") or path.startswith("/api/billing/"):
        return await call_next(request)
    if path.startswith("/api/platform/fieldnote/ai/"):
        return await call_next(request)
    # nginx가 /api/ 프록시 시 X-CH2-Proxy-Token 을 주입(클라이언트 헤더 덮어씀).
    sent = (
        request.headers.get("x-ch2-proxy-token")
        or request.headers.get("x-api-token")
        or ""
    ).strip()
    if sent != expected:
        return JSONResponse(
            status_code=401,
            content={"detail": "API 토큰이 없거나 잘못되었습니다 (X-Api-Token)."},
        )
    return await call_next(request)


# DECISIONS D-001 — V1 통계 엔드포인트(/free/stats/*)는 폐기됨. /free/regions 는 V2로 이전 완료.
# free.py 는 free_v2.py 가 의존하는 헬퍼 함수 유지 목적으로 존재.
app.include_router(free.router, prefix="/api")
app.include_router(geocode.router, prefix="/api")
app.include_router(map_router, prefix="/api")
app.include_router(free_v2.router, prefix="/api")
app.include_router(paid.router, prefix="/api")
app.include_router(upper_stats.router, prefix="/api")
# Twin SSOT: /api/regional-profile/twins* (algo 21). Legacy /twin-regions · /twin-v8 제거.
if built_router is not None:
    app.include_router(built_router, prefix="/api")
    _LOG.info("built_stats API 활성: /api/built/*")
    try:
        from app.built.lab_twin_router import router as twin_lab_router

        app.include_router(twin_lab_router, prefix="/api")
        _LOG.info("Twin Experiment Lab API 활성: /api/built/lab/twin-experiments*")
    except Exception as exc:  # noqa: BLE001 — optional lab
        _LOG.warning("Twin Experiment Lab API 로드 실패: %s", exc)
if collective_router is not None:
    app.include_router(collective_router, prefix="/api")
    _LOG.info("collective_stats API 활성: /api/collective/*")
    from app.regional_profile.router import router as regional_profile_router

    app.include_router(regional_profile_router, prefix="/api")
    _LOG.info("regional_profile API 활성: /api/regional-profile/*")
    from app.qa_audit.router import router as qa_audit_router

    app.include_router(qa_audit_router, prefix="/api")
    _LOG.info("QA audit API 활성(관리자·스키마 비공개): /api/admin/qa/*")
if rent_router is not None:
    app.include_router(rent_router, prefix="/api")
    _LOG.info("rent_stats API 활성: /api/rent/*")

from app.ai.router import router as ai_router
from app.ai.usage_router import router as ai_usage_router

app.include_router(ai_router, prefix="/api")
app.include_router(ai_usage_router, prefix="/api")
_LOG.info("CH2 AI API 활성: /api/ai/* · /api/admin/ai-usage")

from app.parcel_lab.router import router as parcel_lab_router

app.include_router(parcel_lab_router, prefix="/api")
_LOG.info("대장DB 조회 API 활성(관리자·로컬): /api/admin/parcel/status")

if (settings.platform_database_url or "").strip():
    from app.platform.auth_router import router as platform_auth_router
    from app.platform.board_router import router as platform_board_router
    from app.platform.billing_router import router as platform_billing_router
    from app.platform.fieldnote_ai_router import router as platform_fieldnote_ai_router

    app.include_router(platform_auth_router, prefix="/api")
    app.include_router(platform_board_router, prefix="/api")
    app.include_router(platform_billing_router, prefix="/api")
    app.include_router(platform_fieldnote_ai_router, prefix="/api/platform")
    _LOG.info("CH2 Platform API 활성: /api/auth/*, /api/board/*, /api/billing/*")


# 폐기 일정 헤더 — RFC 8594 Sunset. V1 통계 경로(/free/stats/*)에만 적용.
_V1_SUNSET_HEADER = "Wed, 30 Jun 2026 23:59:59 GMT"


@app.middleware("http")
async def _v1_sunset_header(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    # 무료 V1 통계 경로만 대상 (/free/stats/). /free/regions 및 /free/v2/ 는 제외.
    if path.startswith("/api/free/stats/") or path == "/api/free/stats":
        response.headers.setdefault("Sunset", _V1_SUNSET_HEADER)
        response.headers.setdefault(
            "Deprecation",
            "version=\"v1\"; date=\"Mon, 30 Jun 2026 23:59:59 GMT\"",
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


def _approx_table_rows(conn, table: str) -> int | None:
    """pg_class.reltuples 추정 행수 — /health 전수 COUNT 회피."""
    try:
        row = conn.execute(
            text(
                """
                SELECT GREATEST(reltuples::bigint, 0)
                FROM pg_class
                WHERE oid = to_regclass(:t)
                """
            ),
            {"t": f"public.{table}"},
        ).scalar()
        return int(row) if row is not None else None
    except Exception:  # noqa: BLE001
        return None


def _safe_built_health() -> Optional[dict]:
    if not (settings.built_database_url or "").strip():
        return None
    try:
        from app.built.db import get_built_engine

        eng = get_built_engine()
        if eng is None:
            return None
        with eng.connect() as conn:
            conn.execute(text("SELECT 1")).scalar()
            max_year = conn.execute(
                text("SELECT MAX(contract_year) FROM built_transactions")
            ).scalar()
            approx = _approx_table_rows(conn, "built_transactions")
        return {
            "total_transactions": int(approx) if approx is not None else None,
            "total_transactions_approx": True,
            "by_asset_type": {},
            "max_contract_year": int(max_year) if max_year is not None else None,
        }
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("/health built_stats 조회 실패: %s", exc)
        return None


def _safe_collective_health() -> Optional[dict]:
    if not (settings.collective_database_url or "").strip():
        return None
    try:
        from app.collective.db import get_collective_engine

        eng = get_collective_engine()
        if eng is None:
            return None
        with eng.connect() as conn:
            conn.execute(text("SELECT 1")).scalar()
            max_year = conn.execute(
                text("SELECT MAX(contract_year) FROM collective_transactions")
            ).scalar()
            approx = _approx_table_rows(conn, "collective_transactions")
        return {
            "total_transactions": int(approx) if approx is not None else None,
            "total_transactions_approx": True,
            "distinct_buildings": None,
            "by_asset_type": {},
            "max_contract_year": int(max_year) if max_year is not None else None,
        }
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("/health collective_stats 조회 실패: %s", exc)
        return None


@app.get("/health", tags=["헬스체크"])
def health(db: Session = Depends(get_db)):
    """
    DECISIONS D-002 — 외부 모니터·UI 가 신선도 확인에 쓰도록 `latest_as_of_month` 노출.
    값이 비어 있으면 V2 사전집계가 적재되지 않은 상태.
    """
    latest = _safe_latest_as_of_month(db)
    payload: dict = {
        "status": "ok",
        "latest_as_of_month": latest.isoformat() if latest else None,
    }
    built = _safe_built_health()
    if built is not None:
        payload["built_stats"] = built
    collective = _safe_collective_health()
    if collective is not None:
        payload["collective_stats"] = collective
    return payload
