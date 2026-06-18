-- region_sigungu_meta only (collective/built 공통) — 022 UNIQUE 제약 COALESCE 호환

CREATE TABLE IF NOT EXISTS region_sigungu_meta (
    id                  BIGSERIAL PRIMARY KEY,
    asset_domain        VARCHAR(20)  NOT NULL,
    asset_type          VARCHAR(20),
    sido_code           CHAR(2)      NOT NULL,
    sido_name           VARCHAR(30)  NOT NULL,
    sigungu_code        CHAR(5),
    sigungu_name        VARCHAR(60)  NOT NULL,
    addr2_token         VARCHAR(30)  NOT NULL,
    structure_type      VARCHAR(20)  NOT NULL,
    leaf_level          VARCHAR(10)  NOT NULL,
    has_ri              BOOLEAN      NOT NULL DEFAULT FALSE,
    tx_count            BIGINT       NOT NULL DEFAULT 0,
    mapped_tx_count     BIGINT       NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_rsm_grain_null_type
    ON region_sigungu_meta (asset_domain, sido_code, addr2_token)
    WHERE asset_type IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uix_rsm_grain_typed
    ON region_sigungu_meta (asset_domain, asset_type, sido_code, addr2_token)
    WHERE asset_type IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_rsm_domain_sido
    ON region_sigungu_meta (asset_domain, sido_code, addr2_token);
