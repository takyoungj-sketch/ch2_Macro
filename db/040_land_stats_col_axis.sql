-- =============================================================================
-- 040: V2 mart 열 축 구분 — col_axis = category | group (D-026 지목군 병행)
-- =============================================================================
-- 선행: db/007, db/010
-- land_category 컬럼:
--   col_axis='category' → 지목 (전·대·… / ALL)
--   col_axis='group'    → jimok_group_code (agri|forest|… / ALL)
-- =============================================================================

-- land_basic_stats_v2
ALTER TABLE land_basic_stats_v2
    ADD COLUMN IF NOT EXISTS col_axis VARCHAR(16) NOT NULL DEFAULT 'category';

ALTER TABLE land_basic_stats_v2
    DROP CONSTRAINT IF EXISTS land_basic_stats_v2_grain_uq;

ALTER TABLE land_basic_stats_v2
    ADD CONSTRAINT land_basic_stats_v2_grain_uq UNIQUE (
        as_of_month,
        window_years,
        beopjungri_code,
        zone_type,
        land_category,
        col_axis
    );

ALTER TABLE land_basic_stats_v2
    DROP CONSTRAINT IF EXISTS land_basic_stats_v2_col_axis_chk;

ALTER TABLE land_basic_stats_v2
    ADD CONSTRAINT land_basic_stats_v2_col_axis_chk
        CHECK (col_axis IN ('category', 'group'));

COMMENT ON COLUMN land_basic_stats_v2.col_axis IS
    'category=용도×지목(기본), group=용도×지목군(옵션). land_category 는 축에 맞는 키';

CREATE INDEX IF NOT EXISTS ix_lbs_v2_beopjungri_asof_window_axis
    ON land_basic_stats_v2 (beopjungri_code, as_of_month DESC, window_years, col_axis);

-- land_upper_stats_v2
ALTER TABLE land_upper_stats_v2
    ADD COLUMN IF NOT EXISTS col_axis VARCHAR(16) NOT NULL DEFAULT 'category';

ALTER TABLE land_upper_stats_v2
    DROP CONSTRAINT IF EXISTS land_upper_stats_v2_grain_uq;

ALTER TABLE land_upper_stats_v2
    ADD CONSTRAINT land_upper_stats_v2_grain_uq UNIQUE (
        region_level,
        region_code,
        as_of_month,
        window_years,
        zone_type,
        land_category,
        col_axis
    );

ALTER TABLE land_upper_stats_v2
    DROP CONSTRAINT IF EXISTS land_upper_stats_v2_col_axis_chk;

ALTER TABLE land_upper_stats_v2
    ADD CONSTRAINT land_upper_stats_v2_col_axis_chk
        CHECK (col_axis IN ('category', 'group'));

COMMENT ON COLUMN land_upper_stats_v2.col_axis IS
    'category=용도×지목(기본), group=용도×지목군(옵션)';

CREATE INDEX IF NOT EXISTS ix_lus_v2_level_code_asof_window_axis
    ON land_upper_stats_v2 (region_level, region_code, as_of_month DESC, window_years, col_axis);

-- land_category 에 group_code(최대 7자 special) 저장 — 여유 확보
ALTER TABLE land_basic_stats_v2
    ALTER COLUMN land_category TYPE VARCHAR(20);

ALTER TABLE land_upper_stats_v2
    ALTER COLUMN land_category TYPE VARCHAR(20);
