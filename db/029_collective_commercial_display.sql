-- 029: 비주거 집합 거래 표시 컬럼 (주거 026 패턴)

ALTER TABLE collective_commercial_transactions
    ADD COLUMN IF NOT EXISTS buyer_type  VARCHAR(20),
    ADD COLUMN IF NOT EXISTS seller_type VARCHAR(20),
    ADD COLUMN IF NOT EXISTS deal_type   VARCHAR(20);

COMMENT ON COLUMN collective_commercial_transactions.buyer_type IS 'MOLIT 매수';
COMMENT ON COLUMN collective_commercial_transactions.seller_type IS 'MOLIT 매도';
COMMENT ON COLUMN collective_commercial_transactions.deal_type IS 'MOLIT 거래유형';
