-- 주거 전월세 건물 목록·롤링 마트. 전환율 없음.
-- 전세=보증금/㎡, 반전세=보증금/㎡+월세/㎡, 월세(순수)=월세/㎡.

CREATE INDEX IF NOT EXISTS ix_rent_tx_addr1_date
    ON rent_transactions (addr1, contract_date)
    WHERE is_valid = TRUE;

CREATE TABLE IF NOT EXISTS rent_building_stats (
    id                  BIGSERIAL PRIMARY KEY,
    as_of_month         DATE            NOT NULL,
    window_years        SMALLINT        NOT NULL
                        CHECK (window_years >= 1 AND window_years <= 7),
    period_start        DATE            NOT NULL,
    period_end          DATE            NOT NULL,

    building_key        CHAR(64)        NOT NULL,
    asset_type          VARCHAR(20)     NOT NULL,
    display_name        VARCHAR(120)    NOT NULL,
    addr1               VARCHAR(30),
    addr2               VARCHAR(30),
    addr3               VARCHAR(30),
    addr4               VARCHAR(30),
    addr5               VARCHAR(30),
    beopjungri_code     CHAR(10),
    sigungu_code        CHAR(5),
    lot_number          VARCHAR(64),
    road_name           VARCHAR(120),
    building_year       SMALLINT,

    jeonse_n            INTEGER         NOT NULL DEFAULT 0,
    jeonse_mean         NUMERIC(14, 2),
    jeonse_median       NUMERIC(14, 2),
    jeonse_ci_lower     NUMERIC(14, 2),
    jeonse_ci_upper     NUMERIC(14, 2),

    mixed_n             INTEGER         NOT NULL DEFAULT 0,
    mixed_deposit_mean  NUMERIC(14, 2),
    mixed_deposit_median NUMERIC(14, 2),
    mixed_deposit_ci_lower NUMERIC(14, 2),
    mixed_deposit_ci_upper NUMERIC(14, 2),
    mixed_monthly_mean  NUMERIC(14, 2),
    mixed_monthly_median NUMERIC(14, 2),
    mixed_monthly_ci_lower NUMERIC(14, 2),
    mixed_monthly_ci_upper NUMERIC(14, 2),

    monthly_n           INTEGER         NOT NULL DEFAULT 0,
    monthly_mean        NUMERIC(14, 2),
    monthly_median      NUMERIC(14, 2),
    monthly_ci_lower    NUMERIC(14, 2),
    monthly_ci_upper    NUMERIC(14, 2),

    computed_at         TIMESTAMP       NOT NULL DEFAULT NOW(),
    batch_id            TEXT,

    CONSTRAINT rent_building_stats_period_chk
        CHECK (period_start <= period_end),
    CONSTRAINT rent_building_stats_as_of_chk
        CHECK (DATE_TRUNC('month', as_of_month)::DATE = as_of_month),
    CONSTRAINT rent_building_stats_grain_uq UNIQUE (
        as_of_month, window_years, building_key, asset_type
    )
);

CREATE INDEX IF NOT EXISTS ix_rbs_lookup
    ON rent_building_stats (as_of_month, window_years, asset_type, addr1, addr2);

CREATE INDEX IF NOT EXISTS ix_rbs_building
    ON rent_building_stats (building_key, as_of_month, window_years);

COMMENT ON TABLE rent_building_stats IS
    '임대 건물 목록. 전세=deposit/㎡, 반전세=deposit+monthly/㎡, 순수월세=monthly/㎡. 환산 없음.';

CREATE TABLE IF NOT EXISTS rent_building_rolling_stats (
    id                  BIGSERIAL PRIMARY KEY,
    as_of_month         DATE            NOT NULL,
    window_years        SMALLINT        NOT NULL
                        CHECK (window_years >= 1 AND window_years <= 7),
    bucket_index        SMALLINT        NOT NULL
                        CHECK (bucket_index >= 1 AND bucket_index <= 7),
    period_start        DATE            NOT NULL,
    period_end          DATE            NOT NULL,

    building_key        CHAR(64)        NOT NULL,
    asset_type          VARCHAR(20)     NOT NULL,
    display_name        VARCHAR(120)    NOT NULL,

    jeonse_n            INTEGER         NOT NULL DEFAULT 0,
    jeonse_mean         NUMERIC(14, 2),
    jeonse_median       NUMERIC(14, 2),
    jeonse_ci_lower     NUMERIC(14, 2),
    jeonse_ci_upper     NUMERIC(14, 2),

    mixed_n             INTEGER         NOT NULL DEFAULT 0,
    mixed_deposit_mean  NUMERIC(14, 2),
    mixed_deposit_median NUMERIC(14, 2),
    mixed_deposit_ci_lower NUMERIC(14, 2),
    mixed_deposit_ci_upper NUMERIC(14, 2),
    mixed_monthly_mean  NUMERIC(14, 2),
    mixed_monthly_median NUMERIC(14, 2),
    mixed_monthly_ci_lower NUMERIC(14, 2),
    mixed_monthly_ci_upper NUMERIC(14, 2),

    monthly_n           INTEGER         NOT NULL DEFAULT 0,
    monthly_mean        NUMERIC(14, 2),
    monthly_median      NUMERIC(14, 2),
    monthly_ci_lower    NUMERIC(14, 2),
    monthly_ci_upper    NUMERIC(14, 2),

    computed_at         TIMESTAMP       NOT NULL DEFAULT NOW(),
    batch_id            TEXT,

    CONSTRAINT rent_building_rolling_period_chk
        CHECK (period_start <= period_end),
    CONSTRAINT rent_building_rolling_as_of_chk
        CHECK (DATE_TRUNC('month', as_of_month)::DATE = as_of_month),
    CONSTRAINT rent_building_rolling_grain_uq UNIQUE (
        as_of_month, window_years, bucket_index, building_key, asset_type
    )
);

CREATE INDEX IF NOT EXISTS ix_rbr_lookup
    ON rent_building_rolling_stats (building_key, as_of_month, window_years);

COMMENT ON TABLE rent_building_rolling_stats IS
    '임대 건물 12개월 롤링 버킷. 목록과 같은 3유형 단가. 환산 없음.';
