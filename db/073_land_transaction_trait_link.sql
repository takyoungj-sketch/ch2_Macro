-- 토지 거래목록 보강. land_transactions 는 UPDATE 하지 않는다.
-- 키는 transaction_hash. 연결 대상이 아니거나 아직 계산하지 않은 거래는 행이 없다.
-- 공시지가는 exact / label_normalized 이고 금액이 하나로 정해진 경우만 채운다.
-- FK 없음: 월간 적재가 원장 행을 갈아끼워도 보강 행이 삭제를 막지 않게 한다.

CREATE TABLE IF NOT EXISTS land_transaction_trait_link (
    transaction_hash        CHAR(64) PRIMARY KEY,
    link_status             TEXT        NOT NULL,
    price_status            TEXT        NOT NULL,
    official_price_won      NUMERIC,
    price_year              SMALLINT,
    trait_asof              DATE,
    ledger_beopjungri_code  CHAR(10),
    code_resolution         TEXT        NOT NULL,
    unverified              BOOLEAN     NOT NULL DEFAULT TRUE,
    rule_version            TEXT        NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT land_trait_link_status_chk CHECK (
        link_status IN (
            'exact',
            'label_normalized',
            'multiple_candidates',
            'other_unmatched',
            'clean_precontract_traits_differ',
            'label_normalized_traits_differ',
            'post_contract_only',
            'no_precontract_observation',
            'true_conflict'
        )
    ),
    CONSTRAINT land_trait_price_status_chk CHECK (
        price_status IN ('same_year', 'previous_year', 'price_conflict', 'price_missing', 'none')
    ),
    CONSTRAINT land_trait_price_only_when_unique_chk CHECK (
        link_status IN ('exact', 'label_normalized')
        OR price_status = 'none'
    ),
    CONSTRAINT land_trait_price_amount_chk CHECK (
        (
            price_status IN ('same_year', 'previous_year')
            AND official_price_won IS NOT NULL
            AND price_year IS NOT NULL
        )
        OR (
            price_status IN ('price_conflict', 'price_missing', 'none')
            AND official_price_won IS NULL
            AND price_year IS NULL
        )
    ),
    CONSTRAINT land_trait_resolution_chk CHECK (
        code_resolution IN ('held', 'reissued_1to1', 'current_code')
    ),
    CONSTRAINT land_trait_unverified_chk CHECK (unverified)
);

COMMENT ON TABLE land_transaction_trait_link IS
    '토지특성 대장 연결 결과. 원장 무수정. 미계산은 행 없음. 공시지가는 필지가 하나이고 금액이 하나일 때만.';
COMMENT ON COLUMN land_transaction_trait_link.transaction_hash IS
    'land_transactions.transaction_hash. id 는 월간 적재에서 바뀔 수 있다.';
COMMENT ON COLUMN land_transaction_trait_link.trait_asof IS
    '연결에 쓴 특성의 데이터기준일자. 계약일 이전 최신 판.';
COMMENT ON COLUMN land_transaction_trait_link.official_price_won IS
    '공시지가(원/㎡). price_conflict·price_missing·미연결은 NULL.';
COMMENT ON COLUMN land_transaction_trait_link.unverified IS
    '이 규칙 버전은 검증 전 연결만 저장한다.';
