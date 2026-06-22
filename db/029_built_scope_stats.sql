-- 복합부동산 scope 사전통계 (as_of_month × window_years × 시도·시군구)

CREATE TABLE IF NOT EXISTS built_scope_stats (
    id              BIGSERIAL PRIMARY KEY,
    asset_type      VARCHAR(20)  NOT NULL,
    addr1           VARCHAR(30)  NOT NULL,
    addr2           VARCHAR(30)  NOT NULL DEFAULT '',
    as_of_month     DATE         NOT NULL,
    window_years    SMALLINT     NOT NULL,
    tx_count        BIGINT       NOT NULL,
    median_price    NUMERIC(14, 2),
    mean_price      NUMERIC(14, 2),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT built_scope_stats_uq UNIQUE (asset_type, addr1, addr2, as_of_month, window_years)
);

CREATE INDEX IF NOT EXISTS ix_built_scope_stats_lookup
    ON built_scope_stats (asset_type, addr1, addr2, as_of_month, window_years);

COMMENT ON TABLE built_scope_stats IS '복합부동산 지역·유형별 롤링 거래 요약 (Phase B mart)';
