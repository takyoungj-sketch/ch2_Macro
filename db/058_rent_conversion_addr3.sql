-- 전환율 grain에 읍면동(addr3) 추가. 빈 문자열 = 시군구 집계.

ALTER TABLE rent_conversion_rates
    ADD COLUMN IF NOT EXISTS addr3 VARCHAR(30) NOT NULL DEFAULT '';

ALTER TABLE rent_conversion_rates
    DROP CONSTRAINT IF EXISTS rent_conversion_rates_grain_uq;

ALTER TABLE rent_conversion_rates
    ADD CONSTRAINT rent_conversion_rates_grain_uq UNIQUE (
        as_of_month, window_years, addr1, addr2, addr3, asset_type
    );

DROP INDEX IF EXISTS ix_rent_conv_lookup;
CREATE INDEX IF NOT EXISTS ix_rent_conv_lookup
    ON rent_conversion_rates (as_of_month, window_years, addr1, addr2, addr3, asset_type);

COMMENT ON TABLE rent_conversion_rates IS
    '시군구(addr3='''')·읍면동×유형×창 전환율. 목록은 선택 단위 r, 동 미달 시 시군구 fallback.';
