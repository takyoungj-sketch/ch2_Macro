-- 한국부동산원 상업용부동산 임대동향조사 (하위시장/상권). 주거 원장과 조인하지 않음.

CREATE TABLE IF NOT EXISTS rent_sangkwon (
    sec_seq         INTEGER         PRIMARY KEY,
    sec_nm          VARCHAR(80)     NOT NULL UNIQUE,
    district_year   SMALLINT        NOT NULL DEFAULT 2024,
    buld_nm         VARCHAR(80)     NOT NULL DEFAULT '',
    sido            VARCHAR(30)     NOT NULL DEFAULT '',
    geom_geojson    JSONB           NOT NULL,
    bbox_west       DOUBLE PRECISION,
    bbox_south      DOUBLE PRECISION,
    bbox_east       DOUBLE PRECISION,
    bbox_north      DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS ix_rent_sangkwon_sido ON rent_sangkwon (sido);

CREATE TABLE IF NOT EXISTS rent_sangkwon_quarterly (
    id              BIGSERIAL       PRIMARY KEY,
    sec_nm          VARCHAR(80)     NOT NULL,
    sido            VARCHAR(30)     NOT NULL DEFAULT '',
    reb_code        VARCHAR(20)     NOT NULL DEFAULT '',
    asset_kind      VARCHAR(20)     NOT NULL,
    metric          VARCHAR(40)     NOT NULL,
    floor_band      VARCHAR(16)     NOT NULL DEFAULT 'all',
    floor_label     VARCHAR(20)     NOT NULL DEFAULT '',
    year            SMALLINT        NOT NULL,
    quarter         SMALLINT        NOT NULL
                    CHECK (quarter >= 1 AND quarter <= 4),
    value           NUMERIC,
    source_sheet    VARCHAR(8)      NOT NULL,
    CONSTRAINT rent_sangkwon_q_grain_uq UNIQUE (
        sec_nm, asset_kind, metric, floor_band, floor_label, year, quarter
    )
);

CREATE INDEX IF NOT EXISTS ix_rent_sangkwon_q_lookup
    ON rent_sangkwon_quarterly (sec_nm, asset_kind, metric, year);

CREATE TABLE IF NOT EXISTS rent_sangkwon_import_meta (
    id              SMALLINT        PRIMARY KEY DEFAULT 1,
    source_file     TEXT            NOT NULL DEFAULT '',
    latest_year     SMALLINT,
    latest_quarter  SMALLINT,
    n_polygons      INTEGER         NOT NULL DEFAULT 0,
    n_quarterly     INTEGER         NOT NULL DEFAULT 0,
    imported_at     TIMESTAMP       NOT NULL DEFAULT NOW(),
    CONSTRAINT rent_sangkwon_import_meta_one CHECK (id = 1)
);

COMMENT ON TABLE rent_sangkwon IS
    'REB 상권구획 2024. geom_geojson=WGS84. 행정동과 경계가 다름.';
COMMENT ON TABLE rent_sangkwon_quarterly IS
    '하위시장 분기 공표. 104/106(규모별 서울광역) 제외. 109-112는 floor_band=le10/ge11.';
