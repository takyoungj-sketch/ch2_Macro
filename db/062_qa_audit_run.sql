-- =============================================================================
-- 062: qa_audit_run — 지역 단위 QA 검증 런 로그
-- =============================================================================
-- 대상 DB: collective_stats (V1 집합 아파트)
-- QA 엔진은 원장·마트를 UPDATE 하지 않는다. 이 테이블 INSERT 만 허용.
-- 설계: docs/QA_REGION_AUDIT_PLAN.md
-- =============================================================================

CREATE TABLE IF NOT EXISTS qa_audit_run (
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trigger         VARCHAR(16) NOT NULL,
    domain          VARCHAR(32) NOT NULL,
    region_level    VARCHAR(16) NOT NULL,
    region_code     VARCHAR(10) NOT NULL,
    region_name     TEXT,
    period_kind     VARCHAR(24) NOT NULL,
    period_key      VARCHAR(32) NOT NULL,
    asset_type      VARCHAR(32) NOT NULL,
    engine_version  VARCHAR(32) NOT NULL,
    builder_version TEXT,
    as_of           TEXT,
    l1_json         JSONB NOT NULL,
    l2_json         JSONB NOT NULL,
    l3_json         JSONB NOT NULL,
    mart_json       JSONB NOT NULL,
    diffs_json      JSONB NOT NULL,
    verdict         VARCHAR(16) NOT NULL,
    ai_report       TEXT,
    operator_note   TEXT
);

CREATE INDEX IF NOT EXISTS ix_qa_audit_run_created
    ON qa_audit_run (created_at DESC);

CREATE INDEX IF NOT EXISTS ix_qa_audit_run_verdict
    ON qa_audit_run (verdict, created_at DESC);

COMMENT ON TABLE qa_audit_run IS
    '지역 QA 검증 런. 원장/마트 비변경. 판정 PASS/REVIEW/ERROR/BLOCK/SKIP';
