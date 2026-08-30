-- =============================================================================
-- 070: regional_profile_rank — 같은 grain 전국 순위 + 유형 전국 비중 (D-053)
-- =============================================================================
-- 설계: docs/PROFILE_NATIONAL_RANK_PLAN.md
-- DB: collective_stats (regional_profile 과 동일)
-- 빌더: pipeline/build_regional_profile_rank.py (build_regional_profile.py 끝에서 호출)

CREATE TABLE IF NOT EXISTS regional_profile_rank (
    profile_version     VARCHAR(16)     NOT NULL,
    as_of_month         DATE            NOT NULL,
    window_years        SMALLINT        NOT NULL,
    region_level        VARCHAR(12)     NOT NULL,
    region_code         VARCHAR(10)     NOT NULL,
    name_short          TEXT            NOT NULL,
    population          INTEGER,
    amount_3y           DOUBLE PRECISION NOT NULL DEFAULT 0,
    count_3y            INTEGER         NOT NULL DEFAULT 0,
    rank_amount         INTEGER         NOT NULL,
    rank_count          INTEGER         NOT NULL,
    rank_per_capita     INTEGER,
    computed_at         TIMESTAMP       NOT NULL DEFAULT NOW(),
    PRIMARY KEY (profile_version, as_of_month, window_years, region_level, region_code)
);

COMMENT ON TABLE regional_profile_rank IS
    '지역프로필 같은 grain 전국 순위 (3년 총액·건수·액/인구). 라이브 JSONB 정렬 금지.';

CREATE INDEX IF NOT EXISTS ix_regional_profile_rank_lookup
    ON regional_profile_rank (profile_version, as_of_month, window_years, region_level, rank_amount);

CREATE TABLE IF NOT EXISTS regional_profile_national_mix (
    profile_version     VARCHAR(16)     NOT NULL,
    as_of_month         DATE            NOT NULL,
    window_years        SMALLINT        NOT NULL,
    region_level        VARCHAR(12)     NOT NULL,
    universe_n          INTEGER         NOT NULL,
    n_per_capita        INTEGER         NOT NULL,
    share_count         JSONB           NOT NULL DEFAULT '{}'::jsonb,
    share_amount        JSONB           NOT NULL DEFAULT '{}'::jsonb,
    computed_at         TIMESTAMP       NOT NULL DEFAULT NOW(),
    PRIMARY KEY (profile_version, as_of_month, window_years, region_level)
);

COMMENT ON TABLE regional_profile_national_mix IS
    '같은 grain 전국 8대유형 건수·금액 가중 비중 (특화도 배지). 지역 비중 산술평균 아님. type_corr = 유형 동조(D-055).';

ALTER TABLE regional_profile_national_mix
    ADD COLUMN IF NOT EXISTS type_corr JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN regional_profile_national_mix.type_corr IS
    '8대유형 지역 단면 비중 Pearson. {amount,count}:{types,n,matrix}. 합=1 조성자료.';
