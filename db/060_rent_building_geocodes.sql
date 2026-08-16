-- 임대 건물 지도 라벨용 지오코딩 결과 캐시 (집합 029와 동일 구조)
CREATE TABLE IF NOT EXISTS rent_building_geocodes (
    building_key       TEXT PRIMARY KEY,
    label              TEXT NOT NULL,
    jibun_address      TEXT,
    normalized_address TEXT NOT NULL,
    longitude          DOUBLE PRECISION,
    latitude           DOUBLE PRECISION,
    matched_name       TEXT,
    category           TEXT,
    status             TEXT NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('ok', 'not_found', 'error', 'pending')),
    error              TEXT,
    geocoded_at        TIMESTAMP,
    updated_at         TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_rent_building_geocodes_status
    ON rent_building_geocodes (status);
