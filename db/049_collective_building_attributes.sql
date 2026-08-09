-- =============================================================================
-- 049: 집합(주거) 단지 속성 — K-apt 스냅샷 + building_key 매칭
-- =============================================================================
-- 설계: docs/COLLECTIVE_RESIDENTIAL_VALUATION_EXPANSION_REVIEW.md §3
-- Grain: builder_master = (snapshot_ym, danji_code)
--        collective_building_attributes = (snapshot_ym, asset_type, building_key)

CREATE TABLE IF NOT EXISTS builder_master (
    id                  BIGSERIAL PRIMARY KEY,

    snapshot_ym         CHAR(6)         NOT NULL,
    danji_code          VARCHAR(20)     NOT NULL,
    danji_name          VARCHAR(200),
    sido_name           VARCHAR(30),
    sigungu_name        VARCHAR(40),
    eupmyeon_name       VARCHAR(40),
    dongri_name         VARCHAR(40),
    beopjungri_code     CHAR(10),
    legal_address       VARCHAR(300),
    road_address        VARCHAR(300),
    lot_key             VARCHAR(32),
    danji_class         VARCHAR(40),
    supply_type         VARCHAR(40),
    approved_date       VARCHAR(8),
    dong_count          INTEGER,
    households          INTEGER,
    households_sale     INTEGER,
    households_rent     INTEGER,
    builder_raw         VARCHAR(200),
    developer_raw       VARCHAR(200),
    structure_raw       VARCHAR(60),
    max_floor           INTEGER,
    basement_floor      INTEGER,
    parking_total       INTEGER,
    parking_ground      INTEGER,
    parking_underground INTEGER,
    heating_type        VARCHAR(40),
    corridor_type       VARCHAR(40),
    source_file         VARCHAR(120),
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_builder_master_snapshot_danji
    ON builder_master (snapshot_ym, danji_code);

CREATE INDEX IF NOT EXISTS ix_builder_master_beopjungri
    ON builder_master (beopjungri_code)
    WHERE beopjungri_code IS NOT NULL;

COMMENT ON TABLE builder_master IS
    'K-apt 공동주택 단지 기본정보 스냅샷 — 원본 보존 (snapshot_ym × 단지코드)';

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS collective_building_attributes (
    id                  BIGSERIAL PRIMARY KEY,

    snapshot_ym         CHAR(6)         NOT NULL,
    asset_type          VARCHAR(20)     NOT NULL,
    building_key        CHAR(64)        NOT NULL,
    danji_code          VARCHAR(20),
    match_tier          CHAR(1)         NOT NULL,
    match_rule          VARCHAR(40)     NOT NULL,
    approved_year       SMALLINT,
    building_year       SMALLINT,
    year_diff           SMALLINT,
    builder_raw         VARCHAR(200),
    builder_norm        VARCHAR(200),
    builder_group       VARCHAR(200),
    developer_raw       VARCHAR(200),
    brand               VARCHAR(80),
    structure_raw       VARCHAR(60),
    structure_group     VARCHAR(20),
    households          INTEGER,
    households_sale     INTEGER,
    households_rent     INTEGER,
    dong_count          INTEGER,
    max_floor           INTEGER,
    parking_total       INTEGER,
    parking_per_household NUMERIC(8, 3),
    danji_class         VARCHAR(40),
    supply_type         VARCHAR(40),
    n_tx                INTEGER,
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_cba_snapshot_asset_building
    ON collective_building_attributes (snapshot_ym, asset_type, building_key);

CREATE INDEX IF NOT EXISTS ix_cba_match_tier
    ON collective_building_attributes (match_tier);

CREATE INDEX IF NOT EXISTS ix_cba_danji_code
    ON collective_building_attributes (danji_code)
    WHERE danji_code IS NOT NULL;

COMMENT ON TABLE collective_building_attributes IS
    '집합(주거) building_key 단지 속성 — K-apt 매칭 결과 (분석용 파생 컬럼)';
