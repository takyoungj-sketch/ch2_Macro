-- 축약대장 로컬 DB (parcel_master). VPS에 올리지 않는다.
-- 설계: docs/PARCEL_MASTER_DESIGN.md §5. 파일럿은 표제부 「집합」 대전·충북 행만.

CREATE TABLE IF NOT EXISTS parcel (
    pnu               CHAR(19)     PRIMARY KEY,
    beopjungri_code   CHAR(10)     NOT NULL,
    bun               CHAR(4)      NOT NULL,
    ji                CHAR(4)      NOT NULL,
    sido_code         CHAR(2)      NOT NULL,
    sigungu_code      CHAR(5)      NOT NULL,
    jimok_code        CHAR(2),
    land_area         NUMERIC,
    land_area_source  VARCHAR(16),
    first_seen        CHAR(7)      NOT NULL,
    last_seen         CHAR(7)      NOT NULL,
    n_buildings       INTEGER
);

CREATE TABLE IF NOT EXISTS building (
    mgmt_pk           VARCHAR(32)  NOT NULL,
    snapshot          CHAR(7)      NOT NULL,
    pnu               CHAR(19)     NOT NULL,
    beopjungri_code   CHAR(10)     NOT NULL,
    sido_code         CHAR(2)      NOT NULL,
    ledger_kind       VARCHAR(8)   NOT NULL,
    building_name     VARCHAR(200),
    dong_name         VARCHAR(80),
    structure_name    VARCHAR(60),
    structure_group   VARCHAR(16),
    main_purpose      VARCHAR(80),
    purpose_detail    VARCHAR(120),
    households        INTEGER,
    floors_above      INTEGER,
    floors_below      INTEGER,
    gross_area        NUMERIC,
    arch_area         NUMERIC,
    plat_area         NUMERIC,
    title_land_area   NUMERIC,
    approve_date      CHAR(8),
    PRIMARY KEY (mgmt_pk, snapshot)
);

CREATE INDEX IF NOT EXISTS ix_building_pnu ON building (pnu);
CREATE INDEX IF NOT EXISTS ix_building_sido_snap ON building (sido_code, snapshot);
CREATE INDEX IF NOT EXISTS ix_parcel_sido ON parcel (sido_code);

CREATE TABLE IF NOT EXISTS parcel_zone (
    pnu          CHAR(19)     NOT NULL,
    zone_label   VARCHAR(80)  NOT NULL,
    zone_family  VARCHAR(16),
    is_coarse    BOOLEAN      NOT NULL DEFAULT FALSE,
    source       VARCHAR(16)  NOT NULL,
    snapshot     VARCHAR(16)  NOT NULL,
    PRIMARY KEY (pnu, zone_label)
);

CREATE INDEX IF NOT EXISTS ix_parcel_zone_pnu ON parcel_zone (pnu);
CREATE INDEX IF NOT EXISTS ix_parcel_zone_fine ON parcel_zone (pnu) WHERE NOT is_coarse;

COMMENT ON TABLE parcel IS '건물 있는 필지. 표제부 「집합」에서 파생. 전국 스키마, 행은 적재한 시도만';
COMMENT ON TABLE building IS '표제부 동 단위. PK = 관리건축물대장PK × 스냅샷. ledger_kind=집합';
COMMENT ON TABLE parcel_zone IS 'AL_D155 용도지역. 복수 라벨·is_coarse. 원본 48GB가 아니라 parcel에 있는 PNU만';
