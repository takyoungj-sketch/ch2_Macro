-- =============================================================================
-- 044: market_annual_stats.amount_sum — 거래액(Σ금액) additive 컬럼
-- =============================================================================
-- 설계: docs/REGIONAL_PROFILE_ARCHITECTURE.md §12 (D-027)
-- 대상 DB: collective_stats
-- 영향: apartment_market/rowhouse_market/officetel_market/presale_market 4개 도메인
--       모두 동일 빌더(build_collective_market_stats.py)의 build_annual() 루프를 타므로
--       한 번의 컬럼 추가로 4개 도메인 amount 가 함께 채워진다.
-- 기존 count/mean/median/std 컬럼·로직은 무변경(additive).
-- =============================================================================

ALTER TABLE market_annual_stats
    ADD COLUMN IF NOT EXISTS amount_sum NUMERIC(18, 2);

COMMENT ON COLUMN market_annual_stats.amount_sum IS
    'Σ price(만원) — Regional Profile v2 3개년 8대유형 표 거래액 입력 (D-027)';
