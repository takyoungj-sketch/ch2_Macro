-- D-047: 복합 거래 보강. 원장 UPDATE 금지. 미상은 행을 만들지 않는다.
-- 키는 transaction_hash (월간 purge가 id 를 재발급한다).
-- 확정 행은 ON CONFLICT DO NOTHING 으로 동결. 미상만 다음 사이클에서 INSERT.
-- 적용: psql "$BUILT_DATABASE_URL" -f db/068_built_transaction_enrichment.sql

CREATE TABLE IF NOT EXISTS built_transaction_enrichment (
    transaction_hash    CHAR(64) PRIMARY KEY
        REFERENCES built_transactions (transaction_hash),
    recovered_lot       TEXT        NOT NULL,
    bldrgst_pk          TEXT,
    structure_raw       TEXT,
    structure_group     TEXT,
    max_floor           SMALLINT,
    approve_year        SMALLINT,
    zone_labels         TEXT[]      NOT NULL DEFAULT '{}',
    zone_source         TEXT        CHECK (zone_source IS NULL OR zone_source IN ('source', 'al_d155')),
    zone_multi          BOOLEAN     NOT NULL DEFAULT FALSE,
    match_tier          TEXT        NOT NULL CHECK (match_tier IN ('A1', 'A2')),
    match_rule          TEXT        NOT NULL,
    land_area_source    TEXT        CHECK (land_area_source IS NULL OR land_area_source IN ('title', 'summary', 'land_ledger')),
    n_range             INTEGER,
    n_exact             INTEGER,
    snapshots_matched   TEXT[]      NOT NULL DEFAULT '{}',
    coverage_scope      TEXT        NOT NULL,
    matched_cycle       CHAR(6)     NOT NULL,
    evidence            JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE built_transaction_enrichment IS
    '복합 마스킹 복원 확정분만. 원장 무수정. 미상은 행 없음 (D-047). 구조·지번은 표제부 조인';
COMMENT ON COLUMN built_transaction_enrichment.transaction_hash IS
    'built_transactions.transaction_hash. id 금지 — 월간 배치가 id 재발급';
COMMENT ON COLUMN built_transaction_enrichment.recovered_lot IS
    '결합 키. 화면 지번 노출은 별도 결정 (D-046)';

CREATE INDEX IF NOT EXISTS ix_built_enrich_tier
    ON built_transaction_enrichment (match_tier);
CREATE INDEX IF NOT EXISTS ix_built_enrich_cycle
    ON built_transaction_enrichment (matched_cycle);
