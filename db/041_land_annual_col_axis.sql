-- =============================================================================
-- 041: 장기추세 annual mart 열 축 — col_axis = category | group (D-026)
-- =============================================================================
-- 선행: db/014_land_annual_stats.sql, db/021_land_annual_upper_stats.sql
-- land_category 컬럼:
--   col_axis='category' → 지목 (전·대·… / ALL)
--   col_axis='group'    → jimok_group_code (agri|forest|… / ALL)
-- =============================================================================

-- land_annual_stats
ALTER TABLE land_annual_stats
    ADD COLUMN IF NOT EXISTS col_axis VARCHAR(16) NOT NULL DEFAULT 'category';

ALTER TABLE land_annual_stats
    DROP CONSTRAINT IF EXISTS land_annual_stats_grain_uq;

ALTER TABLE land_annual_stats
    ADD CONSTRAINT land_annual_stats_grain_uq UNIQUE (
        calendar_year,
        beopjungri_code,
        zone_type,
        land_category,
        col_axis
    );

ALTER TABLE land_annual_stats
    DROP CONSTRAINT IF EXISTS land_annual_stats_col_axis_chk;

ALTER TABLE land_annual_stats
    ADD CONSTRAINT land_annual_stats_col_axis_chk
        CHECK (col_axis IN ('category', 'group'));

COMMENT ON COLUMN land_annual_stats.col_axis IS
    'category=용도×지목(기본), group=용도×지목군(옵션). land_category 는 축에 맞는 키';

ALTER TABLE land_annual_stats
    ALTER COLUMN land_category TYPE VARCHAR(20);

CREATE INDEX IF NOT EXISTS ix_las_beopjungri_year_axis
    ON land_annual_stats (beopjungri_code, calendar_year DESC, col_axis);

CREATE INDEX IF NOT EXISTS ix_las_year_beopjungri_zone_cat_axis
    ON land_annual_stats (
        calendar_year, beopjungri_code, zone_type, land_category, col_axis
    );

-- land_annual_upper_stats
ALTER TABLE land_annual_upper_stats
    ADD COLUMN IF NOT EXISTS col_axis VARCHAR(16) NOT NULL DEFAULT 'category';

ALTER TABLE land_annual_upper_stats
    DROP CONSTRAINT IF EXISTS land_annual_upper_stats_grain_uq;

ALTER TABLE land_annual_upper_stats
    ADD CONSTRAINT land_annual_upper_stats_grain_uq UNIQUE (
        calendar_year,
        region_level,
        region_code,
        zone_type,
        land_category,
        col_axis
    );

ALTER TABLE land_annual_upper_stats
    DROP CONSTRAINT IF EXISTS land_annual_upper_stats_col_axis_chk;

ALTER TABLE land_annual_upper_stats
    ADD CONSTRAINT land_annual_upper_stats_col_axis_chk
        CHECK (col_axis IN ('category', 'group'));

COMMENT ON COLUMN land_annual_upper_stats.col_axis IS
    'category=용도×지목(기본), group=용도×지목군(옵션)';

ALTER TABLE land_annual_upper_stats
    ALTER COLUMN land_category TYPE VARCHAR(20);

CREATE INDEX IF NOT EXISTS ix_laus_level_code_year_axis
    ON land_annual_upper_stats (
        region_level, region_code, calendar_year DESC, col_axis
    );

CREATE INDEX IF NOT EXISTS ix_laus_year_level_code_zone_cat_axis
    ON land_annual_upper_stats (
        calendar_year, region_level, region_code, zone_type, land_category, col_axis
    );
