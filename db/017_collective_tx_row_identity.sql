-- 집합부동산: 토지와 달리 semantic dedupe 하지 않음.
-- 해제 거래만 정제 단계에서 제외하고, 원본 행마다 1건 적재.
-- transaction_hash = SHA-256(asset_type|source_file|source_row_no) — UNIQUE 아님.

DROP INDEX IF EXISTS uix_collective_tx_hash;

CREATE INDEX IF NOT EXISTS ix_collective_tx_hash
    ON collective_transactions (transaction_hash);

COMMENT ON COLUMN collective_transactions.transaction_hash IS
    '원본 행 식별 SHA-256(asset_type|파일명|순번). 집합부동산은 해제 제외 전량 적재(UNIQUE 아님)';
