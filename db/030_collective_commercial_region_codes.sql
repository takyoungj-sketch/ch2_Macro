-- 집합상가·집합공장 — beopjungri_code 통일 (토지·집합·복합과 동일 ingest)
-- 적용: psql "$COLLECTIVE_DATABASE_URL" -f db/030_collective_commercial_region_codes.sql

ALTER TABLE collective_commercial_transactions
    ADD COLUMN IF NOT EXISTS beopjungri_code CHAR(10),
    ADD COLUMN IF NOT EXISTS sido_code CHAR(2),
    ADD COLUMN IF NOT EXISTS sigungu_code CHAR(5),
    ADD COLUMN IF NOT EXISTS eupmyeondong_code CHAR(8),
    ADD COLUMN IF NOT EXISTS needs_review BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS mapping_notes TEXT;

ALTER TABLE commercial_clusters
    ADD COLUMN IF NOT EXISTS beopjungri_code CHAR(10),
    ADD COLUMN IF NOT EXISTS sido_code CHAR(2),
    ADD COLUMN IF NOT EXISTS sigungu_code CHAR(5),
    ADD COLUMN IF NOT EXISTS eupmyeondong_code CHAR(8);

CREATE INDEX IF NOT EXISTS ix_cc_tx_beopjungri
    ON collective_commercial_transactions (beopjungri_code)
    WHERE beopjungri_code IS NOT NULL AND btrim(beopjungri_code::text) <> '';

CREATE INDEX IF NOT EXISTS ix_cc_tx_sigungu
    ON collective_commercial_transactions (sigungu_code)
    WHERE sigungu_code IS NOT NULL AND btrim(sigungu_code::text) <> '';

COMMENT ON COLUMN collective_commercial_transactions.beopjungri_code IS
    'region_codes 매핑 — attach_beopjungri_codes (cluster_key와 별도, 지역 필터·Profile용)';
