-- =============================================================================
-- 051: 집합(주거) 2단계 특성회귀 + 블록 L 지역 매크로 mart
-- =============================================================================
-- 설계 SSOT: docs/COLLECTIVE_TWO_STAGE_HEDONIC_DESIGN.md §3 · §4
-- 위치 블록·AL_D155: apt_regional_regression plan (P4 · block L)

CREATE TABLE IF NOT EXISTS collective_attribute_effects (
    id                  BIGSERIAL PRIMARY KEY,
    as_of_month         DATE         NOT NULL,
    window_years        SMALLINT     NOT NULL,
    asset_type          VARCHAR(20)  NOT NULL,
    spec                CHAR(1)      NOT NULL,   -- A | B | C | L
    scope_level         VARCHAR(10)  NOT NULL,   -- national | sido | sigungu
    scope_code          VARCHAR(5),
    term                VARCHAR(80)  NOT NULL,
    term_label          VARCHAR(120) NOT NULL,
    term_kind           VARCHAR(20)  NOT NULL,
    coef                NUMERIC(12, 6) NOT NULL,
    pct_effect          NUMERIC(10, 4),
    se                  NUMERIC(12, 6),
    p_value             NUMERIC(10, 6),
    ci_low              NUMERIC(12, 6),
    ci_high             NUMERIC(12, 6),
    boot_ci_low         NUMERIC(12, 6),
    boot_ci_high        NUMERIC(12, 6),
    n_buildings         INTEGER,
    vif                 NUMERIC(10, 4),
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_cae_grain
    ON collective_attribute_effects
       (as_of_month, window_years, asset_type, spec, scope_level, scope_code, term);

CREATE TABLE IF NOT EXISTS collective_attribute_effects_model (
    id                  BIGSERIAL PRIMARY KEY,
    as_of_month         DATE         NOT NULL,
    window_years        SMALLINT     NOT NULL,
    asset_type          VARCHAR(20)  NOT NULL,
    spec                CHAR(1)      NOT NULL,
    scope_level         VARCHAR(10)  NOT NULL,
    scope_code          VARCHAR(5),
    include_location    BOOLEAN      NOT NULL DEFAULT FALSE,
    weighting           VARCHAR(8)   NOT NULL DEFAULT 'wls',
    n_buildings         INTEGER      NOT NULL,
    adj_r_squared       NUMERIC(8, 5),
    equation            TEXT,
    warnings            TEXT,
    sample_breakdown    JSONB,
    reference_categories JSONB,
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_caem_grain
    ON collective_attribute_effects_model
       (as_of_month, window_years, asset_type, spec, scope_level, scope_code, include_location, weighting);

COMMENT ON TABLE collective_attribute_effects IS
    '2단계(스펙 A/B/C) 및 블록 L(스펙 L) 회귀 계수 — term_kind: brand|builder|scale|structure|vintage|location|macro|other';

CREATE TABLE IF NOT EXISTS collective_building_location_enrichment (
    id                  BIGSERIAL PRIMARY KEY,
    as_of_month         DATE         NOT NULL,
    window_years        SMALLINT     NOT NULL,
    asset_type          VARCHAR(20)  NOT NULL,
    building_key        CHAR(64)     NOT NULL,
    beopjungri_code     CHAR(10),
    lot_number          VARCHAR(64),
    eup_population      NUMERIC(14, 2),
    rent_jeonse_p50     NUMERIC(14, 4),
    uqa_code            VARCHAR(16),
    uqa_label           VARCHAR(80),
    land_p50_zone       NUMERIC(14, 2),
    zone_resolution     VARCHAR(16)  NOT NULL DEFAULT 'missing',
    pilot_sido_code     CHAR(2),
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_cble_grain
    ON collective_building_location_enrichment
       (as_of_month, window_years, asset_type, building_key);

COMMENT ON TABLE collective_building_location_enrichment IS
    '2단계 옵션 위치 블록 — 읍 인구·단지 임대 P50·AL_D155 UQA→토지 P50 (단지별)';
