-- 030: 비주거 집합 cluster 사전집계 mart (도로 cluster grain)

CREATE TABLE IF NOT EXISTS collective_cluster_stats (
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
    confidence_tier     VARCHAR(8),

    count               INTEGER         NOT NULL DEFAULT 0,
    mean                NUMERIC(14, 2),
    std                 NUMERIC(14, 2),
    ci_lower            NUMERIC(14, 2),
    ci_upper            NUMERIC(14, 2),
    median              NUMERIC(14, 2),

    computed_at         TIMESTAMP       NOT NULL DEFAULT NOW(),
    batch_id            TEXT,

    CONSTRAINT collective_cluster_stats_period_chk
        CHECK (period_start <= period_end),

    CONSTRAINT collective_cluster_stats_as_of_first_of_month_chk
        CHECK (DATE_TRUNC('month', as_of_month)::DATE = as_of_month),

    CONSTRAINT collective_cluster_stats_grain_uq UNIQUE (
        as_of_month,
        window_years,
        cluster_key,
        asset_type
    )
);

CREATE INDEX IF NOT EXISTS ix_collective_cluster_stats_lookup
    ON collective_cluster_stats (addr1, addr2, asset_type, as_of_month, window_years);

CREATE TABLE IF NOT EXISTS collective_cluster_rolling_stats (
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

    CONSTRAINT collective_cluster_rolling_period_chk
        CHECK (period_start <= period_end),

    CONSTRAINT collective_cluster_rolling_grain_uq UNIQUE (
        as_of_month,
        window_years,
        bucket_index,
        cluster_key,
        asset_type
    )
);

CREATE INDEX IF NOT EXISTS ix_collective_cluster_rolling_lookup
    ON collective_cluster_rolling_stats (cluster_key, as_of_month, window_years);

COMMENT ON TABLE collective_cluster_stats IS '비주거 집합 도로 cluster 롤링 창 사전집계 (목록)';
COMMENT ON TABLE collective_cluster_rolling_stats IS '비주거 집합 도로 cluster 12개월 버킷 (모달 롤링 추세)';
