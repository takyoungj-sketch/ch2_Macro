"""FastAPI 앱 진입점."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import free, paid

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


@app.get("/health", tags=["헬스체크"])
def health():
    return {"status": "ok"}
