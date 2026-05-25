-- 011: 거래 목록/UI용 번지·지분구분 원문·거래유형 (정제 파이프 UPSERT 로 채움)
ALTER TABLE land_transactions
    ADD COLUMN IF NOT EXISTS lot_display VARCHAR(64),
    ADD COLUMN IF NOT EXISTS partial_ownership_label VARCHAR(128),
    ADD COLUMN IF NOT EXISTS deal_type VARCHAR(128);

COMMENT ON COLUMN land_transactions.lot_display IS '번지 표시 문자열 (엑셀 번지 또는 본번-부번)';
COMMENT ON COLUMN land_transactions.partial_ownership_label IS '원천 지분구분 문자열';
COMMENT ON COLUMN land_transactions.deal_type IS '원천 거래유형(거래유형/dealingGbn 등) 문자열';
