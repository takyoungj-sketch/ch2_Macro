-- 토지 목록 보강. 필지가 하나로 정해진 행의 대장 지번.
-- land_transactions 는 고치지 않는다. 칸의 공개 번지는 그대로 두고, 보강을 켠 호버만 이 값을 쓴다.

ALTER TABLE land_transaction_trait_link
    ADD COLUMN IF NOT EXISTS recovered_lot TEXT;

ALTER TABLE land_transaction_trait_link
    DROP CONSTRAINT IF EXISTS land_trait_recovered_lot_chk;

ALTER TABLE land_transaction_trait_link
    ADD CONSTRAINT land_trait_recovered_lot_chk CHECK (
        recovered_lot IS NULL
        OR (
            link_status IN ('exact', 'label_normalized')
            AND btrim(recovered_lot) <> ''
        )
    );

COMMENT ON COLUMN land_transaction_trait_link.recovered_lot IS
    '일치·표기 정규화 행의 대장 지번(본번-부번, 산). 목록 칸을 바꾸지 않는다. 검증 전.';
