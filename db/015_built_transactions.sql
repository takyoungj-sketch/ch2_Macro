-- 복합부동산(상업·공장) 연구 MVP — built_stats 전용
-- land_stats 와 분리. region_codes 는 land_stats 에서 1회 복사하거나 seed_region_codes 로 적재.

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

CREATE UNIQUE INDEX IF NOT EXISTS uix_built_region_codes_beopjungri
    ON region_codes (beopjungri_code);

CREATE TABLE IF NOT EXISTS built_transactions (
    id                  BIGSERIAL PRIMARY KEY,
    transaction_hash    CHAR(64)     NOT NULL,
    asset_type          VARCHAR(20)  NOT NULL,  -- commercial | factory | detached
    deal_form           VARCHAR(20)  NOT NULL DEFAULT 'general',  -- general (집합 제외)
    -- 주소 (정제 xlsx 주1~5)
    addr1               VARCHAR(30),
    addr2               VARCHAR(30),
    addr3               VARCHAR(30),
    addr4               VARCHAR(30),
    addr5               VARCHAR(30),
    lot_number          VARCHAR(64),
    -- 행정 코드 (매핑 성공 시)
    beopjungri_code     CHAR(10),
    sido_code           CHAR(2),
    sigungu_code        CHAR(5),
    eupmyeondong_code   CHAR(8),
    -- 거래 시점
    trade_year_label    VARCHAR(4),   -- '21' 등
    contract_year       SMALLINT,
    contract_month      SMALLINT,
    contract_date       DATE,
    -- 특성 (엑셀 정제 컬럼)
    zone_type           VARCHAR(40),
    building_use        VARCHAR(40),
    building_scale      NUMERIC(12, 2),
    land_scale          NUMERIC(12, 2),
    age_bucket          NUMERIC(8, 1),
    price               NUMERIC(14, 2) NOT NULL,  -- 만원
    gross_area          NUMERIC(14, 4),
    land_area           NUMERIC(14, 4),
    building_age        NUMERIC(8, 1),
    road_code           NUMERIC(6, 1),
    floor               NUMERIC(6, 1),
    housing_type        VARCHAR(40),  -- 2차 단독다가구
    floor_area_ratio    NUMERIC(8, 2),
    is_valid            BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_built_tx_hash
    ON built_transactions (transaction_hash);

CREATE INDEX IF NOT EXISTS ix_built_tx_asset
    ON built_transactions (asset_type);

CREATE INDEX IF NOT EXISTS ix_built_tx_contract_year
    ON built_transactions (contract_year);

CREATE INDEX IF NOT EXISTS ix_built_tx_sigungu
    ON built_transactions (sigungu_code);

CREATE INDEX IF NOT EXISTS ix_built_tx_eup
    ON built_transactions (eupmyeondong_code);

CREATE INDEX IF NOT EXISTS ix_built_tx_addr
    ON built_transactions (addr1, addr2, addr3);

COMMENT ON TABLE built_transactions IS '복합부동산(상업·공장·단독다가구) 일반(非집합) 정제 거래 — GUKTO xlsx ingest';
