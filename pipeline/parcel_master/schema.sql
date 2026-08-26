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
    n_hits       INTEGER      NOT NULL DEFAULT 1,
    PRIMARY KEY (pnu, zone_label)
);

CREATE INDEX IF NOT EXISTS ix_parcel_zone_pnu ON parcel_zone (pnu);
CREATE INDEX IF NOT EXISTS ix_parcel_zone_fine ON parcel_zone (pnu) WHERE NOT is_coarse;

-- D-050 P1: 판본 레지스트리. 미상 재시도는 여기 새 행이 생긴 달에만.
CREATE TABLE IF NOT EXISTS ledger_snapshot (
    source      TEXT        NOT NULL,
    snapshot    TEXT        NOT NULL,
    sido_code   CHAR(2)     NOT NULL,
    kind        TEXT        NOT NULL DEFAULT '',
    loaded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    row_count   BIGINT,
    PRIMARY KEY (source, snapshot, sido_code, kind)
);

-- D-050 P1: 개별공시지가. 그레인 (pnu, price_year). 제품은 최신 1개만 파생.
CREATE TABLE IF NOT EXISTS parcel_land_price (
    pnu           CHAR(19)     NOT NULL,
    price_year    SMALLINT     NOT NULL,
    price_per_m2  NUMERIC      NOT NULL,
    base_date     DATE,
    source_sido   CHAR(2)      NOT NULL,
    snapshot      VARCHAR(16)  NOT NULL,
    PRIMARY KEY (pnu, price_year),
    CONSTRAINT parcel_land_price_amt CHECK (price_per_m2 > 0),
    CONSTRAINT parcel_land_price_year CHECK (price_year BETWEEN 1900 AND 2200)
);
CREATE INDEX IF NOT EXISTS ix_parcel_land_price_pnu ON parcel_land_price (pnu);

-- 확정 매칭 개정 자리. P1에서 적재하지 않음. is_current 자동 전환 금지 (D-050).
CREATE TABLE IF NOT EXISTS match_revision (
    domain      VARCHAR(16) NOT NULL,
    entity_key  TEXT        NOT NULL,
    revision    INTEGER     NOT NULL,
    is_current  BOOLEAN     NOT NULL DEFAULT TRUE,
    approved_at TIMESTAMPTZ,
    note        TEXT,
    PRIMARY KEY (domain, entity_key, revision)
);

COMMENT ON TABLE parcel IS '수요 필지. 표제부(집합·일반)에서 파생. 빈 필지 39M 미적재';
COMMENT ON TABLE building IS '표제부 동 단위. PK = 관리건축물대장PK × 스냅샷. ledger_kind=집합|일반';
COMMENT ON TABLE parcel_zone IS 'AL_D155 용도지역. 복수 라벨·is_coarse. 원본 48GB가 아니라 parcel에 있는 PNU만';
COMMENT ON TABLE ledger_snapshot IS '원본 판본 레지스트리. (source, snapshot, sido_code, kind). 표제부는 kind=집합|일반';
COMMENT ON TABLE parcel_land_price IS 'AL_D151 필지·연도 이력. 광주·전남 구코드 29/46은 PNU를 12로 맵핑';
COMMENT ON TABLE match_revision IS '확정 매칭 값 변경용 자리. 적재 없음. 자동 is_current flip 금지';
