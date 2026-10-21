-- 복합 제품 전환 (2026-10-19). 화면 용도지역(zone_labels)은 유지한다.
-- supply_hold 가 있는 행은 제품 조회에서 붙이지 않는다. 행은 지우지 않는다.
-- zone_contract_year, zone_latest 는 새 칸이다. 화면 문구로 쓰지 않는다.

ALTER TABLE built_transaction_enrichment
    ADD COLUMN IF NOT EXISTS supply_hold TEXT,
    ADD COLUMN IF NOT EXISTS zone_contract_year TEXT,
    ADD COLUMN IF NOT EXISTS zone_latest TEXT;

ALTER TABLE built_transaction_enrichment
    DROP CONSTRAINT IF EXISTS built_enrichment_supply_hold_chk;

ALTER TABLE built_transaction_enrichment
    ADD CONSTRAINT built_enrichment_supply_hold_chk
    CHECK (supply_hold IS NULL OR supply_hold IN (
        'orphaned', 'collective_apartment_d079', 'engine_unlinked'
    ));

COMMENT ON COLUMN built_transaction_enrichment.supply_hold IS
    'orphaned: 원장에 거래 없음. collective_apartment_d079: 집합 공동주택은 확정 건물 연결이 아님. engine_unlinked: 엔진이 연결하지 않음. 행은 남기고 조회에서만 뺀다.';
COMMENT ON COLUMN built_transaction_enrichment.zone_contract_year IS
    '엔진 계약연도 용도지역. 화면의 zone_labels 를 대체하지 않는다.';
COMMENT ON COLUMN built_transaction_enrichment.zone_latest IS
    '엔진 최신 용도지역. 화면의 zone_labels 를 대체하지 않는다.';
