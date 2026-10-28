"""D-080 제품 게이트.

비로그인은 토지·집합 기본통계와 기본 조건 5년 롤링만 연다.
그 밖은 로그인 또는 구독이 필요하다. 산식은 여기서 바꾸지 않는다.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Mapping

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.platform.db import get_platform_session_factory
from app.platform.entitlements import list_entitlements
from app.platform.jwt_util import COOKIE_NAME, decode_access_token

_LOGIN = "로그인이 필요합니다."
_SUBSCRIBE = "구독이 필요합니다."

_ALWAYS_OPEN_PREFIXES = (
    "/health",
    "/openapi.json",
    "/docs",
    "/redoc",
    "/api/auth/",
    "/api/billing/",
    "/api/board/",
    "/api/ops/",
    "/api/platform/",
    "/api/map/",
    "/api/geocode/",
    "/api/admin/",
    "/api/lab/",
    "/api/built/lab/",
    "/api/free/v2/regions",
    "/api/free/v2/meta/",
    "/api/free/regions",
)

_MACRO_PREFIXES = (
    "/api/built/",
    "/api/rent/",
    "/api/regional-profile/",
    "/api/insight/",
    "/api/ai/",
    "/api/ai3/",
)


def _window_is_five(raw: object) -> bool:
    if raw is None:
        return True
    text_value = str(raw).strip()
    if text_value == "":
        return True
    return text_value in {"5", "5.0"}


def _query_filled(query: Mapping[str, str], name: str) -> bool:
    raw = query.get(name)
    return raw is not None and str(raw).strip() != ""


def _parse_day(raw: object) -> date | None:
    if not isinstance(raw, str) or len(raw) < 10:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _nonempty(raw: object) -> bool:
    if raw is None:
        return False
    if isinstance(raw, (list, tuple, set)):
        return len(raw) > 0
    if isinstance(raw, str):
        return raw.strip() != ""
    return True


def is_default_land_rolling(body: object) -> bool:
    """기본 조건 5년 롤링. 필터·3·7년·달력연도 모드는 아니다."""
    if not isinstance(body, dict):
        return False
    try:
        buckets = int(body.get("rolling_bucket_count"))
    except (TypeError, ValueError):
        return False
    if buckets != 5:
        return False
    start = _parse_day(body.get("rolling_matrix_period_start"))
    end = _parse_day(body.get("rolling_matrix_period_end"))
    if start is None or end is None or end <= start:
        return False
    span = (end - start).days
    if not (5 * 365 - 20 <= span <= 5 * 366 + 5):
        return False
    for key in (
        "road_conditions",
        "area_categories",
        "land_categories",
        "zone_types",
        "deal_types",
        "years",
    ):
        if _nonempty(body.get(key)):
            return False
    if body.get("exclude_partial") or body.get("exclude_outlier"):
        return False
    if _nonempty(body.get("year_from")) or _nonempty(body.get("year_to")):
        return False
    if body.get("area_sqm_min") is not None or body.get("area_sqm_max") is not None:
        return False
    return True


def _collective_list_is_free(query: Mapping[str, str]) -> bool:
    if not _window_is_five(query.get("window_years")):
        return False
    if _query_filled(query, "contract_year_from") or _query_filled(query, "contract_year_to"):
        return False
    mode = (query.get("presale_stats_mode") or "rolling").strip()
    return mode == "rolling"


def _rolling_is_free(query: Mapping[str, str]) -> bool:
    return _window_is_five(query.get("window_years"))


def _collective_open(method: str, path: str, query: Mapping[str, str]) -> bool:
    if method == "GET" and (
        path.startswith("/api/collective/regions/")
        or path == "/api/collective/meta/filters"
        or path.startswith("/api/collective/commercial/regions/")
        or path == "/api/collective/commercial/meta/filters"
    ):
        return True
    if method == "GET" and path == "/api/collective/buildings":
        return _collective_list_is_free(query)
    if method == "GET" and path == "/api/collective/commercial/clusters":
        return _collective_list_is_free(query)
    if method == "GET" and path.startswith("/api/collective/buildings/") and path.endswith("/stats/rolling"):
        return _rolling_is_free(query)
    if method == "GET" and path.startswith("/api/collective/commercial/clusters/") and path.endswith("/stats/rolling"):
        return _rolling_is_free(query)
    if method == "POST" and path in {
        "/api/collective/buildings/geocode",
        "/api/collective/buildings/map-points",
        "/api/collective/commercial/roads/geocode",
        "/api/collective/commercial/roads/map-points",
        "/api/collective/commercial/roads/line",
    }:
        return True
    return False


def needs_macro(
    method: str,
    path: str,
    query: Mapping[str, str],
    body: object = None,
) -> bool:
    """True 이면 매크로 구독이 있어야 한다."""
    if method == "OPTIONS":
        return False
    if path in {"/health", "/openapi.json", "/docs", "/redoc"}:
        return False
    for prefix in _ALWAYS_OPEN_PREFIXES:
        if path.startswith(prefix):
            return False
    if path.startswith("/api/free/v2/stats"):
        if method == "GET":
            return not _window_is_five(query.get("window_years"))
        if method == "POST" and path == "/api/free/v2/stats/bulk":
            window = 5
            if isinstance(body, dict) and body.get("window_years") is not None:
                window = body.get("window_years")
            return not _window_is_five(window)
        return True
    if path.startswith("/api/paid/upper-stats/") and method == "GET":
        return not _window_is_five(query.get("window_years"))
    if path == "/api/paid/matrix-yearly" and method == "POST":
        return not is_default_land_rolling(body)
    if path.startswith("/api/paid/"):
        return True
    if path.startswith("/api/collective/"):
        return not _collective_open(method, path, query)
    if path.startswith("/api/free/"):
        return True
    for prefix in _MACRO_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def caller_access(request: Request) -> str:
    """anonymous | login | macro. 플랫폼 DB를 못 읽으면 anonymous."""
    factory = get_platform_session_factory()
    if factory is None:
        return "anonymous"
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        return "anonymous"
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        return "anonymous"
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        return "anonymous"
    db = factory()
    try:
        row = db.execute(
            text("SELECT id FROM users WHERE id = :id"),
            {"id": user_id},
        ).first()
        if row is None:
            return "anonymous"
        ent = list_entitlements(db, user_id)
        if ent.get("macro"):
            return "macro"
        return "login"
    except Exception:
        return "anonymous"
    finally:
        db.close()


async def product_gate_response(request: Request) -> JSONResponse | None:
    body: object = None
    path = request.url.path
    if request.method == "POST" and path in {
        "/api/paid/matrix-yearly",
        "/api/free/v2/stats/bulk",
    }:
        raw = await request.body()
        if raw:
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                body = None
    if not needs_macro(request.method, path, request.query_params, body):
        return None
    access = caller_access(request)
    if access == "macro":
        return None
    if access == "login":
        return JSONResponse(status_code=403, content={"detail": _SUBSCRIBE})
    return JSONResponse(status_code=401, content={"detail": _LOGIN})
