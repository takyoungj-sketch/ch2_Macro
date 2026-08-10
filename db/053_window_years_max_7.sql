-- =============================================================================
-- 053: 롤링 window_years 상한 5 → 7 (3·5·7 UI)
-- =============================================================================
-- 설계: docs/ROLLING_WINDOW_7Y_PLAN.md
-- land_stats / collective_stats 등 DB마다 테이블 subset — 존재하는 것만 ALTER.

DO $$
BEGIN
    IF to_regclass('public.land_basic_stats_v2') IS NOT NULL THEN
        ALTER TABLE land_basic_stats_v2
            DROP CONSTRAINT IF EXISTS land_basic_stats_v2_window_years_check;
        ALTER TABLE land_basic_stats_v2
            ADD CONSTRAINT land_basic_stats_v2_window_years_check
                CHECK (window_years >= 1 AND window_years <= 7);
    END IF;

    IF to_regclass('public.land_upper_stats_v2') IS NOT NULL THEN
        ALTER TABLE land_upper_stats_v2
            DROP CONSTRAINT IF EXISTS land_upper_stats_v2_window_years_check;
        ALTER TABLE land_upper_stats_v2
            ADD CONSTRAINT land_upper_stats_v2_window_years_check
                CHECK (window_years >= 1 AND window_years <= 7);
    END IF;

    IF to_regclass('public.collective_building_stats') IS NOT NULL THEN
        ALTER TABLE collective_building_stats
            DROP CONSTRAINT IF EXISTS collective_building_stats_window_years_check;
        ALTER TABLE collective_building_stats
            ADD CONSTRAINT collective_building_stats_window_years_check
                CHECK (window_years >= 1 AND window_years <= 7);
    END IF;

    IF to_regclass('public.collective_building_rolling_stats') IS NOT NULL THEN
        ALTER TABLE collective_building_rolling_stats
            DROP CONSTRAINT IF EXISTS collective_building_rolling_stats_window_years_check;
        ALTER TABLE collective_building_rolling_stats
            ADD CONSTRAINT collective_building_rolling_stats_window_years_check
                CHECK (window_years >= 1 AND window_years <= 7);
        ALTER TABLE collective_building_rolling_stats
            DROP CONSTRAINT IF EXISTS collective_building_rolling_stats_bucket_index_check;
        ALTER TABLE collective_building_rolling_stats
            ADD CONSTRAINT collective_building_rolling_stats_bucket_index_check
                CHECK (bucket_index >= 1 AND bucket_index <= 7);
    END IF;

    IF to_regclass('public.market_stats') IS NOT NULL THEN
        ALTER TABLE market_stats
            DROP CONSTRAINT IF EXISTS market_stats_window_years_check;
        ALTER TABLE market_stats
            ADD CONSTRAINT market_stats_window_years_check
                CHECK (window_years >= 1 AND window_years <= 7);
    END IF;

    IF to_regclass('public.regional_profile') IS NOT NULL THEN
        ALTER TABLE regional_profile
            DROP CONSTRAINT IF EXISTS regional_profile_window_years_check;
        ALTER TABLE regional_profile
            ADD CONSTRAINT regional_profile_window_years_check
                CHECK (window_years >= 1 AND window_years <= 7);
    END IF;

    IF to_regclass('public.collective_commercial_cluster_stats') IS NOT NULL THEN
        ALTER TABLE collective_commercial_cluster_stats
            DROP CONSTRAINT IF EXISTS collective_commercial_cluster_stats_window_years_check;
        ALTER TABLE collective_commercial_cluster_stats
            ADD CONSTRAINT collective_commercial_cluster_stats_window_years_check
                CHECK (window_years >= 1 AND window_years <= 7);
    END IF;

    IF to_regclass('public.collective_commercial_cluster_rolling_stats') IS NOT NULL THEN
        ALTER TABLE collective_commercial_cluster_rolling_stats
            DROP CONSTRAINT IF EXISTS collective_commercial_cluster_rolling_stats_window_years_check;
        ALTER TABLE collective_commercial_cluster_rolling_stats
            ADD CONSTRAINT collective_commercial_cluster_rolling_stats_window_years_check
                CHECK (window_years >= 1 AND window_years <= 7);
        ALTER TABLE collective_commercial_cluster_rolling_stats
            DROP CONSTRAINT IF EXISTS collective_commercial_cluster_rolling_stats_bucket_index_check;
        ALTER TABLE collective_commercial_cluster_rolling_stats
            ADD CONSTRAINT collective_commercial_cluster_rolling_stats_bucket_index_check
                CHECK (bucket_index >= 1 AND bucket_index <= 7);
    END IF;
END $$;
