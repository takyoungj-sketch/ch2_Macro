-- 복합부동산 원장 재구축 (MOLIT raw base) — Phase A
-- 적용: psql "$BUILT_DATABASE_URL" -f db/028_built_ledger_rebuild.sql

ALTER TABLE built_transactions
    ADD COLUMN IF NOT EXISTS road_width_label VARCHAR(32);

ALTER TABLE built_transactions
    ADD COLUMN IF NOT EXISTS road_name VARCHAR(64);

ALTER TABLE built_transactions
    ADD COLUMN IF NOT EXISTS display_address VARCHAR(256);

ALTER TABLE built_transactions
    ADD COLUMN IF NOT EXISTS deal_type VARCHAR(40);

COMMENT ON COLUMN built_transactions.road_width_label IS 'MOLIT 도로조건 원문 (8m이하, 25m미만 등)';
COMMENT ON COLUMN built_transactions.road_name IS 'MOLIT 도로명';
COMMENT ON COLUMN built_transactions.display_address IS '목록 표시용 — addr3·4·5·번지·(도로명) 규칙 B';
COMMENT ON COLUMN built_transactions.deal_type IS 'MOLIT 거래유형 (중개거래 등)';
COMMENT ON COLUMN built_transactions.road_code IS 'DEPRECATED — Phase A ingest NULL. 회귀는 road_width_label 더미 (Phase B)';

CREATE INDEX IF NOT EXISTS ix_built_tx_contract_date
    ON built_transactions (contract_date)
    WHERE contract_date IS NOT NULL;
