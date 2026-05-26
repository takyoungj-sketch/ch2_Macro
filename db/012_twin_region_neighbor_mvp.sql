-- 012: 쌍둥이 지역(Twin Region) MVP — 충북·충남 시군구 후보 결과 저장
-- 파이프라인: pipeline/build_twin_regions_mvp.py 실행 후 채워짐

CREATE TABLE IF NOT EXISTS twin_region_neighbor_mvp (
    batch_key           VARCHAR(64)     NOT NULL,
    computed_at         TIMESTAMP       NOT NULL DEFAULT NOW(),
    algorithm_version   SMALLINT        NOT NULL DEFAULT 1,

    sido_scope_codes    VARCHAR(20)     NOT NULL,

    anchor_sigungu_code CHAR(5)         NOT NULL,
    anchor_sigungu_name VARCHAR(30)       NOT NULL,
    anchor_sido_code    CHAR(2)          NOT NULL,
    anchor_sido_name    VARCHAR(30)       NOT NULL,

    rank                SMALLINT         NOT NULL,
    twin_sigungu_code   CHAR(5)          NOT NULL,
    twin_sigungu_name   VARCHAR(30)      NOT NULL,
    twin_sido_code      CHAR(2)          NOT NULL,
    twin_sido_name      VARCHAR(30)      NOT NULL,

    similarity_score    NUMERIC(14, 10)  NOT NULL,
    detail_scores       JSONB            NOT NULL DEFAULT '{}'::jsonb,

    PRIMARY KEY (batch_key, anchor_sigungu_code, rank),

    CONSTRAINT twin_region_neighbor_mvp_chk_rank_pos CHECK (rank >= 1 AND rank <= 20)
);

CREATE INDEX IF NOT EXISTS ix_twin_neighbor_mvp_anchor
    ON twin_region_neighbor_mvp (anchor_sigungu_code, batch_key);

CREATE INDEX IF NOT EXISTS ix_twin_neighbor_mvp_batch
    ON twin_region_neighbor_mvp (computed_at DESC);

COMMENT ON TABLE twin_region_neighbor_mvp IS
    'MVP Twin Region 후보 상위 순위 저장 (충북·충남 시군구 등 정책 스코프). batch_key 재실행별 구분.';
COMMENT ON COLUMN twin_region_neighbor_mvp.sido_scope_codes IS
    '예: 43,44';

