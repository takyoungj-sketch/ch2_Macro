-- =============================================================================
-- 007: V2 사전 집계 테이블 land_basic_stats_v2
-- =============================================================================
-- 설계: docs/V2_STATS_DESIGN.md
-- 대상: PostgreSQL 14+ (프로젝트 db/001_init.sql 과 동일 스택)
--
-- 적용 예:
--   psql "$env:DATABASE_URL" -f db/007_land_basic_stats_v2.sql
--   또는: psql -h ... -U ... -d ... -f db/007_land_basic_stats_v2.sql
--
-- 특징:
--   - v1 land_basic_stats 와 병행 (year_from/year_to 대신 as_of_month·window_years·날짜 구간)
--   - 집계 그레인: (as_of_month, window_years, beopjungri_code, zone_type, land_category)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- UP
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS land_basic_stats_v2 (
    id                  BIGSERIAL PRIMARY KEY,

    -- 기준월: 해당 달의 1일 (예: 2026-04-01 → UI "2026년 4월 말 기준")
    as_of_month         DATE            NOT NULL,

    -- 롤링 창(연 단위 정수 1~5; 실제 일수는 period_start/period_end 로 확정)
    window_years        SMALLINT        NOT NULL
                        CHECK (window_years >= 1 AND window_years <= 5),

    -- contract_date 포함 구간 (V2_STATS_DESIGN.md §4)
    period_start        DATE            NOT NULL,
    period_end          DATE            NOT NULL,

    beopjungri_code     CHAR(10)        NOT NULL,
    zone_type           VARCHAR(20)     NOT NULL DEFAULT 'ALL',
    land_category       VARCHAR(10)     NOT NULL DEFAULT 'ALL',

    count               INTEGER         NOT NULL DEFAULT 0,
    mean                NUMERIC(14, 2),
    std                 NUMERIC(14, 2),
    ci_lower            NUMERIC(14, 2),
    ci_upper            NUMERIC(14, 2),
    p_min               NUMERIC(14, 2),
    p25                 NUMERIC(14, 2),
    median              NUMERIC(14, 2),
    p75                 NUMERIC(14, 2),
    p_max               NUMERIC(14, 2),

    computed_at         TIMESTAMP       NOT NULL DEFAULT NOW(),
    batch_id            TEXT,

    CONSTRAINT land_basic_stats_v2_period_chk
        CHECK (period_start <= period_end),

    CONSTRAINT land_basic_stats_v2_as_of_first_of_month_chk
        CHECK (DATE_TRUNC('month', as_of_month)::DATE = as_of_month),

    CONSTRAINT land_basic_stats_v2_grain_uq UNIQUE (
        as_of_month,
        window_years,
        beopjungri_code,
        zone_type,
        land_category
    )
);

COMMENT ON TABLE land_basic_stats_v2 IS
    'V2: as_of_month·window_years·contract_date 구간별 법정동×용도×지목 단가 통계 사전집계';
COMMENT ON COLUMN land_basic_stats_v2.as_of_month IS
    '기준월(해당 월 1일 저장). UI는 동일 달 말일까지 반영으로 표시';
COMMENT ON COLUMN land_basic_stats_v2.window_years IS
    '1~5. 무료: 3·5, 유료: 1~5 (제품 정책은 API/프론트)';
COMMENT ON COLUMN land_basic_stats_v2.period_start IS
    '포함 시작일 (contract_date >= period_start; contract_date NULL 행은 집계 제외 권장)';
COMMENT ON COLUMN land_basic_stats_v2.period_end IS
    '포함 종료일 (contract_date <= period_end)';
COMMENT ON COLUMN land_basic_stats_v2.batch_id IS
    '월별 배치 실행 ID·버전 문자열(선택)';

CREATE INDEX IF NOT EXISTS ix_lbs_v2_beopjungri_asof_window
    ON land_basic_stats_v2 (beopjungri_code, as_of_month DESC, window_years);

CREATE INDEX IF NOT EXISTS ix_lbs_v2_asof_window_beopjungri
    ON land_basic_stats_v2 (as_of_month, window_years, beopjungri_code);

-- -----------------------------------------------------------------------------
-- DOWN (롤백 시 아래만 실행)
-- -----------------------------------------------------------------------------
-- DROP INDEX IF EXISTS ix_lbs_v2_asof_window_beopjungri;
-- DROP INDEX IF EXISTS ix_lbs_v2_beopjungri_asof_window;
-- DROP TABLE IF EXISTS land_basic_stats_v2;
