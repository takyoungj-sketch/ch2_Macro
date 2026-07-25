-- =============================================================================
-- 042: built_annual_stats — 일반 부동산(상업업무/공장창고/단독다가구) 연도×지역 mart
-- =============================================================================
-- 설계: docs/REGIONAL_PROFILE_ARCHITECTURE.md §12 (D-027)
-- 대상 DB: built_stats (built_transactions 와 동일 DB, land_annual_stats 패턴과 동일)
-- 그레인: (asset_type, region_level, region_code, calendar_year)
-- 빌더: pipeline/build_built_market_stats.py
-- =============================================================================

CREATE TABLE IF NOT EXISTS built_annual_stats (
    id                  BIGSERIAL PRIMARY KEY,

    asset_type          VARCHAR(20)     NOT NULL,  -- commercial | factory | detached
    region_level         VARCHAR(12)     NOT NULL,  -- eupmyeondong | sigungu | sido
    region_code          VARCHAR(10)     NOT NULL,
    calendar_year        SMALLINT        NOT NULL
                          CHECK (calendar_year >= 2000 AND calendar_year <= 2100),

    count                INTEGER         NOT NULL DEFAULT 0,
    amount_sum           NUMERIC(18, 2),   -- Σ price (만원)
    mean                 NUMERIC(14, 2),   -- 단가(price/gross_area, 만원/㎡) 평균
    median               NUMERIC(14, 2),
    std                  NUMERIC(14, 2),

    computed_at          TIMESTAMP       NOT NULL DEFAULT NOW(),
    batch_id             TEXT,

    CONSTRAINT built_annual_stats_grain_uq UNIQUE (
        asset_type, region_level, region_code, calendar_year
    )
);

COMMENT ON TABLE built_annual_stats IS
    '상업업무/공장창고/단독다가구 연도×지역 mart — Regional Profile v2 8대유형(상가/공장/단독다가구) 표 입력';
COMMENT ON COLUMN built_annual_stats.amount_sum IS 'Σ price(만원) — 3개년 시장현황 표 거래액';
COMMENT ON COLUMN built_annual_stats.mean IS '단가(price/gross_area, 만원/㎡) 평균 — gross_area>0 인 거래만';

CREATE INDEX IF NOT EXISTS ix_built_annual_domain_year
    ON built_annual_stats (asset_type, calendar_year);

CREATE INDEX IF NOT EXISTS ix_built_annual_code_year
    ON built_annual_stats (region_level, region_code, calendar_year);
