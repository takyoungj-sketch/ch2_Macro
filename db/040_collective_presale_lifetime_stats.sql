-- =============================================================================
-- 040: 분양·입주권 전체 거래기간 Object Stats
-- =============================================================================
-- 설계: docs/COLLECTIVE_PRESALE_BUILDING_KEY.md
-- Grain: building_key (asset_type = presale 고정)
-- period_start/end = 해당 키의 실거래 min/max 계약일

CREATE TABLE IF NOT EXISTS collective_presale_lifetime_stats (
    id                  BIGSERIAL PRIMARY KEY,

    building_key        CHAR(64)        NOT NULL,
    asset_type          VARCHAR(20)     NOT NULL DEFAULT 'presale'
                        CHECK (asset_type = 'presale'),
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

    period_start        DATE            NOT NULL,
    period_end          DATE            NOT NULL,

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

    snapshot_as_of      DATE,
    computed_at         TIMESTAMP       NOT NULL DEFAULT NOW(),
    batch_id            TEXT,

    CONSTRAINT collective_presale_lifetime_period_chk
        CHECK (period_start <= period_end),

    CONSTRAINT collective_presale_lifetime_grain_uq UNIQUE (building_key)
);

COMMENT ON TABLE collective_presale_lifetime_stats IS
    '분양·입주권 building_key 전체 거래기간 요약 — 목록 기본 통계 (3/5년 mart와 분리)';

CREATE INDEX IF NOT EXISTS ix_cpls_region
    ON collective_presale_lifetime_stats (addr1, addr2, addr3);

CREATE INDEX IF NOT EXISTS ix_cpls_addr2
    ON collective_presale_lifetime_stats (addr2);
