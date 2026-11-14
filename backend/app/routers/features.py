"""GET /api/features — 이 요청자에게 켜진 기능 이름 (D-085).

꺼진 기능 이름은 주지 않는다. 응답은 사람마다 다르므로 저장하지 않게 한다.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.feature_gates import enabled_features, private_features

router = APIRouter(tags=["features"])


@router.get("/features")
def list_features(request: Request, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Vary"] = "Cookie, Authorization"
    return {
        "features": enabled_features(request),
        # 관리자에게만 차는 값: 켜져 있지만 아직 비공개인 기능(배지용).
        "private": private_features(request),
    }
