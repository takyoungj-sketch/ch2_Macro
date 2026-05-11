-- =============================================================================
-- 성능 최적화 인덱스 (초기 전국 5년 데이터 적재 후 실행)
-- =============================================================================

-- 시도별 파티션 인덱스 (추후 파티션 전환 시 대비)
CREATE INDEX IF NOT EXISTS ix_land_tx_sido
    ON land_transactions (sido_code, contract_year);

-- 복합 필터 쿼리 최적화 (유료 동적 쿼리용)
CREATE INDEX IF NOT EXISTS ix_land_tx_paid_query
    ON land_transactions (
        sigungu_code,
        contract_year,
        is_valid,
        is_cancelled,
        is_partial_ownership,
        road_condition,
        area_category,
        land_category,
        zone_type
    )
    WHERE is_valid = TRUE AND is_cancelled = FALSE;

-- 단가 범위 조회용 (이상치 제거 시 활용)
CREATE INDEX IF NOT EXISTS ix_land_tx_unit_price
    ON land_transactions (beopjungri_code, unit_price_per_sqm)
    WHERE unit_price_per_sqm IS NOT NULL AND is_valid = TRUE;

-- region_codes 검색 최적화
CREATE INDEX IF NOT EXISTS ix_region_codes_sigungu
    ON region_codes (sigungu_code);

CREATE INDEX IF NOT EXISTS ix_region_codes_eupmyeondong
    ON region_codes (eupmyeondong_code);

CREATE INDEX IF NOT EXISTS ix_region_codes_names
    ON region_codes USING gin (
        to_tsvector('simple', sido_name || ' ' || sigungu_name || ' ' || eupmyeondong_name || ' ' || beopjungri_name)
    );
