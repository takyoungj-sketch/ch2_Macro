"""FastAPI 앱 진입점."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import free, paid

logging.basicConfig(level=logging.INFO)


app = FastAPI(
    title="토지 실거래 통계 API",
    description="감정평가사용 토지 실거래 통계 웹서비스 MVP",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(free.router, prefix="/api")
app.include_router(paid.router, prefix="/api")


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


@app.get("/health", tags=["헬스체크"])
def health():
    return {"status": "ok"}
