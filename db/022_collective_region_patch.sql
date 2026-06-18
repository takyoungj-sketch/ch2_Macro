-- collective_stats 전용: 022 중 collective_transactions·인덱스만 (built_transactions 제외)

ALTER TABLE collective_transactions
    ADD COLUMN IF NOT EXISTS needs_review BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE collective_transactions
    ADD COLUMN IF NOT EXISTS mapping_notes TEXT;

CREATE INDEX IF NOT EXISTS ix_collective_tx_beopjungri
    ON collective_transactions (beopjungri_code)
    WHERE beopjungri_code IS NOT NULL AND btrim(beopjungri_code::text) <> '';
