-- 비주거 집합 도로명 cluster 대표점·지도 라벨용 지오코딩 결과 캐시
CREATE TABLE IF NOT EXISTS collective_commercial_map_geocodes (
    cluster_key       TEXT PRIMARY KEY,
    label             TEXT NOT NULL,
    normalized_query  TEXT NOT NULL,
    longitude         DOUBLE PRECISION,
    latitude          DOUBLE PRECISION,
    matched_name      TEXT,
    category          TEXT,
    status            TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('ok', 'not_found', 'error', 'pending')),
    error             TEXT,
    geocoded_at       TIMESTAMP,
    updated_at        TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_collective_commercial_map_geocodes_status
    ON collective_commercial_map_geocodes (status);

