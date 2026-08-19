-- =============================================================================
-- 064: 신규아파트 회귀모델 트랙 A — 단지 × 연도 마트
-- =============================================================================
-- SSOT: docs/NEW_APARTMENT_REGRESSION_DESIGN.md
-- 품질지수(050)와 분리. Y는 단지 중앙값 ㎡당 매매.

CREATE TABLE IF NOT EXISTS new_apartment_complex_year (
    id                      BIGSERIAL PRIMARY KEY,
    sido_code               CHAR(2)      NOT NULL,
    sigungu_code            CHAR(5)      NOT NULL,
    building_key            CHAR(64)     NOT NULL,
    calendar_year           SMALLINT     NOT NULL,
    asset_type              VARCHAR(20)  NOT NULL DEFAULT 'apartment',

    y_median_unit_price     NUMERIC(14, 4) NOT NULL,
    y_mean_unit_price       NUMERIC(14, 4),
    n_tx                    INTEGER      NOT NULL,

    building_year           SMALLINT,
    approved_year           SMALLINT,
    age                     SMALLINT,
    vintage                 VARCHAR(16),

    match_tier              CHAR(1),
    builder_group           VARCHAR(200),
    structure_group         VARCHAR(20),
    households              INTEGER,
    max_floor               INTEGER,
    parking_per_household   NUMERIC(8, 3),
    danji_class             VARCHAR(40),
    attr_quality_flags      VARCHAR(120),

    beopjungri_code         CHAR(10),
    lot_number              VARCHAR(64),
    uqa_code                VARCHAR(16),
    uqa_label               VARCHAR(80),
    zone_compact            VARCHAR(8),
    zone_resolution         VARCHAR(16)  NOT NULL DEFAULT 'missing',
    land_p50                NUMERIC(14, 2),
    land_n                  INTEGER,

    sigungu_sale_p50_lag    NUMERIC(14, 4),
    sigungu_rent_p50_lag    NUMERIC(14, 4),
    eup_population          NUMERIC(14, 2),

    created_at              TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_nacy_grain
    ON new_apartment_complex_year (sido_code, building_key, calendar_year, asset_type);

CREATE INDEX IF NOT EXISTS ix_nacy_sigungu_year
    ON new_apartment_complex_year (sigungu_code, calendar_year);

COMMENT ON TABLE new_apartment_complex_year IS
    '신규아파트 회귀 트랙 A 학습 셀 — 단지×연도. 품질지수 테이블과 무관';
