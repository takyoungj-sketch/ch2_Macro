-- =============================================================================
-- 010: V2 상위 행정구역 사전 집계 land_upper_stats_v2
-- =============================================================================
-- 설계: docs/UPPER_STATS_DESIGN.md
-- 적용: psql "$DATABASE_URL" -f db/010_land_upper_stats_v2.sql

CREATE TABLE IF NOT EXISTS land_upper_stats_v2 (
    id             BIGSERIAL PRIMARY KEY,

    region_level   VARCHAR(12)  NOT NULL,
    region_code    VARCHAR(10)  NOT NULL,

    as_of_month    DATE         NOT NULL,
    window_years   SMALLINT     NOT NULL
                   CHECK (window_years >= 1 AND window_years <= 5),
    period_start   DATE         NOT NULL,
    period_end     DATE         NOT NULL,

    zone_type      VARCHAR(20)  NOT NULL DEFAULT 'ALL',
    land_category  VARCHAR(10)  NOT NULL DEFAULT 'ALL',

    count          INTEGER      NOT NULL DEFAULT 0,
    mean           NUMERIC(14, 2),
    std            NUMERIC(14, 2),
    ci_lower       NUMERIC(14, 2),
    ci_upper       NUMERIC(14, 2),
    p_min          NUMERIC(14, 2),
    p25            NUMERIC(14, 2),
    median         NUMERIC(14, 2),
    p75            NUMERIC(14, 2),
    p_max          NUMERIC(14, 2),

    computed_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
    batch_id       TEXT,

    CONSTRAINT land_upper_stats_v2_period_chk
        CHECK (period_start <= period_end),

    CONSTRAINT land_upper_stats_v2_as_of_first_of_month_chk
        CHECK (DATE_TRUNC('month', as_of_month)::DATE = as_of_month),

    CONSTRAINT land_upper_stats_v2_grain_uq UNIQUE (
        region_level,
        region_code,
        as_of_month,
        window_years,
        zone_type,
        land_category
    )
);

COMMENT ON TABLE land_upper_stats_v2 IS
    'V2: 시도·시군구·읍면동 단위 단가 통계 사전집계 (원장 직접 GROUP BY)';
COMMENT ON COLUMN land_upper_stats_v2.region_level IS 'sido | sigungu | eupmyeondong';
COMMENT ON COLUMN land_upper_stats_v2.region_code IS
    'sido 2자리, sigungu 5자리, eupmyeondong 8자리';

CREATE INDEX IF NOT EXISTS ix_lus_v2_level_code_asof_window
    ON land_upper_stats_v2 (region_level, region_code, as_of_month DESC, window_years);

CREATE INDEX IF NOT EXISTS ix_lus_v2_asof_window_level
    ON land_upper_stats_v2 (as_of_month, window_years, region_level, region_code);

-- DOWN
-- DROP INDEX IF EXISTS ix_lus_v2_asof_window_level;
-- DROP INDEX IF EXISTS ix_lus_v2_level_code_asof_window;
-- DROP TABLE IF EXISTS land_upper_stats_v2;
