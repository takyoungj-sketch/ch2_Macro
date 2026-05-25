-- =============================================================================
-- 토지 실거래 통계 웹서비스 MVP - 초기 스키마
-- PostgreSQL 14+
-- =============================================================================

-- 확장
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- 1. 지역 코드 테이블
-- =============================================================================
CREATE TABLE IF NOT EXISTS region_codes (
    id              SERIAL PRIMARY KEY,
    sido_code       CHAR(2)      NOT NULL,          -- 시도 코드 (2자리)
    sido_name       VARCHAR(20)  NOT NULL,
    sigungu_code    CHAR(5)      NOT NULL,          -- 시군구 코드 (5자리)
    sigungu_name    VARCHAR(30)  NOT NULL,
    eupmyeondong_code CHAR(8)    NOT NULL,          -- 읍면동 코드 (8자리)
    eupmyeondong_name VARCHAR(30) NOT NULL,
    beopjungri_code CHAR(10)     NOT NULL,          -- 법정리 코드 (10자리, 동 단위는 8자리+00)
    beopjungri_name VARCHAR(30)  NOT NULL,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    updated_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_region_codes_beopjungri
    ON region_codes (beopjungri_code);

COMMENT ON TABLE region_codes IS '행정/법정 구역 코드 참조 테이블';
COMMENT ON COLUMN region_codes.beopjungri_code IS '법정동/리 코드 10자리 (동=8자리+00)';

-- =============================================================================
-- 2. 원자료 보존 테이블 (국토부 Excel 원본 → 적재)
-- =============================================================================
CREATE TABLE IF NOT EXISTS land_transactions_raw (
    id              BIGSERIAL PRIMARY KEY,
    source_year     SMALLINT     NOT NULL,           -- 공공데이터 기준 연도
    source_month    SMALLINT     NOT NULL,           -- 공공데이터 기준 월
    raw_data        JSONB        NOT NULL,           -- 원본 행 그대로 JSON 보존
    loaded_at       TIMESTAMP    NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE land_transactions_raw IS '국토부 원천 Excel 원본 보존 (정제 전)';

-- =============================================================================
-- 3. 분석용 정규화 테이블
-- =============================================================================
CREATE TABLE IF NOT EXISTS land_transactions (
    id                      BIGSERIAL PRIMARY KEY,
    transaction_hash        CHAR(64)     NOT NULL,   -- SHA-256 중복 방지
    -- 거래 기본 정보
    contract_year           SMALLINT     NOT NULL,
    contract_month          SMALLINT     NOT NULL,
    contract_date           DATE,
    -- 지역 코드
    beopjungri_code         CHAR(10)     NOT NULL,
    sido_code               CHAR(2)      NOT NULL,
    sigungu_code            CHAR(5)      NOT NULL,
    -- 토지 특성
    land_category           VARCHAR(10),             -- 지목 (전, 답, 대, 임야 등)
    zone_type               VARCHAR(20),             -- 용도지역
    road_condition          VARCHAR(20),             -- 도로조건
    area_sqm                NUMERIC(12,2),           -- 계약면적 (㎡)
    area_category           VARCHAR(10),             -- 면적구분 (광소/정상/광대)
    -- 가격
    total_price_10k         NUMERIC(14,2) NOT NULL,  -- 거래금액 (만원)
    unit_price_per_sqm      NUMERIC(14,2),           -- 단가 (만원/㎡) = total_price_10k / area
    -- 목록·참고 표시 (원천 엑셀/API에서 정제 시 채움)
    lot_display               VARCHAR(64),
    partial_ownership_label   VARCHAR(128),
    deal_type                 VARCHAR(128),
    -- 지분거래
    is_partial_ownership    BOOLEAN      NOT NULL DEFAULT FALSE,
    -- 정제 상태
    is_cancelled            BOOLEAN      NOT NULL DEFAULT FALSE,  -- 해제거래
    is_valid                BOOLEAN      NOT NULL DEFAULT TRUE,
    -- 메타
    raw_id                  BIGINT REFERENCES land_transactions_raw(id),
    created_at              TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_land_tx_hash
    ON land_transactions (transaction_hash);

CREATE INDEX IF NOT EXISTS ix_land_tx_beopjungri
    ON land_transactions (beopjungri_code);

CREATE INDEX IF NOT EXISTS ix_land_tx_sigungu
    ON land_transactions (sigungu_code);

CREATE INDEX IF NOT EXISTS ix_land_tx_year_month
    ON land_transactions (contract_year, contract_month);

CREATE INDEX IF NOT EXISTS ix_land_tx_filters
    ON land_transactions (beopjungri_code, contract_year, road_condition, area_category, land_category, zone_type);

COMMENT ON TABLE land_transactions IS '분석용 정규화 토지 실거래 테이블';
COMMENT ON COLUMN land_transactions.transaction_hash IS 'SHA-256(시군구+계약일+지번+면적+금액) 중복 방지';
COMMENT ON COLUMN land_transactions.is_partial_ownership IS '지분거래 여부 (분자/분모 형태 소유권)';

-- =============================================================================
-- 4. 무료 기본 통계 사전 집계 테이블
-- =============================================================================
-- 집계 기준: 법정동/리 × 용도지역 × 지목 (기본 5년, 정상 데이터, 지분거래 포함)
CREATE TABLE IF NOT EXISTS land_basic_stats (
    id                  BIGSERIAL PRIMARY KEY,
    beopjungri_code     CHAR(10)     NOT NULL,
    zone_type           VARCHAR(20)  NOT NULL DEFAULT 'ALL',   -- 'ALL' 또는 특정 용도지역
    land_category       VARCHAR(10)  NOT NULL DEFAULT 'ALL',   -- 'ALL' 또는 특정 지목
    -- 통계 항목
    count               INTEGER      NOT NULL DEFAULT 0,
    mean                NUMERIC(14,2),
    std                 NUMERIC(14,2),
    ci_lower            NUMERIC(14,2),
    ci_upper            NUMERIC(14,2),
    p_min               NUMERIC(14,2),
    p25                 NUMERIC(14,2),
    median              NUMERIC(14,2),
    p75                 NUMERIC(14,2),
    p_max               NUMERIC(14,2),
    -- 집계 범위
    year_from           SMALLINT     NOT NULL,
    year_to             SMALLINT     NOT NULL,
    -- 메타
    computed_at         TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_basic_stats_key
    ON land_basic_stats (beopjungri_code, zone_type, land_category, year_from, year_to);

CREATE INDEX IF NOT EXISTS ix_basic_stats_beopjungri
    ON land_basic_stats (beopjungri_code);

COMMENT ON TABLE land_basic_stats IS '무료 화면용 동/리 단위 사전 집계 (빠른 조회)';

-- =============================================================================
-- 5. 유료 분석 사용 기록
-- =============================================================================
CREATE TABLE IF NOT EXISTS paid_analysis_logs (
    id              BIGSERIAL PRIMARY KEY,
    session_id      UUID         NOT NULL DEFAULT uuid_generate_v4(),
    user_id         VARCHAR(100),                    -- 추후 인증 연동 시 사용
    -- 쿼리 조건
    region_codes    TEXT[]       NOT NULL,           -- 선택한 법정동/리 코드 목록
    year_from       SMALLINT,
    year_to         SMALLINT,
    road_conditions TEXT[],
    area_categories TEXT[],
    land_categories TEXT[],
    zone_types      TEXT[],
    exclude_partial BOOLEAN      NOT NULL DEFAULT FALSE,
    exclude_outlier BOOLEAN      NOT NULL DEFAULT FALSE,
    -- 결과 요약
    result_count    INTEGER,
    response_ms     INTEGER,                         -- 응답 시간 (ms)
    -- 메타
    requested_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
    ip_address      INET
);

COMMENT ON TABLE paid_analysis_logs IS '유료 동적 분석 사용 기록 (캐시 전략 및 과금 근거)';

-- =============================================================================
-- 6. 캐시 테이블 (자주 조회되는 유료 쿼리 결과 임시 저장)
-- =============================================================================
CREATE TABLE IF NOT EXISTS analysis_cache (
    cache_key       VARCHAR(255) PRIMARY KEY,        -- SHA-256(정렬된 쿼리 파라미터)
    result_json     JSONB        NOT NULL,
    hit_count       INTEGER      NOT NULL DEFAULT 1,
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMP    NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_cache_expires
    ON analysis_cache (expires_at);

COMMENT ON TABLE analysis_cache IS '자주 반복되는 유료 분석 쿼리 결과 캐시';

-- =============================================================================
-- 7. 행정구역별 인구 (추후 지도 레이어용, MVP에서는 비어 있음)
-- =============================================================================
CREATE TABLE IF NOT EXISTS population_stats (
    id                  BIGSERIAL PRIMARY KEY,
    stats_year          SMALLINT     NOT NULL,
    stats_month         SMALLINT,
    admin_code          VARCHAR(10)  NOT NULL,      -- 법정동/행정동 등 연계 코드
    admin_level         VARCHAR(20)  NOT NULL,      -- beopjungri | haengjeongdong 등
    total_population    INTEGER,
    household_count     INTEGER,
    pop_change_rate     NUMERIC(8, 4),
    density_per_km2     NUMERIC(14, 4),
    source              VARCHAR(80),
    loaded_at           TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_pop_stats_admin
    ON population_stats (admin_code, stats_year);

COMMENT ON TABLE population_stats IS '추후 행정구역 인구 레이어 (행안부·KOSIS·SGIS 등 연동)';
