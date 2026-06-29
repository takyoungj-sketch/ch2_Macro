-- =============================================================================
-- 토지 거래 보정 규칙 엔진 (Correction Rule Engine)
-- 설계 원칙: 운영자가 확인한 예외 처리 기준을 DB에 저장한다.
--            Rule이 있으면 land_transactions_resolved VIEW에서 자동 반영.
--            Rule 삭제 → 즉시 원래 Master 값 복원.
-- 관련: docs/DECISIONS.md D-025, db/036_land_transactions_resolved_view.sql
-- =============================================================================

CREATE TABLE IF NOT EXISTS land_correction_rules (
    rule_id             BIGSERIAL       PRIMARY KEY,

    -- 매칭 조건 (NULL = 와일드카드)
    -- 좁을수록 정밀, 넓을수록 범용
    beopjungri_code     CHAR(10),
    contract_year       INT,
    contract_month      INT,
    contract_day        INT,
    area_sqm            NUMERIC(12,2),
    total_price_10k     NUMERIC(14,2),
    lot_display         TEXT,           -- 지번이 특정되는 경우에만 사용

    -- 충돌 유형
    conflict_type       TEXT            NOT NULL,
    -- 'zone_type'     : 용도지역 충돌
    -- 'land_category' : 지목 충돌

    -- 보정 방식
    action              TEXT            NOT NULL,
    -- 'set_zone_type'      : zone_type_resolved = action_value
    -- 'set_land_category'  : land_category_resolved = action_value
    -- 'prefer_seq_min'     : 순번 최소 raw 기준 (action_value 불필요)

    action_value        TEXT,           -- 예: '보녹', '자녹', '1주'

    -- 메타
    basis               TEXT,           -- 근거. 예: '국토부 충북_토지_매매_2025.csv 순번25163 원본 보전녹지지역 확인'
    created_by          TEXT            NOT NULL DEFAULT 'system',
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,

    -- 출처 예외 (NULL이면 수동 등록)
    source_exception_id BIGINT          REFERENCES land_exception_queue(id) ON DELETE SET NULL
);

-- 인덱스 (VIEW에서 LATERAL JOIN 성능)
CREATE INDEX IF NOT EXISTS idx_lcr_active_zone
    ON land_correction_rules (beopjungri_code, contract_year, contract_month, contract_day, area_sqm, total_price_10k)
    WHERE is_active = TRUE AND conflict_type = 'zone_type';

CREATE INDEX IF NOT EXISTS idx_lcr_active_land
    ON land_correction_rules (beopjungri_code, contract_year, contract_month, contract_day, area_sqm, total_price_10k)
    WHERE is_active = TRUE AND conflict_type = 'land_category';

COMMENT ON TABLE  land_correction_rules IS '토지 거래 보정 규칙. land_transactions_resolved VIEW가 이 테이블을 참조해 Master 수정 없이 분석 경로에서 값을 보정한다.';
COMMENT ON COLUMN land_correction_rules.conflict_type  IS 'zone_type | land_category';
COMMENT ON COLUMN land_correction_rules.action         IS 'set_zone_type | set_land_category | prefer_seq_min';
COMMENT ON COLUMN land_correction_rules.action_value   IS 'action 적용 값. 예: 보녹. prefer_seq_min 이면 불필요.';
COMMENT ON COLUMN land_correction_rules.basis          IS '운영자가 남기는 근거. 원본 CSV 파일명·순번·확인 방법 등.';
