-- =============================================================================
-- 027: 집합부동산 building 롤링 12개월 버킷 stats (모달 추세·요약)
-- =============================================================================
-- grain: building_key × asset_type × as_of_month × window_years × bucket_index

CREATE TABLE IF NOT EXISTS collective_building_rolling_stats (
    id                  BIGSERIAL PRIMARY KEY,

    as_of_month         DATE            NOT NULL,
    window_years        SMALLINT        NOT NULL
                        CHECK (window_years >= 1 AND window_years <= 5),
    bucket_index        SMALLINT        NOT NULL
                        CHECK (bucket_index >= 1 AND bucket_index <= 5),
    period_start        DATE            NOT NULL,
    period_end          DATE            NOT NULL,

    building_key        CHAR(64)        NOT NULL,
    asset_type          VARCHAR(20)     NOT NULL,
    display_name        VARCHAR(120)    NOT NULL,

    count               INTEGER         NOT NULL DEFAULT 0,
    mean                NUMERIC(14, 2),
    std                 NUMERIC(14, 2),
    ci_lower            NUMERIC(14, 2),
    ci_upper            NUMERIC(14, 2),
    median              NUMERIC(14, 2),

    computed_at         TIMESTAMP       NOT NULL DEFAULT NOW(),
    batch_id            TEXT,

    CONSTRAINT collective_building_rolling_period_chk
        CHECK (period_start <= period_end),

    CONSTRAINT collective_building_rolling_as_of_first_of_month_chk
        CHECK (DATE_TRUNC('month', as_of_month)::DATE = as_of_month),

    CONSTRAINT collective_building_rolling_grain_uq UNIQUE (
        as_of_month,
        window_years,
        bucket_index,
        building_key,
        asset_type
    )
);

CREATE INDEX IF NOT EXISTS ix_collective_building_rolling_lookup
    ON collective_building_rolling_stats (building_key, as_of_month, window_years);

COMMENT ON TABLE collective_building_rolling_stats IS
    '건물별 12개월 롤링 버킷 통계 — 모달 기본 추세 (토지 매트릭스 롤링과 동일 축)';
