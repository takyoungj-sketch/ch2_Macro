-- =============================================================================
-- 014: 장기 추세용 연도별 사전 집계 land_annual_stats
-- =============================================================================
-- 설계: docs/LONG_TERM_TREND_DESIGN.md
-- 적용: psql "$DATABASE_URL" -f db/014_land_annual_stats.sql
--
-- 그레인: (calendar_year, beopjungri_code, zone_type, land_category)
-- 집계 원칙: land_transactions 원장 직접 GROUP BY (V2·UPPER_STATS 와 동일)
-- =============================================================================

CREATE TABLE IF NOT EXISTS land_annual_stats (
    id                      BIGSERIAL PRIMARY KEY,

    calendar_year           SMALLINT        NOT NULL
                            CHECK (calendar_year >= 2000 AND calendar_year <= 2100),

    beopjungri_code         CHAR(10)        NOT NULL,

    zone_type               VARCHAR(20)     NOT NULL DEFAULT 'ALL',
    land_category           VARCHAR(10)     NOT NULL DEFAULT 'ALL',

    transaction_count       INTEGER         NOT NULL DEFAULT 0,

    mean_unit_price         NUMERIC(14, 2),
    median_unit_price       NUMERIC(14, 2),
    std_dev                 NUMERIC(14, 2),
    ci95_low                NUMERIC(14, 2),
    ci95_high               NUMERIC(14, 2),

    p10                     NUMERIC(14, 2),
    p25                     NUMERIC(14, 2),
    p75                     NUMERIC(14, 2),
    p90                     NUMERIC(14, 2),

    min_price               NUMERIC(14, 2),
    max_price               NUMERIC(14, 2),

    -- 집계에 사용한 contract_date 구간 (만년력 1·1 ~ 12·31)
    period_start            DATE            NOT NULL,
    period_end              DATE            NOT NULL,

    computed_at             TIMESTAMP       NOT NULL DEFAULT NOW(),
    batch_id                TEXT,

    CONSTRAINT land_annual_stats_period_chk
        CHECK (period_start <= period_end),

    CONSTRAINT land_annual_stats_grain_uq UNIQUE (
        calendar_year,
        beopjungri_code,
        zone_type,
        land_category
    )
);

COMMENT ON TABLE land_annual_stats IS
    '장기 추세: 달력 연도 × 법정동/리 × 용도×지목 단가 통계 (필터분석 장기 모달용)';
COMMENT ON COLUMN land_annual_stats.calendar_year IS
    '만년력 연도 — period_start/end 와 contract_date 로 정의 (필터분석 by_year 와 동일 축)';
COMMENT ON COLUMN land_annual_stats.beopjungri_code IS
    '현행 region_codes 기준 법정동/리 10자리 (행정 이력 remap 후 집계)';
COMMENT ON COLUMN land_annual_stats.zone_type IS
    '용도지역 원문 또는 ALL';
COMMENT ON COLUMN land_annual_stats.land_category IS
    '지목 원문 또는 ALL';

CREATE INDEX IF NOT EXISTS ix_las_beopjungri_year
    ON land_annual_stats (beopjungri_code, calendar_year DESC);

CREATE INDEX IF NOT EXISTS ix_las_year_beopjungri_zone_cat
    ON land_annual_stats (calendar_year, beopjungri_code, zone_type, land_category);

-- 행정구역 코드 이력 (장기 backfill·remap 선행 — 상세 docs/LONG_TERM_TREND_DESIGN.md §2)
CREATE TABLE IF NOT EXISTS region_code_history (
    id                  BIGSERIAL PRIMARY KEY,

    from_code           CHAR(10)     NOT NULL,
    to_code             CHAR(10)     NOT NULL,

    change_type         VARCHAR(20)  NOT NULL,
    -- merge | split | rename | boundary | code_reissue

    effective_from      DATE         NOT NULL,
    effective_to        DATE,

    source_note         TEXT,
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW(),

    CONSTRAINT region_code_history_type_chk
        CHECK (change_type IN ('merge', 'split', 'rename', 'boundary', 'code_reissue'))
);

COMMENT ON TABLE region_code_history IS
    '법정동 코드 변경 이력 — 원장 beopjungri_code 는 보존, 연도 마트 집계 시 remap 참조';

CREATE INDEX IF NOT EXISTS ix_region_code_history_from
    ON region_code_history (from_code, effective_from);

CREATE INDEX IF NOT EXISTS ix_region_code_history_to
    ON region_code_history (to_code, effective_from);
