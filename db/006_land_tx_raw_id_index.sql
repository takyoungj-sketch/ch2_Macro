-- land_transactions.raw_id 로 미처리 원천(raw) 조회 시 부분 인덱스(NOT NULL)
-- (clean.py fetch_unprocessed_raw 의 NOT EXISTS 에 유리)
CREATE INDEX IF NOT EXISTS ix_land_tx_raw_id
    ON land_transactions (raw_id)
    WHERE raw_id IS NOT NULL;
