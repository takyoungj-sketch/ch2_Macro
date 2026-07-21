-- =============================================================================
-- 046: region_code_history — Built / Collective 공유용 DDL
-- =============================================================================
-- 설계: docs/REGION_CODE_LAYERS.md §7 (공통 지역 마스터)
-- 적용 대상 DB: built_stats, collective_stats (land_stats 는 014에 이미 존재)
--
-- 현재 운영: land_stats.region_code_history 를 SSOT로 동기화(sync_region_code_history.py).
-- 장기: region_codes + region_code_history 를 CH2 Macro 공통 지역 마스터로 독립.
-- =============================================================================

CREATE TABLE IF NOT EXISTS region_code_history (
    id                  BIGSERIAL PRIMARY KEY,

    from_code           CHAR(10)     NOT NULL,
    to_code             CHAR(10)     NOT NULL,

    change_type         VARCHAR(20)  NOT NULL,
    -- merge | split | rename | boundary | code_reissue

    effective_from      DATE         NOT NULL,
    effective_to        DATE,

    source_note         TEXT,
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW(),

    CONSTRAINT region_code_history_type_chk
        CHECK (change_type IN ('merge', 'split', 'rename', 'boundary', 'code_reissue'))
);

COMMENT ON TABLE region_code_history IS
    '법정동 코드 변경 이력 — 원장 beopjungri_code 보존, 분석·mart 는 to_code(canonical) 사용 (D-028)';

CREATE INDEX IF NOT EXISTS ix_region_code_history_from
    ON region_code_history (from_code, effective_from);

CREATE INDEX IF NOT EXISTS ix_region_code_history_to
    ON region_code_history (to_code, effective_from);
