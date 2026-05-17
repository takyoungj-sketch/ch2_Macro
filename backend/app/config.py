from datetime import date
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# uvicorn 실행 CWD 가 backend 가 아니어도 backend/.env 를 읽도록 고정
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )
    database_url: str = "postgresql+psycopg2://postgres:password@localhost:5432/land_stats"
    secret_key: str = "change_me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175"
    #: 필터 분석 percentile 정렬용 work_mem(MB). 너무 작으면 디스크 스필로 매우 느려질 수 있음.
    paid_analyze_work_mem_mb: int = 192

    #: DECISIONS D-007 — 비어 있으면 인증 미들웨어 비활성. 값이 있으면 비-/health 요청은
    #: `X-Api-Token: <값>` 헤더가 필요하다. 결제·로그인 도입 전 1단 보호용.
    api_token: str = ""

    #: 무료 V2 API: 요청에 as_of_month 없을 때. None 이면 요청 시점 기준 직전 달 1일(§3).
    stats_v2_default_as_of_month: Optional[date] = Field(
        default=None,
        description="고정 시 우선. 미설정 시 동적 직전 달(as_of_month_for_service)",
    )
    #: 로컬·검증: «오늘» 대신 이 날짜로 직전 달 as_of_month 를 계산. 예: 2026-01-01 → 2025-12-01.
    #: stats_v2_default_as_of_month 가 있으면 그쪽이 우선(이 필드는 무시).
    stats_v2_assumed_today: Optional[date] = Field(
        default=None,
        description="통계 기준일 가정(STATS_V2_ASSUMED_TODAY)",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()
