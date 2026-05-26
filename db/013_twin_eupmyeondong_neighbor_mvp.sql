-- 013: 쌍둥이 지역 MVP — 충북·충남 읍면동 단위 후보 결과
-- 파이프라인: pipeline/build_twin_eupmyeondong_mvp.py

CREATE TABLE IF NOT EXISTS twin_eupmyeondong_neighbor_mvp (
    batch_key                  VARCHAR(64)     NOT NULL,
    computed_at                TIMESTAMP       NOT NULL DEFAULT NOW(),
    algorithm_version          SMALLINT        NOT NULL DEFAULT 2,

    sido_scope_codes           VARCHAR(20)     NOT NULL,

    anchor_eupmyeondong_code   CHAR(8)          NOT NULL,
    anchor_eupmyeondong_name   VARCHAR(30)       NOT NULL,
    anchor_sigungu_code        CHAR(5)          NOT NULL,
    anchor_sigungu_name        VARCHAR(30)       NOT NULL,
    anchor_sido_code           CHAR(2)          NOT NULL,
    anchor_sido_name           VARCHAR(30)       NOT NULL,

    rank                       SMALLINT         NOT NULL,

    twin_eupmyeondong_code     CHAR(8)          NOT NULL,
    twin_eupmyeondong_name     VARCHAR(30)       NOT NULL,
    twin_sigungu_code          CHAR(5)          NOT NULL,
    twin_sigungu_name          VARCHAR(30)       NOT NULL,
    twin_sido_code             CHAR(2)          NOT NULL,
    twin_sido_name             VARCHAR(30)       NOT NULL,

    similarity_score           NUMERIC(14, 10) NOT NULL,
    detail_scores              JSONB            NOT NULL DEFAULT '{}'::jsonb,

    PRIMARY KEY (batch_key, anchor_eupmyeondong_code, rank),

    CONSTRAINT twin_eup_neighbor_mvp_chk_rank_pos CHECK (rank >= 1 AND rank <= 20)
);

CREATE INDEX IF NOT EXISTS ix_twin_eup_neighbor_mvp_anchor
    ON twin_eupmyeondong_neighbor_mvp (anchor_eupmyeondong_code, batch_key);

CREATE INDEX IF NOT EXISTS ix_twin_eup_neighbor_mvp_batch
    ON twin_eupmyeondong_neighbor_mvp (computed_at DESC);

COMMENT ON TABLE twin_eupmyeondong_neighbor_mvp IS
    'Twin Region MVP — 읍면동(법정리 상위 8자리) 단위 후보 순위 (충북·충남)';
COMMENT ON COLUMN twin_eupmyeondong_neighbor_mvp.anchor_eupmyeondong_code IS
    '행정표준 코드 읍면동 8자리 (= beopjungri_code 앞 8자리)';
