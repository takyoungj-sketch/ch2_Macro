-- 토지 대장 연결 재판정 기록. 설계·운영: docs/lab/LAND_LINK_V2_ROLLOUT_PLAN_20261110.md.
-- 재판정은 미연결 행만 바꾼다. 바꾸기 전 상태를 이 테이블에 남긴다.
-- 연결 행(exact, label_normalized)은 이 경로로 덮지 않는다.
-- 적용: pipeline/parcel_master/land_trait_link_rejudge.py --apply (현재 --target honam_v2만 허용).

CREATE TABLE IF NOT EXISTS land_transaction_trait_link_event (
    event_id                  BIGSERIAL   PRIMARY KEY,
    transaction_hash          CHAR(64)    NOT NULL,
    cycle_id                  TEXT        NOT NULL,
    target                    TEXT        NOT NULL,
    previous_status           TEXT        NOT NULL,
    previous_rule_version     TEXT        NOT NULL,
    previous_price_status     TEXT        NOT NULL,
    previous_trait_asof       DATE,
    previous_ledger_beopjungri_code CHAR(10),
    previous_code_resolution  TEXT        NOT NULL,
    new_status                TEXT        NOT NULL,
    new_rule_version          TEXT        NOT NULL,
    new_price_status          TEXT        NOT NULL,
    new_trait_asof            DATE,
    ledger_latest_asof        DATE        NOT NULL,
    judged_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    applied_by                TEXT        NOT NULL,
    CONSTRAINT land_trait_link_event_target_chk CHECK (target IN ('honam_v2', 'new_plate')),
    CONSTRAINT land_trait_link_event_previous_unlinked_chk CHECK (
        previous_status NOT IN ('exact', 'label_normalized')
    )
);

CREATE INDEX IF NOT EXISTS land_transaction_trait_link_event_hash_idx
    ON land_transaction_trait_link_event (transaction_hash, judged_at);
CREATE INDEX IF NOT EXISTS land_transaction_trait_link_event_cycle_idx
    ON land_transaction_trait_link_event (cycle_id);

ALTER TABLE land_transaction_trait_link
    ADD COLUMN IF NOT EXISTS judged_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS ledger_latest_asof DATE;

COMMENT ON TABLE land_transaction_trait_link_event IS
    '토지 대장 연결 재판정 기록. 미연결 행이 바뀔 때만 한 행. 되돌리기는 previous_* 값으로 한다.';
COMMENT ON COLUMN land_transaction_trait_link.judged_at IS
    '마지막 판정 시각. NULL이면 created_at에 처음 판정한 뒤 바뀌지 않음.';
COMMENT ON COLUMN land_transaction_trait_link.ledger_latest_asof IS
    '판정에 쓴 대장의 최신 판 날짜. NULL이면 재판정 전(2026-07-20 판 기준 적재).';
