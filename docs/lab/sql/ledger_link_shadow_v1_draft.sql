-- =============================================================================
-- 초안 — 적용 금지. 대장 연결 결과 공통 소비 계약 v1 섀도 표 (계획 7단계)
-- =============================================================================
-- 설계: docs/lab/LEDGER_CONSUMPTION_CONTRACT_V1_DRAFT.md
-- 유형별 DB(land_stats / built_stats / collective_stats / rent_stats)에 같은 두 표를 둔다.
-- 기존 결과표(land_transaction_trait_link, built_transaction_enrichment, collective_*)와
-- 원장(*_transactions)은 바꾸지 않는다. 롤백은 두 표 DROP.
-- 원장 값(가격·면적·계약일)은 복사하지 않는다. source_digest 로 원장 무변경만 확인한다.
-- 결측·미검증은 상태 열로만 표현하고, 불확실한 값은 채우지 않는다.

CREATE TABLE IF NOT EXISTS ledger_link_header_v1 (
    domain                  TEXT        NOT NULL,
    target_kind             TEXT        NOT NULL,
    target_key              TEXT        NOT NULL,
    link_state              TEXT        NOT NULL,
    link_reason             TEXT,
    link_level              TEXT        NOT NULL,
    parcel_resolved         BOOLEAN     NOT NULL,
    building_id_state       TEXT        NOT NULL,
    bldrgst_pk              TEXT,
    candidate_count         INTEGER,
    hold_flags              TEXT[]      NOT NULL DEFAULT '{}',
    code_resolution         TEXT,
    register_snapshot       CHAR(7),
    register_after_contract BOOLEAN,
    trait_asof              DATE,
    rule_version            TEXT        NOT NULL,
    unverified              BOOLEAN     NOT NULL DEFAULT TRUE,
    verification_basis      TEXT        NOT NULL DEFAULT 'none',
    computed_cycle          CHAR(6)     NOT NULL,
    source_digest           CHAR(32),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (domain, target_key),
    CONSTRAINT llh_domain_chk CHECK (domain IN ('land', 'built', 'collective', 'rent')),
    CONSTRAINT llh_kind_chk CHECK (target_kind IN ('transaction', 'building_key')),
    CONSTRAINT llh_state_chk CHECK (link_state IN ('linked', 'unlinked', 'not_applicable')),
    -- building = 표제부 한 동(관리번호) · parcel = 필지까지(동 미정) · complex = 집합 단지
    CONSTRAINT llh_level_chk CHECK (link_level IN ('building', 'parcel', 'complex', 'none')),
    CONSTRAINT llh_id_chk CHECK (building_id_state IN (
        'confirmed', 'candidates_agree', 'candidates_conflict',
        'aggregated', 'weak_match', 'not_applicable'
    )),
    CONSTRAINT llh_pk_only_confirmed_chk CHECK (bldrgst_pk IS NULL OR building_id_state = 'confirmed'),
    CONSTRAINT llh_linked_level_chk CHECK ((link_state = 'linked') = (link_level <> 'none')),
    CONSTRAINT llh_code_chk CHECK (code_resolution IS NULL OR code_resolution IN (
        'held', 'reissued_1to1', 'current_code', 'bridge_12', 'prefix_v1'
    )),
    CONSTRAINT llh_verify_chk CHECK (verification_basis IN ('none', 'auto_crosscheck', 'sample')),
    CONSTRAINT llh_unverified_chk CHECK (unverified OR verification_basis = 'sample')
);

CREATE TABLE IF NOT EXISTS ledger_link_value_v1 (
    domain          TEXT        NOT NULL,
    target_key      TEXT        NOT NULL,
    variable        TEXT        NOT NULL,
    value_num       NUMERIC,
    value_text      TEXT,
    value_state     TEXT        NOT NULL,
    -- building = 그 동의 값 · parcel = 필지 값 · complex_aggregate = 단지(여러 동·단지) 합산값
    value_level     TEXT        NOT NULL,
    source          TEXT,
    basis_date      DATE,
    timing          TEXT,
    change_risk     TEXT        NOT NULL DEFAULT 'none',
    use_approved    BOOLEAN     NOT NULL DEFAULT FALSE,
    PRIMARY KEY (domain, target_key, variable),
    FOREIGN KEY (domain, target_key) REFERENCES ledger_link_header_v1 (domain, target_key) ON DELETE CASCADE,
    CONSTRAINT llv_state_chk CHECK (value_state IN (
        'confirmed', 'candidates_agree', 'conflict_missing', 'source_missing', 'undetermined', 'not_linked'
    )),
    CONSTRAINT llv_level_chk CHECK (value_level IN ('building', 'parcel', 'complex_aggregate')),
    -- 값은 확정·후보 동일일 때만. 나머지 상태는 값 없음.
    CONSTRAINT llv_value_only_when_known_chk CHECK (
        (value_state IN ('confirmed', 'candidates_agree')) = (value_num IS NOT NULL OR value_text IS NOT NULL)
    ),
    -- 후보 동일은 표본 판정 뒤 사용자 승인으로만 켠다. 그 외 확정 아닌 상태는 항상 꺼짐.
    CONSTRAINT llv_approved_chk CHECK (NOT use_approved OR value_state IN ('confirmed', 'candidates_agree')),
    -- 단지 합산값은 개별 건물의 확정 속성이 아니다.
    CONSTRAINT llv_aggregate_not_building_chk CHECK (value_level <> 'complex_aggregate' OR value_state <> 'candidates_agree'),
    CONSTRAINT llv_source_chk CHECK (source IS NULL OR source IN (
        'building_ledger', 'land_trait_slim', 'al_d155', 'land_ledger', 'kapt', 'tx_source'
    )),
    CONSTRAINT llv_timing_chk CHECK (timing IS NULL OR timing IN (
        'contract_year', 'contract_year_estimated', 'previous_year', 'adjacent_before', 'adjacent_after',
        'pre_contract_register', 'post_contract_register', 'latest'
    )),
    CONSTRAINT llv_risk_chk CHECK (change_risk IN ('none', 'next_base_differs', 'undetermined'))
);

CREATE INDEX IF NOT EXISTS ix_llv_variable_state ON ledger_link_value_v1 (domain, variable, value_state);

COMMENT ON TABLE ledger_link_header_v1 IS
    '대장 연결 머리 — 대상 하나에 한 행. 미연결·해당 없음도 행으로 둔다. linked 는 정확함이 아니다.';
COMMENT ON TABLE ledger_link_value_v1 IS
    '대장 속성 값 — 대상×변수 한 행. 확정·후보 동일만 값. 단지 합산값은 complex_aggregate.';
COMMENT ON COLUMN ledger_link_header_v1.source_digest IS
    '원장 행 지문(md5). 원장 값은 복사하지 않고 무변경 확인에만 쓴다.';
