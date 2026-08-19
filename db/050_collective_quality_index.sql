-- =============================================================================
-- 050: 집합(주거) 1단계 단지 품질지수 mart
-- =============================================================================
-- 설계 SSOT: docs/COLLECTIVE_TWO_STAGE_HEDONIC_DESIGN.md §2 · §4

CREATE TABLE IF NOT EXISTS collective_building_quality_index (
    id                  BIGSERIAL PRIMARY KEY,
    as_of_month         DATE         NOT NULL,
    window_years        SMALLINT     NOT NULL,
    asset_type          VARCHAR(20)  NOT NULL,
    sigungu_code        CHAR(5)      NOT NULL,
    building_key        CHAR(64)     NOT NULL,
    quality_index       NUMERIC(10, 6) NOT NULL,
    quality_se          NUMERIC(10, 6),
    n_tx                INTEGER      NOT NULL,
    first_year          SMALLINT,
    last_year           SMALLINT,
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_cbqi_grain
    ON collective_building_quality_index
       (as_of_month, window_years, asset_type, building_key);

CREATE INDEX IF NOT EXISTS ix_cbqi_sigungu
    ON collective_building_quality_index (as_of_month, sigungu_code);

COMMENT ON TABLE collective_building_quality_index IS
    '1단계 시군구 OLS 단지 FE(센터링) — 면적·층·계약연도 통제 후 상대 가격수준';

CREATE TABLE IF NOT EXISTS collective_sigungu_base_level (
    id                  BIGSERIAL PRIMARY KEY,
    as_of_month         DATE         NOT NULL,
    window_years        SMALLINT     NOT NULL,
    asset_type          VARCHAR(20)  NOT NULL,
    sigungu_code        CHAR(5)      NOT NULL,
    base_ln_price       NUMERIC(12, 6) NOT NULL,
    ref_area            NUMERIC(10, 3) NOT NULL,
    ref_floor_group     VARCHAR(20)  NOT NULL,
    ref_year            SMALLINT     NOT NULL,
    area_beta           NUMERIC(10, 6),
    r_squared           NUMERIC(8, 5),
    n_buildings         INTEGER      NOT NULL,
    n_tx                INTEGER      NOT NULL,
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_csbl_grain
    ON collective_sigungu_base_level
       (as_of_month, window_years, asset_type, sigungu_code);

COMMENT ON TABLE collective_sigungu_base_level IS
    '1단계 시군구 기준 log(㎡당가) — 품질지수와 분리 저장(절대수준 복원용)';
