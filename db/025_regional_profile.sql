-- =============================================================================
-- 025: Regional Profile — Feature Vector (건물 미포함) · 데이터 제품(Data Product)
-- =============================================================================
-- 설계: docs/REGIONAL_PROFILE_ARCHITECTURE.md Layer 4 / Phase D (D-017)
-- 원칙: Profile은 회귀·쌍둥이·AI가 공통 소비 → 버전·메타로 재현성을 보장한다.

CREATE TABLE IF NOT EXISTS regional_profile (
    id                  BIGSERIAL PRIMARY KEY,

    -- 데이터 제품 식별 (D-017)
    profile_version     VARCHAR(16)     NOT NULL DEFAULT 'v1.0',  -- Feature 셋 정의 버전
    region_level        VARCHAR(12)     NOT NULL,
    region_code         VARCHAR(10)     NOT NULL,
    as_of_month         DATE            NOT NULL,
    window_years        SMALLINT        NOT NULL DEFAULT 5
                        CHECK (window_years >= 1 AND window_years <= 5),

    features            JSONB           NOT NULL DEFAULT '{}'::jsonb,

    -- 메타데이터 (QA·드리프트·재현성)
    feature_count       INTEGER,                          -- 벡터 차원 수
    builder_version     TEXT,                             -- 빌더 코드 버전/날짜
    validation_status   VARCHAR(12)     NOT NULL DEFAULT 'PENDING'
                        CHECK (validation_status IN ('PENDING', 'PASS', 'FAIL')),

    computed_at         TIMESTAMP       NOT NULL DEFAULT NOW(),
    batch_id            TEXT,

    CONSTRAINT regional_profile_as_of_first_of_month_chk
        CHECK (DATE_TRUNC('month', as_of_month)::DATE = as_of_month),

    -- 고유 grain: 버전·창을 포함 → v1/v2, 3년/5년 공존(silent overwrite 방지)
    CONSTRAINT regional_profile_grain_uq UNIQUE (
        profile_version,
        region_level,
        region_code,
        as_of_month,
        window_years
    )
);

COMMENT ON TABLE regional_profile IS
    '지역 Feature Vector(데이터 제품) — market_stats + population 등 JOIN 결과. 소비자는 (profile_version, as_of_month, window_years) 명시 조회';

CREATE INDEX IF NOT EXISTS ix_regional_profile_lookup
    ON regional_profile (profile_version, region_level, region_code, as_of_month DESC, window_years);

CREATE INDEX IF NOT EXISTS ix_regional_profile_features_gin
    ON regional_profile USING gin (features);
