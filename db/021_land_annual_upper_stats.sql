-- =============================================================================
-- 021: 장기 추세용 상위 행정구역 연도별 사전 집계 land_annual_upper_stats
-- =============================================================================
-- 설계: docs/LONG_TERM_TREND_DESIGN.md §P5 · land_upper_stats_v2 레벨 정렬
-- 적용: psql "$DATABASE_URL" -f db/021_land_annual_upper_stats.sql
--
-- 그레인: (calendar_year, region_level, region_code, zone_type, land_category)
-- =============================================================================

CREATE TABLE IF NOT EXISTS land_annual_upper_stats (
    id                      BIGSERIAL PRIMARY KEY,

    calendar_year           SMALLINT        NOT NULL
                            CHECK (calendar_year >= 2000 AND calendar_year <= 2100),

    region_level            VARCHAR(12)     NOT NULL,
    region_code             VARCHAR(10)     NOT NULL,

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

    period_start            DATE            NOT NULL,
    period_end              DATE            NOT NULL,

    computed_at             TIMESTAMP       NOT NULL DEFAULT NOW(),
    batch_id                TEXT,

    CONSTRAINT land_annual_upper_stats_level_chk
        CHECK (region_level IN ('sido', 'sigungu', 'eupmyeondong', 'city')),

    CONSTRAINT land_annual_upper_stats_period_chk
        CHECK (period_start <= period_end),

    CONSTRAINT land_annual_upper_stats_grain_uq UNIQUE (
        calendar_year,
        region_level,
        region_code,
        zone_type,
        land_category
    )
);

COMMENT ON TABLE land_annual_upper_stats IS
    '장기 추세: 만년력 연도 × 상위 행정(시도·시군구·읍면동·city) × 용도×지목';

CREATE INDEX IF NOT EXISTS ix_laus_level_code_year
    ON land_annual_upper_stats (region_level, region_code, calendar_year DESC);

CREATE INDEX IF NOT EXISTS ix_laus_year_level_code_zone_cat
    ON land_annual_upper_stats (
        calendar_year, region_level, region_code, zone_type, land_category
    );

-- VPS 운영 DB 사용자(ch2app) 조회 권한 — DDL 적용 직후 1회
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ch2app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON land_annual_upper_stats TO ch2app;
    END IF;
END $$;
