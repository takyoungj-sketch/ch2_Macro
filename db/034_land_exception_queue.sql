-- =============================================================================
-- 토지 거래 예외 대기열 (Exception Queue)
-- 설계 원칙: Master(land_transactions)는 절대 수정하지 않는다.
--            충돌·이상 데이터는 이 테이블에 격리한 뒤 운영자가 검토·해소한다.
-- 관련: docs/DECISIONS.md D-025, pipeline/detect_land_exceptions.py
-- =============================================================================

CREATE TABLE IF NOT EXISTS land_exception_queue (
    id                  BIGSERIAL       PRIMARY KEY,

    -- 충돌 당사자 (land_transactions.id 배열, 같은 거래로 추정되는 행들)
    tx_ids              BIGINT[]        NOT NULL,
    raw_ids             BIGINT[],       -- land_transactions_raw.id

    -- 충돌 거래의 식별 키
    beopjungri_code     CHAR(10),
    contract_date       DATE,
    area_sqm            NUMERIC(12,2),
    total_price_10k     NUMERIC(14,2),
    lot_display         TEXT,

    -- 충돌 내용
    conflict_type       TEXT            NOT NULL,
    -- 'zone_type'         : 동일 거래에 용도지역이 2가지 이상
    -- 'land_category'     : 동일 거래에 지목이 2가지 이상
    -- 'duplicate_raw'     : 완전 동일 내용 raw 중복
    -- 'price_outlier'     : 단가 이상 (추후 확장)

    conflict_values     JSONB           NOT NULL,
    -- 예: {"zone_type": ["보녹", "자녹"], "raw_seq": ["25163", "25166"]}

    -- 처리 상태
    status              TEXT            NOT NULL DEFAULT 'pending',
    -- 'pending'   : 검토 대기
    -- 'resolved'  : 운영자가 정답 선택 완료 → land_correction_rules 에 Rule 등록
    -- 'dismissed' : 정상 데이터임을 확인, 별도 조치 불필요

    -- 운영자 해소 정보
    resolved_value      TEXT,           -- 선택된 정답 값 (예: '보녹')
    resolution_note     TEXT,           -- 근거 메모
    resolved_by         TEXT,
    resolved_at         TIMESTAMPTZ,
    correction_rule_id  BIGINT,         -- 생성된 land_correction_rules.rule_id (FK는 순환 참조라 비적용)

    -- 감지 메타
    detected_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    source_file         TEXT,           -- 감지된 CSV 파일명
    detect_batch        TEXT            -- detect 실행 배치 ID (YYYYMMDD-HHmmss)
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_leq_status
    ON land_exception_queue (status)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_leq_beopjungri
    ON land_exception_queue (beopjungri_code, contract_date);

CREATE INDEX IF NOT EXISTS idx_leq_conflict_type
    ON land_exception_queue (conflict_type, status);

-- 같은 충돌이 중복 등록되지 않도록: (법정동, 계약일, 면적, 금액, 충돌유형)
CREATE UNIQUE INDEX IF NOT EXISTS uq_leq_conflict_key
    ON land_exception_queue (beopjungri_code, contract_date, area_sqm, total_price_10k, conflict_type)
    WHERE status != 'dismissed';

COMMENT ON TABLE  land_exception_queue IS '토지 거래 예외 대기열 — Master 불변 원칙. 충돌·이상 데이터를 격리해 운영자가 해소하면 land_correction_rules 에 Rule 등록.';
COMMENT ON COLUMN land_exception_queue.conflict_type    IS 'zone_type | land_category | duplicate_raw | price_outlier';
COMMENT ON COLUMN land_exception_queue.conflict_values  IS '충돌 값 목록 JSONB. 예: {"zone_type":["보녹","자녹"],"raw_seq":["25163","25166"]}';
COMMENT ON COLUMN land_exception_queue.status           IS 'pending(검토대기) | resolved(Rule등록완료) | dismissed(정상확인)';
