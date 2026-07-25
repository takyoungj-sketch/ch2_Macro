-- =============================================================================
-- 043: collective_commercial_region_annual_stats — 집합상가/집합공장 연도×행정구역 mart
-- =============================================================================
-- 설계: docs/REGIONAL_PROFILE_ARCHITECTURE.md §12 (D-027)
-- 대상 DB: collective_stats (collective_commercial_transactions 와 동일 DB)
-- 그레인: (asset_type, region_level, region_code, calendar_year) — region_code 기준.
-- 기존 collective_commercial_cluster_annual_stats(cluster_key 그레인, 모달 추세용)와는
-- 별도 mart이며 그 테이블은 이번 변경에서 무변경.
-- 빌더: pipeline/build_collective_commercial_market_stats.py
-- =============================================================================

CREATE TABLE IF NOT EXISTS collective_commercial_region_annual_stats (
    id                  BIGSERIAL PRIMARY KEY,

    asset_type          VARCHAR(24)     NOT NULL,  -- collective_shop | collective_factory
    region_level         VARCHAR(12)     NOT NULL,  -- eupmyeondong | sigungu | sido
    region_code          VARCHAR(10)     NOT NULL,
    calendar_year        SMALLINT        NOT NULL
                          CHECK (calendar_year >= 2000 AND calendar_year <= 2100),

    count                INTEGER         NOT NULL DEFAULT 0,
    amount_sum           NUMERIC(18, 2),   -- Σ price (만원)
    mean                 NUMERIC(14, 4),   -- unit_price 평균
    median               NUMERIC(14, 4),
    std                  NUMERIC(14, 4),

    computed_at          TIMESTAMP       NOT NULL DEFAULT NOW(),
    batch_id             TEXT,

    CONSTRAINT cc_region_annual_stats_grain_uq UNIQUE (
        asset_type, region_level, region_code, calendar_year
    )
);

COMMENT ON TABLE collective_commercial_region_annual_stats IS
    '집합상가/집합공장 연도×행정구역(region_code) mart — Regional Profile v2 8대유형(상가/공장) 표 입력. cluster_key 그레인 마트와 별도.';
COMMENT ON COLUMN collective_commercial_region_annual_stats.amount_sum IS 'Σ price(만원)';

CREATE INDEX IF NOT EXISTS ix_cc_region_annual_domain_year
    ON collective_commercial_region_annual_stats (asset_type, calendar_year);

CREATE INDEX IF NOT EXISTS ix_cc_region_annual_code_year
    ON collective_commercial_region_annual_stats (region_level, region_code, calendar_year);
