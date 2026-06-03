-- 집합부동산(아파트·연립·오피스텔) — collective_stats 전용
-- land_stats / built_stats 와 분리

CREATE TABLE IF NOT EXISTS region_codes (
    id              SERIAL PRIMARY KEY,
    sido_code       CHAR(2)      NOT NULL,
    sido_name       VARCHAR(20)  NOT NULL,
    sigungu_code    CHAR(5)      NOT NULL,
    sigungu_name    VARCHAR(30)  NOT NULL,
    eupmyeondong_code CHAR(8)    NOT NULL,
    eupmyeondong_name VARCHAR(30) NOT NULL,
    beopjungri_code CHAR(10)     NOT NULL,
    beopjungri_name VARCHAR(30)  NOT NULL,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    updated_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_collective_region_codes_beopjungri
    ON region_codes (beopjungri_code);

CREATE TABLE IF NOT EXISTS collective_transactions (
    id                  BIGSERIAL PRIMARY KEY,
    transaction_hash    CHAR(64)     NOT NULL,
    asset_type          VARCHAR(20)  NOT NULL,  -- apartment | rowhouse | officetel
    building_key        CHAR(64)     NOT NULL,
    display_name        VARCHAR(120) NOT NULL,
    building_name       VARCHAR(120),
    housing_subtype     VARCHAR(40),
    addr1               VARCHAR(30),
    addr2               VARCHAR(30),
    addr3               VARCHAR(30),
    addr4               VARCHAR(30),
    addr5               VARCHAR(30),
    lot_number          VARCHAR(64),
    road_name           VARCHAR(120),
    sido_code           CHAR(2),
    sigungu_code        CHAR(5),
    eupmyeondong_code   CHAR(8),
    beopjungri_code     CHAR(10),
    contract_year       SMALLINT,
    contract_month      SMALLINT,
    contract_date       DATE,
    building_year       SMALLINT,
    building_age        NUMERIC(8, 1),
    exclusive_area      NUMERIC(14, 4) NOT NULL,
    price               NUMERIC(14, 2) NOT NULL,
    unit_price          NUMERIC(14, 4),
    area_bucket         NUMERIC(8, 1),
    age_bucket          NUMERIC(8, 1),
    floor               NUMERIC(8, 1),
    dong                VARCHAR(64),
    is_valid            BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_collective_tx_hash
    ON collective_transactions (transaction_hash);

CREATE INDEX IF NOT EXISTS ix_collective_tx_asset
    ON collective_transactions (asset_type);

CREATE INDEX IF NOT EXISTS ix_collective_tx_building
    ON collective_transactions (building_key);

CREATE INDEX IF NOT EXISTS ix_collective_tx_addr
    ON collective_transactions (addr1, addr2, addr3);

CREATE INDEX IF NOT EXISTS ix_collective_tx_contract_year
    ON collective_transactions (contract_year);

CREATE INDEX IF NOT EXISTS ix_collective_tx_sigungu
    ON collective_transactions (sigungu_code);

COMMENT ON TABLE collective_transactions IS '집합부동산 거래 원장 — 건물(building_key) 내 다건';
