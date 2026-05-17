-- =============================================================================
-- 008: V2 전국 배치용 land_transactions 부분 인덱스
-- =============================================================================
-- build_stats_v2.py 가 시도(sido_code) 단위로 아래 조건을 반복 조회할 때 활용.
-- 적용 후 ANALYZE land_transactions; 권장.
--
--   psql ... -f db/008_land_transactions_v2_batch_index.sql
-- =============================================================================

CREATE INDEX IF NOT EXISTS ix_land_tx_v2_batch_sido_contract
    ON land_transactions (sido_code, contract_date)
    WHERE is_valid = TRUE
      AND is_cancelled = FALSE
      AND unit_price_per_sqm IS NOT NULL
      AND contract_date IS NOT NULL;

COMMENT ON INDEX ix_land_tx_v2_batch_sido_contract IS
    'V2 배치: 시도+계약일 구간 스캔 (정제 행만)';

-- DOWN
-- DROP INDEX IF EXISTS ix_land_tx_v2_batch_sido_contract;
