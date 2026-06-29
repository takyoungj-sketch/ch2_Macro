-- =============================================================================
-- 032: 집합상가·집합공장 cluster stats — mart / rolling / annual
-- =============================================================================
-- Grain: cluster_key × as_of_month × window_years (mart) / cluster_key × year (annual)

CREATE TABLE IF NOT EXISTS collective_commercial_cluster_stats (
    id                  BIGSERIAL PRIMARY KEY,

    as_of_month         DATE            NOT NULL,
    window_years        SMALLINT        NOT NULL
                        CHECK (window_years >= 1 AND window_years <= 5),
    period_start        DATE            NOT NULL,
    period_end          DATE            NOT NULL,

    cluster_key         CHAR(64)        NOT NULL,
    asset_type          VARCHAR(24)     NOT NULL,
    display_label       VARCHAR(200)    NOT NULL,

    addr1               VARCHAR(30),
    addr2               VARCHAR(30),
    addr3               VARCHAR(30),
    addr4               VARCHAR(30),
    road_name           VARCHAR(120),
    zone_type           VARCHAR(40),
    building_use        VARCHAR(40),
    building_year       SMALLINT,
    area_bucket_label   VARCHAR(32),
    resolution_mode     VARCHAR(16),
    confidence_tier     VARCHAR(8),

    count               INTEGER         NOT NULL DEFAULT 0,
    mean                NUMERIC(14, 2),
    std                 NUMERIC(14, 2),
    ci_lower            NUMERIC(14, 2),
    ci_upper            NUMERIC(14, 2),
    p_min               NUMERIC(14, 2),
    p25                 NUMERIC(14, 2),
    median              NUMERIC(14, 2),
    p75                 NUMERIC(14, 2),
    p_max               NUMERIC(14, 2),

    computed_at         TIMESTAMP       NOT NULL DEFAULT NOW(),
    batch_id            TEXT,

    CONSTRAINT collective_commercial_cluster_stats_period_chk
        CHECK (period_start <= period_end),

    CONSTRAINT collective_commercial_cluster_stats_as_of_first_of_month_chk
        CHECK (DATE_TRUNC('month', as_of_month)::DATE = as_of_month),

    CONSTRAINT collective_commercial_cluster_stats_grain_uq UNIQUE (
        as_of_month,
        window_years,
        cluster_key,
        asset_type
    )
);

COMMENT ON TABLE collective_commercial_cluster_stats IS
    '집합상가·공장 cluster_key 단위 롤링 창 사전집계 (UI cluster 목록)';

CREATE INDEX IF NOT EXISTS ix_cccs_asof_window_asset
    ON collective_commercial_cluster_stats (as_of_month DESC, window_years, asset_type);

CREATE INDEX IF NOT EXISTS ix_cccs_region_lookup
    ON collective_commercial_cluster_stats (as_of_month, window_years, asset_type, addr1, addr2);

CREATE INDEX IF NOT EXISTS ix_cccs_cluster_key
    ON collective_commercial_cluster_stats (cluster_key);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS collective_commercial_cluster_annual_stats (
    id                  BIGSERIAL PRIMARY KEY,

    cluster_key         CHAR(64)        NOT NULL,
    asset_type          VARCHAR(24)     NOT NULL,
    contract_year       SMALLINT        NOT NULL,

    display_label       VARCHAR(200)    NOT NULL,
    addr1               VARCHAR(30),
    addr2               VARCHAR(30),
    addr3               VARCHAR(30),
    addr4               VARCHAR(30),
    road_name           VARCHAR(120),

    count               INTEGER         NOT NULL DEFAULT 0,
    mean                NUMERIC(14, 2),
    std                 NUMERIC(14, 2),
    ci_lower            NUMERIC(14, 2),
    ci_upper            NUMERIC(14, 2),
    median              NUMERIC(14, 2),

    computed_at         TIMESTAMP       NOT NULL DEFAULT NOW(),
    batch_id            TEXT,

    CONSTRAINT collective_commercial_cluster_annual_stats_grain_uq UNIQUE (
        cluster_key,
        asset_type,
        contract_year
    )
);

COMMENT ON TABLE collective_commercial_cluster_annual_stats IS
    'cluster_key × 달력연도 — 모달 장기 추세용';

CREATE INDEX IF NOT EXISTS ix_cccas_year
    ON collective_commercial_cluster_annual_stats (contract_year);

CREATE INDEX IF NOT EXISTS ix_cccas_cluster
    ON collective_commercial_cluster_annual_stats (cluster_key, asset_type);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS collective_commercial_cluster_rolling_stats (
    id                  BIGSERIAL PRIMARY KEY,

    as_of_month         DATE            NOT NULL,
    window_years        SMALLINT        NOT NULL
                        CHECK (window_years >= 1 AND window_years <= 5),
    bucket_index        SMALLINT        NOT NULL
                        CHECK (bucket_index >= 1 AND bucket_index <= 5),
    period_start        DATE            NOT NULL,
    period_end          DATE            NOT NULL,

    cluster_key         CHAR(64)        NOT NULL,
    asset_type          VARCHAR(24)     NOT NULL,
    display_label       VARCHAR(200)    NOT NULL,

    count               INTEGER         NOT NULL DEFAULT 0,
    mean                NUMERIC(14, 2),
    std                 NUMERIC(14, 2),
    ci_lower            NUMERIC(14, 2),
    ci_upper            NUMERIC(14, 2),
    median              NUMERIC(14, 2),

    computed_at         TIMESTAMP       NOT NULL DEFAULT NOW(),
    batch_id            TEXT,

    CONSTRAINT collective_commercial_cluster_rolling_period_chk
        CHECK (period_start <= period_end),

    CONSTRAINT collective_commercial_cluster_rolling_as_of_first_of_month_chk
        CHECK (DATE_TRUNC('month', as_of_month)::DATE = as_of_month),

    CONSTRAINT collective_commercial_cluster_rolling_grain_uq UNIQUE (
        as_of_month,
        window_years,
        bucket_index,
        cluster_key,
        asset_type
    )
);

CREATE INDEX IF NOT EXISTS ix_collective_commercial_cluster_rolling_lookup
    ON collective_commercial_cluster_rolling_stats (cluster_key, as_of_month, window_years);

COMMENT ON TABLE collective_commercial_cluster_rolling_stats IS
    'cluster별 12개월 롤링 버킷 통계 — 모달 기본 추세';
