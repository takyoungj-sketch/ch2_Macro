-- =============================================================================
-- 069: 집합 단지별 최신 대표 필지 개별공시지가
-- =============================================================================
-- Grain: building_key × asset_type — 기본통계의 대표 필지 1개에 대한 최신값
-- 회귀에서는 assessed_land_price를 원값(원/㎡)으로 사용한다. 로그 변환은 후속 실험.

CREATE TABLE IF NOT EXISTS collective_building_assessed_land_price (
    building_key             CHAR(64)       NOT NULL,
    asset_type               VARCHAR(20)    NOT NULL,
    representative_pnu       CHAR(19)       NOT NULL,
    assessed_land_price      NUMERIC(14, 2) NOT NULL
                             CHECK (assessed_land_price > 0),
    assessed_land_price_year SMALLINT       NOT NULL
                             CHECK (assessed_land_price_year BETWEEN 1900 AND 2200),
    source                   TEXT           NOT NULL,
    loaded_at                TIMESTAMP      NOT NULL DEFAULT NOW(),

    CONSTRAINT collective_building_assessed_land_price_pk
        PRIMARY KEY (building_key, asset_type)
);

COMMENT ON TABLE collective_building_assessed_land_price IS
    '집합 단지별 최신 개별공시지가 — 기본통계 대표 필지 1개, 회귀 원값';

COMMENT ON COLUMN collective_building_assessed_land_price.representative_pnu IS
    '기본통계에 표시하는 대표 필지의 19자리 PNU';

CREATE INDEX IF NOT EXISTS ix_cbalp_pnu
    ON collective_building_assessed_land_price (representative_pnu);

CREATE INDEX IF NOT EXISTS ix_cbalp_year
    ON collective_building_assessed_land_price (assessed_land_price_year);
