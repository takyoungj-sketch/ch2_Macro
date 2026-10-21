-- 복합 보강: 복원 필지의 개별공시지가. 화면·회귀는 보강을 켠 뒤에만 읽는다.
-- 계약연도와 같은 기준연도, 없을 때만 직전 연도. 같은 연도 값이 둘이면 비운다.

ALTER TABLE built_transaction_enrichment
    ADD COLUMN IF NOT EXISTS assessed_land_price BIGINT,
    ADD COLUMN IF NOT EXISTS assessed_land_price_year SMALLINT,
    ADD COLUMN IF NOT EXISTS assessed_land_price_basis TEXT;

ALTER TABLE built_transaction_enrichment
    DROP CONSTRAINT IF EXISTS built_enrichment_assessed_price_chk;

ALTER TABLE built_transaction_enrichment
    ADD CONSTRAINT built_enrichment_assessed_price_chk
    CHECK (
        (
            assessed_land_price IS NULL
            AND assessed_land_price_year IS NULL
            AND assessed_land_price_basis IS NULL
        )
        OR (
            assessed_land_price IS NOT NULL
            AND assessed_land_price_year IS NOT NULL
            AND assessed_land_price_basis IN ('same_year', 'prior_year')
        )
    );

COMMENT ON COLUMN built_transaction_enrichment.assessed_land_price IS
    '복원 필지 개별공시지가(원/㎡). 건물 전체 합이나 총액이 아니다.';
COMMENT ON COLUMN built_transaction_enrichment.assessed_land_price_year IS
    '그 가격의 기준연도.';
COMMENT ON COLUMN built_transaction_enrichment.assessed_land_price_basis IS
    'same_year: 계약연도. prior_year: 직전 연도.';
