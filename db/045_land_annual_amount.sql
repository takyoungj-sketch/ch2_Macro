-- =============================================================================
-- 045: land_annual_stats.amount_sum_10k — 거래액(Σ금액) additive 컬럼
-- =============================================================================
-- 설계: docs/REGIONAL_PROFILE_ARCHITECTURE.md §12 (D-027)
-- 대상 DB: land_stats
-- 기존 count/단가 통계 컬럼·로직은 무변경(additive).
-- =============================================================================

ALTER TABLE land_annual_stats
    ADD COLUMN IF NOT EXISTS amount_sum_10k NUMERIC(18, 2);

COMMENT ON COLUMN land_annual_stats.amount_sum_10k IS
    'Σ total_price_10k(만원) — Regional Profile v2 3개년 8대유형 표(토지) 거래액 입력 (D-027)';
