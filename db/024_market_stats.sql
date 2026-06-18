-- =============================================================================
-- 024: Market Stats — region × market_domain × window (Profile 입력)
-- =============================================================================
-- 설계: docs/REGIONAL_PROFILE_ARCHITECTURE.md Phase B

CREATE TABLE IF NOT EXISTS market_stats (
    id                  BIGSERIAL PRIMARY KEY,

    market_domain       VARCHAR(32)     NOT NULL,
    region_level        VARCHAR(12)     NOT NULL,
    region_code         VARCHAR(10)     NOT NULL,

    as_of_month         DATE            NOT NULL,
    window_years        SMALLINT        NOT NULL
                        CHECK (window_years >= 1 AND window_years <= 5),
    period_start        DATE            NOT NULL,
    period_end          DATE            NOT NULL,

    count               INTEGER         NOT NULL DEFAULT 0,
    mean                NUMERIC(14, 2),
    std                 NUMERIC(14, 2),
    ci_lower            NUMERIC(14, 2),
    ci_upper            NUMERIC(14, 2),
    p25                 NUMERIC(14, 2),
    median              NUMERIC(14, 2),
    p75                 NUMERIC(14, 2),
    yoy                 NUMERIC(10, 4),
    volatility          NUMERIC(10, 4),

    computed_at         TIMESTAMP       NOT NULL DEFAULT NOW(),
    batch_id            TEXT,

    CONSTRAINT market_stats_period_chk
        CHECK (period_start <= period_end),

    CONSTRAINT market_stats_as_of_first_of_month_chk
        CHECK (DATE_TRUNC('month', as_of_month)::DATE = as_of_month),

    CONSTRAINT market_stats_grain_uq UNIQUE (
        market_domain,
        region_level,
        region_code,
        as_of_month,
        window_years
    )
);

COMMENT ON TABLE market_stats IS
    '지역 시장 통계 — market_domain × region × 롤링 창 (Profile·쌍둥이 입력)';

CREATE INDEX IF NOT EXISTS ix_market_stats_lookup
    ON market_stats (market_domain, region_level, as_of_month DESC, window_years);

CREATE INDEX IF NOT EXISTS ix_market_stats_code
    ON market_stats (region_level, region_code, as_of_month DESC, window_years);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS market_annual_stats (
    id                  BIGSERIAL PRIMARY KEY,

    market_domain       VARCHAR(32)     NOT NULL,
    region_level        VARCHAR(12)     NOT NULL,
    region_code         VARCHAR(10)     NOT NULL,
    calendar_year       SMALLINT        NOT NULL,

    count               INTEGER         NOT NULL DEFAULT 0,
    mean                NUMERIC(14, 2),
    median              NUMERIC(14, 2),
    std                 NUMERIC(14, 2),

    computed_at         TIMESTAMP       NOT NULL DEFAULT NOW(),
    batch_id            TEXT,

    CONSTRAINT market_annual_stats_grain_uq UNIQUE (
        market_domain,
        region_level,
        region_code,
        calendar_year
    )
);

COMMENT ON TABLE market_annual_stats IS
    'Market domain × region × 달력연도 — 장기 추세·yoy 보조';

CREATE INDEX IF NOT EXISTS ix_market_annual_domain_year
    ON market_annual_stats (market_domain, calendar_year);
