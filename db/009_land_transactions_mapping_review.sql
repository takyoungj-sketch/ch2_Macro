-- 법정동 코드 매핑 검수 플래그 (clean.py 강화 매핑 연동)
-- 적용: psql -U ... -d land_stats -f db/009_land_transactions_mapping_review.sql

ALTER TABLE land_transactions
    ADD COLUMN IF NOT EXISTS needs_review BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE land_transactions
    ADD COLUMN IF NOT EXISTS mapping_notes VARCHAR(240);

COMMENT ON COLUMN land_transactions.needs_review IS
    'TRUE: 주소→법정동 강한 키 매핑 실패·검수 필요(동명이인 등). 통계 제외 권장.';
COMMENT ON COLUMN land_transactions.mapping_notes IS
    '매핑 시도 요약/실패 사유(예: no_strong_match)';

CREATE INDEX IF NOT EXISTS ix_land_tx_needs_review
    ON land_transactions (needs_review)
    WHERE needs_review = TRUE;
