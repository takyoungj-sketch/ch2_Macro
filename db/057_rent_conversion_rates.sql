-- 지역×주택유형×롤링 창별 CH2 자체 전월세전환율 (분석층). 원장 환산 컬럼 없음.

CREATE TABLE IF NOT EXISTS rent_conversion_rates (
    id                  BIGSERIAL PRIMARY KEY,
    as_of_month         DATE            NOT NULL,
    window_years        SMALLINT        NOT NULL
                        CHECK (window_years >= 1 AND window_years <= 7),
    period_start        DATE            NOT NULL,
    period_end          DATE            NOT NULL,

    addr1               VARCHAR(30)     NOT NULL,
    addr2               VARCHAR(30)     NOT NULL,
    addr3               VARCHAR(30)     NOT NULL DEFAULT '',
    asset_type          VARCHAR(20)     NOT NULL,

    n_buildings         INTEGER         NOT NULL DEFAULT 0,
    n_jeonse            INTEGER         NOT NULL DEFAULT 0,
    n_mixed             INTEGER         NOT NULL DEFAULT 0,

    r_mean_simple       NUMERIC(8, 4),
    r_mean_weighted     NUMERIC(8, 4),
    r_ols_origin        NUMERIC(8, 4),
    r_ols_weighted      NUMERIC(8, 4),

    r_selected          NUMERIC(8, 4),
    method_selected     VARCHAR(24)     NOT NULL DEFAULT 'ols_origin',
    gate_passed         BOOLEAN         NOT NULL DEFAULT FALSE,

    computed_at         TIMESTAMP       NOT NULL DEFAULT NOW(),
    batch_id            TEXT,

    CONSTRAINT rent_conversion_rates_period_chk
        CHECK (period_start <= period_end),
    CONSTRAINT rent_conversion_rates_as_of_chk
        CHECK (DATE_TRUNC('month', as_of_month)::DATE = as_of_month),
    CONSTRAINT rent_conversion_rates_grain_uq UNIQUE (
        as_of_month, window_years, addr1, addr2, addr3, asset_type
    )
);

CREATE INDEX IF NOT EXISTS ix_rent_conv_lookup
    ON rent_conversion_rates (as_of_month, window_years, addr1, addr2, addr3, asset_type);

COMMENT ON TABLE rent_conversion_rates IS
    '시군구(addr3='''')·읍면동×유형×창 전환율. 환산은 선택 단위 r_selected.';
