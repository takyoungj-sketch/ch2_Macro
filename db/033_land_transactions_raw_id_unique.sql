-- raw_id 1:1 — 표시 컬럼 백fill UPSERT 중복 INSERT 재발 방지
-- dedupe_land_transactions.py --execute 완료 후 적용 (중복 잔존 시 실패)
CREATE UNIQUE INDEX IF NOT EXISTS uq_land_transactions_raw_id
    ON land_transactions (raw_id)
    WHERE raw_id IS NOT NULL;

COMMENT ON INDEX uq_land_transactions_raw_id IS
    'land_transactions_raw 1행 → land_transactions 1행. hash drift UPSERT 중복 차단.';
