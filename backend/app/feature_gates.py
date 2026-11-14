"""관리자 전용 기능 스위치 (D-085).

개선 중인 기능을 관리자에게만 열고, 사용자에게는 숨긴다. 공개는 환경변수 하나로 한다.

- 모드: ``public``(모두) · ``admin``(관리자만, 기본) · ``off``(관리자도 닫음)
- 덮어쓰기: ``FEATURE_<NAME>=public|admin|off`` (예 ``FEATURE_RENT_REGRESSION=public``).
  프로세스 환경변수가 먼저, 없으면 ``backend/.env``(settings). 비었거나 모르는 값이면 기본값.
- 관리자: 로그인 ``users.role == "admin"`` 또는 QA 토큰(`X-Qa-Audit-Token`) 일치.
  `/lab/` Nginx Basic Auth(D-061)와는 별개다.

공개 절차: ``docs/ops/FEATURE_GATES.md``.
"""

from __future__ import annotations

import os
from typing import Callable

from fastapi import HTTPException, Request

RENT_REGRESSION = "rent_regression"
LAND_REGRESSION = "land_regression"
LAND_LEDGER_LINK = "land_ledger_link"

MODES = ("public", "admin", "off")

# 이름 → 기본 모드. 새 스위치는 여기에만 추가한다.
FEATURES: dict[str, str] = {
    RENT_REGRESSION: "admin",
    LAND_REGRESSION: "admin",
    LAND_LEDGER_LINK: "admin",
}

HIDDEN_DETAIL = "아직 공개하지 않은 기능입니다."

_STATE_KEY = "ch2_is_admin"


def feature_mode(name: str) -> str:
    """프로세스 환경변수 → backend/.env(settings) → 기본값 순."""
    if name not in FEATURES:
        raise KeyError(name)
    raw = os.getenv(f"FEATURE_{name.upper()}")
    if raw is None:
        from app.config import settings

        raw = getattr(settings, f"feature_{name}", "") or ""
    raw = raw.strip().lower()
    return raw if raw in MODES else FEATURES[name]


def is_admin(request: Request) -> bool:
    """요청마다 한 번만 판정한다(request.state 에 저장)."""
    state = getattr(request, "state", None)
    cached = getattr(state, _STATE_KEY, None) if state is not None else None
    if cached is not None:
        return bool(cached)
    from app.admin_auth import _token_ok, caller_role

    try:
        ok = _token_ok(request) or caller_role(request) == "admin"
    except Exception:  # noqa: BLE001 — 판정 실패는 비관리자로 본다
        ok = False
    if state is not None:
        try:
            setattr(state, _STATE_KEY, ok)
        except Exception:  # noqa: BLE001
            pass
    return ok


def feature_enabled(request: Request, name: str) -> bool:
    mode = feature_mode(name)
    if mode == "public":
        return True
    if mode == "off":
        return False
    return is_admin(request)


def enabled_features(request: Request) -> list[str]:
    return [name for name in FEATURES if feature_enabled(request, name)]


def private_features(request: Request) -> list[str]:
    """켜져 있지만 아직 관리자 전용인 기능(관리자 화면의 「비공개」 배지용)."""
    return [
        name
        for name in FEATURES
        if feature_mode(name) == "admin" and feature_enabled(request, name)
    ]


def gate_profile(request: Request) -> str:
    """권한별 응답 캐시 키에 넣는 값. 켜진 스위치 이름을 정렬해 잇는다."""
    return ",".join(sorted(enabled_features(request)))


def ensure_feature(request: Request, name: str) -> None:
    if not feature_enabled(request, name):
        raise HTTPException(403, HIDDEN_DETAIL)


def require_feature(name: str) -> Callable[[Request], None]:
    """FastAPI 라우트 의존성. 라우트 데코레이터 ``dependencies=[...]`` 에 걸어
    DB 세션·조회 마감(임대 90초)보다 먼저 403 을 낸다."""
    if name not in FEATURES:
        raise KeyError(name)

    def _dep(request: Request) -> None:
        ensure_feature(request, name)

    _dep.__name__ = f"require_feature_{name}"
    return _dep


# product_gate 경로 규칙(라우트 의존성의 이중 방어). (메서드, 판정 함수, 스위치)
def _rent_regression_path(path: str) -> bool:
    if path == "/api/rent/regression/run":
        return True
    return path.startswith("/api/rent/buildings/") and path.endswith("/regression/run")


_LAND_REGRESSION_PATHS = frozenset(
    {
        "/api/paid/matrix-cell-transactions/regression",
        "/api/paid/matrix-cell-transactions/regression/suggest",
        "/api/paid/matrix-cell-transactions/regression/predict",
    }
)


def gated_feature_for_path(method: str, path: str) -> str | None:
    if method != "POST":
        return None
    if _rent_regression_path(path):
        return RENT_REGRESSION
    if path in _LAND_REGRESSION_PATHS:
        return LAND_REGRESSION
    return None
