-- 집합부동산 거래 원장 — 모달·거래목록 표시 컬럼 (토지 lot_display·deal_type 패턴)

ALTER TABLE collective_transactions
    ADD COLUMN IF NOT EXISTS buyer_type   VARCHAR(20),
    ADD COLUMN IF NOT EXISTS seller_type  VARCHAR(20),
    ADD COLUMN IF NOT EXISTS deal_type    VARCHAR(40);

COMMENT ON COLUMN collective_transactions.buyer_type IS '매수자 구분 (개인·법인 등)';
COMMENT ON COLUMN collective_transactions.seller_type IS '매도자 구분';
COMMENT ON COLUMN collective_transactions.deal_type IS '거래유형 (중개거래·직거래 등)';
