-- Twin v8 — 충청권 1차 (토지 60 + 집합 40, Confidence·설명문)
-- pipeline/build_twin_v8.py

CREATE TABLE IF NOT EXISTS twin_neighbor_v8 (
    batch_key              VARCHAR(64)     NOT NULL,
    computed_at            TIMESTAMP       NOT NULL DEFAULT NOW(),
    algorithm_version      SMALLINT        NOT NULL DEFAULT 8,
    scope_label            VARCHAR(32)     NOT NULL DEFAULT '충청권',

    region_level           VARCHAR(12)     NOT NULL,
    anchor_region_code     VARCHAR(10)     NOT NULL,
    anchor_region_name     VARCHAR(60)     NOT NULL,
    anchor_sigungu_code    CHAR(5),
    anchor_sigungu_name    VARCHAR(30),
    anchor_sido_code       CHAR(2)         NOT NULL,
    anchor_sido_name       VARCHAR(30)     NOT NULL,

    rank                   SMALLINT        NOT NULL,
    twin_region_code       VARCHAR(10)     NOT NULL,
    twin_region_name       VARCHAR(60)     NOT NULL,
    twin_sigungu_code      CHAR(5),
    twin_sigungu_name      VARCHAR(30),
    twin_sido_code         CHAR(2)         NOT NULL,
    twin_sido_name         VARCHAR(30)     NOT NULL,

    similarity_score       NUMERIC(6, 2)   NOT NULL,
    confidence_score       NUMERIC(6, 2)   NOT NULL,
    detail_scores          JSONB           NOT NULL DEFAULT '{}'::jsonb,
    explanation_ko         TEXT,

    PRIMARY KEY (batch_key, region_level, anchor_region_code, rank),

    CONSTRAINT twin_neighbor_v8_chk_rank CHECK (rank >= 1 AND rank <= 50),
    CONSTRAINT twin_neighbor_v8_chk_level CHECK (
        region_level IN ('sigungu', 'eupmyeondong', 'beopjungri')
    )
);

CREATE INDEX IF NOT EXISTS ix_twin_neighbor_v8_anchor
    ON twin_neighbor_v8 (region_level, anchor_region_code, batch_key);

CREATE INDEX IF NOT EXISTS ix_twin_neighbor_v8_batch
    ON twin_neighbor_v8 (computed_at DESC);

COMMENT ON TABLE twin_neighbor_v8 IS
    'Twin v8 — 토지 구조·가격 + 아파트 분위 유사도 (Hybrid V2와 algorithm_version 분리)';
