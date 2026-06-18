-- 지역선택 재구축: 매핑 메타·시군구 구조 메타
-- 적용: psql "$BUILT_DATABASE_URL" -f db/022_region_rebuild.sql
--       psql "$COLLECTIVE_DATABASE_URL" -f db/022_region_rebuild.sql

-- built_transactions
ALTER TABLE built_transactions
    ADD COLUMN IF NOT EXISTS needs_review BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE built_transactions
    ADD COLUMN IF NOT EXISTS mapping_notes TEXT;

CREATE INDEX IF NOT EXISTS ix_built_tx_beopjungri
    ON built_transactions (beopjungri_code)
    WHERE beopjungri_code IS NOT NULL AND btrim(beopjungri_code::text) <> '';

-- collective_transactions
ALTER TABLE collective_transactions
    ADD COLUMN IF NOT EXISTS needs_review BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE collective_transactions
    ADD COLUMN IF NOT EXISTS mapping_notes TEXT;

CREATE INDEX IF NOT EXISTS ix_collective_tx_beopjungri
    ON collective_transactions (beopjungri_code)
    WHERE beopjungri_code IS NOT NULL AND btrim(beopjungri_code::text) <> '';

-- 시군구별 주소 구조 (built / collective 각 DB에 동일 스키마)
CREATE TABLE IF NOT EXISTS region_sigungu_meta (
    id                  BIGSERIAL PRIMARY KEY,
    asset_domain        VARCHAR(20)  NOT NULL,
    asset_type          VARCHAR(20),
    sido_code           CHAR(2)      NOT NULL,
    sido_name           VARCHAR(30)  NOT NULL,
    sigungu_code        CHAR(5),
    sigungu_name        VARCHAR(60)  NOT NULL,
    addr2_token         VARCHAR(30)  NOT NULL,
    structure_type      VARCHAR(20)  NOT NULL,
    leaf_level          VARCHAR(10)  NOT NULL,
    has_ri              BOOLEAN      NOT NULL DEFAULT FALSE,
    tx_count            BIGINT       NOT NULL DEFAULT 0,
    mapped_tx_count     BIGINT       NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT region_sigungu_meta_uq UNIQUE (
        asset_domain, COALESCE(asset_type, ''), sido_code, addr2_token
    )
);

COMMENT ON TABLE region_sigungu_meta IS
    '시군구(addr2)별 주소 깊이·리 보유 — detect_region_structure 런타임 대체';
COMMENT ON COLUMN region_sigungu_meta.structure_type IS 'GU | FLAT | FLAT_SIDO';
COMMENT ON COLUMN region_sigungu_meta.leaf_level IS 'addr3=flat, addr4=구-동';

CREATE INDEX IF NOT EXISTS ix_rsm_domain_sido
    ON region_sigungu_meta (asset_domain, sido_code, addr2_token);
