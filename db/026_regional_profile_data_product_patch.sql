-- =============================================================================
-- 026: regional_profile — Data Product 컬럼·grain 패치 (기존 Phase D 골격 → D-017)
-- =============================================================================
-- 선행: 025_regional_profile.sql (신규 DB) 또는 레거시 regional_profile 테이블

ALTER TABLE regional_profile
    ADD COLUMN IF NOT EXISTS profile_version VARCHAR(16) NOT NULL DEFAULT 'v1.0';

ALTER TABLE regional_profile
    ADD COLUMN IF NOT EXISTS window_years SMALLINT NOT NULL DEFAULT 5;

ALTER TABLE regional_profile
    ADD COLUMN IF NOT EXISTS feature_count INTEGER;

ALTER TABLE regional_profile
    ADD COLUMN IF NOT EXISTS builder_version TEXT;

ALTER TABLE regional_profile
    ADD COLUMN IF NOT EXISTS validation_status VARCHAR(12) NOT NULL DEFAULT 'PENDING';

-- 레거시 grain 제약 제거 (있을 때만)
ALTER TABLE regional_profile DROP CONSTRAINT IF EXISTS regional_profile_grain_uq;
ALTER TABLE regional_profile DROP CONSTRAINT IF EXISTS regional_profile_region_level_region_code_as_of_month_key;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'regional_profile_grain_uq'
    ) THEN
        ALTER TABLE regional_profile
            ADD CONSTRAINT regional_profile_grain_uq UNIQUE (
                profile_version, region_level, region_code, as_of_month, window_years
            );
    END IF;
END $$;

ALTER TABLE regional_profile DROP CONSTRAINT IF EXISTS regional_profile_validation_status_chk;
ALTER TABLE regional_profile
    ADD CONSTRAINT regional_profile_validation_status_chk
    CHECK (validation_status IN ('PENDING', 'PASS', 'FAIL'));

CREATE INDEX IF NOT EXISTS ix_regional_profile_lookup
    ON regional_profile (profile_version, region_level, region_code, as_of_month DESC, window_years);

CREATE INDEX IF NOT EXISTS ix_regional_profile_features_gin
    ON regional_profile USING gin (features);
