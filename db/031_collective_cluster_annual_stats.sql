-- =============================================================================
-- 031: 비주거 집합 cluster_key × 달력연도 annual mart (장기 추세 2010~2020 + 2021~)
-- =============================================================================
-- Grain: cluster_key × asset_type × contract_year
-- 2010~2020: ingest_collective_commercial_long_term_annual.py
-- 2021~    : build_collective_cluster_annual_stats.py

CREATE TABLE IF NOT EXISTS collective_cluster_annual_stats (
    id                  BIGSERIAL PRIMARY KEY,

    cluster_key         CHAR(64)        NOT NULL,
    asset_type          VARCHAR(20)     NOT NULL,
    contract_year       SMALLINT        NOT NULL,

    display_label       VARCHAR(120)    NOT NULL,
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

    CONSTRAINT collective_cluster_annual_stats_grain_uq UNIQUE (
        cluster_key,
        asset_type,
        contract_year
    )
);

COMMENT ON TABLE collective_cluster_annual_stats IS
    '비주거 집합 cluster_key × 달력연도 — 모달 장기 추세 탭용';

CREATE INDEX IF NOT EXISTS ix_ccas_year
    ON collective_cluster_annual_stats (contract_year);

CREATE INDEX IF NOT EXISTS ix_ccas_cluster
    ON collective_cluster_annual_stats (cluster_key, asset_type);
