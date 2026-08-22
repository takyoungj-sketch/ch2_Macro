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
    #: built_stats (복합부동산 연구 MVP). 비어 있으면 /api/built 라우터 미등록.
    built_database_url: str = Field(
        default="",
        validation_alias="BUILT_DATABASE_URL",
    )
    #: collective_stats (집합부동산 MVP). 비어 있으면 /api/collective 라우터 미등록.
    collective_database_url: str = Field(
        default="",
        validation_alias="COLLECTIVE_DATABASE_URL",
    )
    #: 로컬 대장DB parcel_master. 비어 있으면 collective URL의 형제 DB명을 시도.
    #: 없거나 연결 실패면 관리자 대장 조회는 503. VPS에 올리지 않는다.
    parcel_master_database_url: str = Field(
        default="",
        validation_alias="PARCEL_MASTER_DATABASE_URL",
    )
    #: rent_stats (주거 전월세 원장). 비어 있으면 임대 라우터 미등록(후속).
    rent_database_url: str = Field(
        default="",
        validation_alias="RENT_DATABASE_URL",
    )
    secret_key: str = "change_me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175,http://localhost:5176,http://localhost:5177,http://localhost:5178,http://127.0.0.1:5173,http://127.0.0.1:5176,http://127.0.0.1:5177,http://127.0.0.1:5178"
    #: 필터 분석 percentile 정렬용 work_mem(MB). 너무 작으면 디스크 스필로 매우 느려질 수 있음.
    paid_analyze_work_mem_mb: int = 192

    #: DECISIONS D-007 — 비어 있으면 인증 미들웨어 비활성. 값이 있으면 비-/health 요청은
    #: `X-Api-Token: <값>` 헤더가 필요하다. 결제·로그인 도입 전 1단 보호용.
    api_token: str = ""
    #: 관리자 QA 검증 API (`/api/admin/qa/*`). 비어 있으면 통과(로컬).
    #: 값이 있으면 `X-Qa-Audit-Token` 필요. 공개 앱과 분리.
    qa_audit_token: str = Field(default="", validation_alias="QA_AUDIT_TOKEN")

    #: 무료 V2 API: 요청에 as_of_month 없을 때. None 이면 요청 시점 기준 직전 달 1일(§3).
    stats_v2_default_as_of_month: Optional[date] = Field(
        default=None,
        validation_alias="STATS_V2_DEFAULT_AS_OF_MONTH",
        description="고정 시 우선. 미설정 시 동적 직전 달(as_of_month_for_service)",
    )
    #: 로컬·검증: «오늘» 대신 이 날짜로 직전 달 as_of_month 를 계산. 예: 2026-01-01 → 2025-12-01.
    #: stats_v2_default_as_of_month 가 있으면 그쪽이 우선(이 필드는 무시).
    stats_v2_assumed_today: Optional[date] = Field(
        default=None,
        validation_alias="STATS_V2_ASSUMED_TODAY",
        description="통계 기준일 가정(STATS_V2_ASSUMED_TODAY)",
    )

    #: CH2 AI — OpenAI (비어 있으면 템플릿·Explain presets 모드)
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5-mini", validation_alias="OPENAI_MODEL")
    ai_session_ttl_seconds: int = Field(default=86400, validation_alias="AI_SESSION_TTL_SECONDS")
    ai_rate_limit_per_minute: int = Field(default=30, validation_alias="AI_RATE_LIMIT_PER_MINUTE")
    #: CH2 AI — 템플릿 내러티브 OpenAI polish (OPENAI_API_KEY 필요)
    ai_polish_enabled: bool = Field(default=False, validation_alias="AI_POLISH_ENABLED")
    #: 실험 — 일상 대화 톤·인사 허용 (사실·수치는 CH2 지식·Bundle만)
    ai_casual_dialogue_enabled: bool = Field(
        default=True,
        validation_alias="AI_CASUAL_DIALOGUE_ENABLED",
    )
    #: 개발·검증 — 라우팅/템플릿 우회, LLM 우선 (화면 facts는 soft cite만)
    ai_open_mode: bool = Field(
        default=False,
        validation_alias="AI_OPEN_MODE",
    )
    #: 실험 — 서버 전체 월 LLM 호출 상한. 0이면 횟수 한도 없음.
    ai_monthly_call_limit: int = Field(default=200, validation_alias="AI_MONTHLY_CALL_LIMIT")
    #: 실험 — 서버 전체 월 추정 원 상한. 0이면 비용 한도 없음.
    ai_monthly_budget_krw: float = Field(default=10000, validation_alias="AI_MONTHLY_BUDGET_KRW")
    ai_usd_krw: float = Field(default=1400, validation_alias="AI_USD_KRW")
    ai_usage_log_dir: str = Field(default="", validation_alias="AI_USAGE_LOG_DIR")
    #: CH2 AI — Tavily 웹 검색 (없으면 DuckDuckGo Instant 폴백)
    tavily_api_key: str = Field(default="", validation_alias="TAVILY_API_KEY")
    #: 카카오 Local API (FieldNote 주소 지오코딩 프록시)
    kakao_rest_api_key: str = Field(default="", validation_alias="KAKAO_REST_API_KEY")
    #: VWorld 2D API (Map Hub 타일·행정경계 Data API)
    vworld_api_key: str = Field(default="", validation_alias="VWORLD_API_KEY")
    vworld_api_domain: str = Field(default="localhost", validation_alias="VWORLD_API_DOMAIN")

    #: ch2_platform — 통합 회원·게시판·구독 (Macro 통계 DB와 분리)
    platform_database_url: str = Field(default="", validation_alias="DATABASE_URL_PLATFORM")
    google_client_id: str = Field(default="", validation_alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", validation_alias="GOOGLE_CLIENT_SECRET")
    google_oauth_redirect_uri: str = Field(
        default="https://ch2data.com/api/auth/google/callback",
        validation_alias="GOOGLE_OAUTH_REDIRECT_URI",
    )
    platform_cookie_domain: str = Field(default=".ch2data.com", validation_alias="PLATFORM_COOKIE_DOMAIN")
    platform_cookie_secure: bool = Field(default=True, validation_alias="PLATFORM_COOKIE_SECURE")
    fieldnote_ai_monthly_quota: int = Field(default=50, validation_alias="FIELDNOTE_AI_MONTHLY_QUOTA")
    #: 단문/장문/주소표 분리 한도 (클라와 맞춤). legacy fieldnote_ai_monthly_quota는 하위호환용.
    fieldnote_ai_short_monthly_quota: int = Field(
        default=100, validation_alias="FIELDNOTE_AI_SHORT_MONTHLY_QUOTA"
    )
    fieldnote_ai_long_monthly_quota: int = Field(
        default=50, validation_alias="FIELDNOTE_AI_LONG_MONTHLY_QUOTA"
    )
    fieldnote_ai_sheet_monthly_quota: int = Field(
        default=40, validation_alias="FIELDNOTE_AI_SHEET_MONTHLY_QUOTA"
    )
    fieldnote_ai_short_pro_monthly_quota: int = Field(
        default=500, validation_alias="FIELDNOTE_AI_SHORT_PRO_MONTHLY_QUOTA"
    )
    fieldnote_ai_long_pro_monthly_quota: int = Field(
        default=250, validation_alias="FIELDNOTE_AI_LONG_PRO_MONTHLY_QUOTA"
    )
    fieldnote_ai_sheet_pro_monthly_quota: int = Field(
        default=200, validation_alias="FIELDNOTE_AI_SHEET_PRO_MONTHLY_QUOTA"
    )
    #: 토스페이먼츠 웹훅 서명 검증용 (Phase 3)
    toss_webhook_secret: str = Field(default="", validation_alias="TOSS_WEBHOOK_SECRET")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()
