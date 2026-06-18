-- =============================================================================
-- 023: 집합부동산 Object Stats — building_stats · building_annual_stats
-- =============================================================================
-- 설계: docs/REGIONAL_PROFILE_ARCHITECTURE.md Phase A
-- Grain: building_key × as_of_month × window_years (mart) / building_key × year (annual)

CREATE TABLE IF NOT EXISTS collective_building_stats (
    id                  BIGSERIAL PRIMARY KEY,

    as_of_month         DATE            NOT NULL,
    window_years        SMALLINT        NOT NULL
                        CHECK (window_years >= 1 AND window_years <= 5),
    period_start        DATE            NOT NULL,
    period_end          DATE            NOT NULL,

    building_key        CHAR(64)        NOT NULL,
    asset_type          VARCHAR(20)     NOT NULL,
    display_name        VARCHAR(120)    NOT NULL,

    addr1               VARCHAR(30),
    addr2               VARCHAR(30),
    addr3               VARCHAR(30),
    addr4               VARCHAR(30),
    beopjungri_code     CHAR(10),
    sigungu_code        CHAR(5),
    lot_number          VARCHAR(64),
    road_name           VARCHAR(120),
    building_year       SMALLINT,

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

    CONSTRAINT collective_building_stats_period_chk
        CHECK (period_start <= period_end),

    CONSTRAINT collective_building_stats_as_of_first_of_month_chk
        CHECK (DATE_TRUNC('month', as_of_month)::DATE = as_of_month),

    CONSTRAINT collective_building_stats_grain_uq UNIQUE (
        as_of_month,
        window_years,
        building_key,
        asset_type
    )
);

COMMENT ON TABLE collective_building_stats IS
    '집합 Object Stats — building_key 단위 롤링 창 사전집계 (UI 건물 목록)';

CREATE INDEX IF NOT EXISTS ix_cbs_asof_window_asset
    ON collective_building_stats (as_of_month DESC, window_years, asset_type);

CREATE INDEX IF NOT EXISTS ix_cbs_region_lookup
    ON collective_building_stats (as_of_month, window_years, asset_type, addr1, addr2);

CREATE INDEX IF NOT EXISTS ix_cbs_beopjungri
    ON collective_building_stats (beopjungri_code)
    WHERE beopjungri_code IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_cbs_building_key
    ON collective_building_stats (building_key);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS collective_building_annual_stats (
    id                  BIGSERIAL PRIMARY KEY,

    building_key        CHAR(64)        NOT NULL,
    asset_type          VARCHAR(20)     NOT NULL,
    contract_year       SMALLINT        NOT NULL,

    display_name        VARCHAR(120)    NOT NULL,
    addr1               VARCHAR(30),
    addr2               VARCHAR(30),
    addr3               VARCHAR(30),
    addr4               VARCHAR(30),
    beopjungri_code     CHAR(10),

    count               INTEGER         NOT NULL DEFAULT 0,
    mean                NUMERIC(14, 2),
    std                 NUMERIC(14, 2),
    ci_lower            NUMERIC(14, 2),
    ci_upper            NUMERIC(14, 2),
    median              NUMERIC(14, 2),

    computed_at         TIMESTAMP       NOT NULL DEFAULT NOW(),
    batch_id            TEXT,

    CONSTRAINT collective_building_annual_stats_grain_uq UNIQUE (
        building_key,
        asset_type,
        contract_year
    )
);

COMMENT ON TABLE collective_building_annual_stats IS
    '집합 building_key × 달력연도 — 모달 추세·게이트(count_recent)용';

CREATE INDEX IF NOT EXISTS ix_cbas_year
    ON collective_building_annual_stats (contract_year);

CREATE INDEX IF NOT EXISTS ix_cbas_building
    ON collective_building_annual_stats (building_key, asset_type);
