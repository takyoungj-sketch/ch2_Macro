-- 집합상가·집합공장 (cluster_key 기반, collective_stats)

CREATE TABLE IF NOT EXISTS commercial_clusters (
    id                  BIGSERIAL PRIMARY KEY,
    cluster_key         CHAR(64)     NOT NULL,
    asset_type          VARCHAR(24)  NOT NULL,  -- collective_shop | collective_factory
    display_label       VARCHAR(200) NOT NULL,
    resolution_mode     VARCHAR(16)  NOT NULL DEFAULT 'cluster',
    building_key        CHAR(64),
    addr1               VARCHAR(30),
    addr2               VARCHAR(30),
    addr3               VARCHAR(30),
    addr4               VARCHAR(30),
    road_name           VARCHAR(120),
    zone_type           VARCHAR(40),
    building_use        VARCHAR(40),
    building_year       SMALLINT,
    area_bucket_label   VARCHAR(32),
    n_total             INTEGER      NOT NULL DEFAULT 0,
    cohesion_score      NUMERIC(6, 2),
    confidence_tier     VARCHAR(8),   -- high | medium | low
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_commercial_clusters_key
    ON commercial_clusters (cluster_key);

CREATE INDEX IF NOT EXISTS ix_commercial_clusters_asset_addr
    ON commercial_clusters (asset_type, addr1, addr2, addr3);

CREATE TABLE IF NOT EXISTS collective_commercial_transactions (
    id                  BIGSERIAL PRIMARY KEY,
    transaction_hash    CHAR(64)     NOT NULL,
    cluster_id          BIGINT       NOT NULL REFERENCES commercial_clusters(id),
    asset_type          VARCHAR(24)  NOT NULL,
    cluster_key         CHAR(64)     NOT NULL,
    resolution_mode     VARCHAR(16)  NOT NULL DEFAULT 'cluster',
    building_key        CHAR(64),
    addr1               VARCHAR(30),
    addr2               VARCHAR(30),
    addr3               VARCHAR(30),
    addr4               VARCHAR(30),
    addr5               VARCHAR(30),
    lot_number          VARCHAR(64),
    road_name           VARCHAR(120),
    zone_type           VARCHAR(40),
    building_use        VARCHAR(40),
    building_year       SMALLINT,
    area_bucket_label   VARCHAR(32),
    contract_year       SMALLINT,
    contract_month      SMALLINT,
    contract_date       DATE,
    price               NUMERIC(14, 2) NOT NULL,
    gross_area          NUMERIC(14, 4) NOT NULL,
    land_area           NUMERIC(14, 4),
    unit_price          NUMERIC(14, 4),
    floor               NUMERIC(8, 1),
    road_code           NUMERIC(6, 1),
    road_width_label    VARCHAR(32),
    building_age        NUMERIC(8, 1),
    is_valid            BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_cc_tx_cluster
    ON collective_commercial_transactions (cluster_id);

CREATE INDEX IF NOT EXISTS ix_cc_tx_asset_year
    ON collective_commercial_transactions (asset_type, contract_year);

CREATE INDEX IF NOT EXISTS ix_cc_tx_hash
    ON collective_commercial_transactions (transaction_hash);

COMMENT ON TABLE commercial_clusters IS '집합상가·집합공장 상품군(cluster_key) 차원';
COMMENT ON TABLE collective_commercial_transactions IS '집합상가·집합공장 거래 원장';
