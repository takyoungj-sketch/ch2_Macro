-- 행정구역 위상 인접 그래프 (Map Hub Selection SSOT)
-- Display(viewport)와 분리. docs/MAP_NEIGHBOR_TOPOLOGY_DESIGN.md

CREATE TABLE IF NOT EXISTS region_neighbors (
    level TEXT NOT NULL,
    code TEXT NOT NULL,
    neighbor_code TEXT NOT NULL,
    PRIMARY KEY (level, code, neighbor_code),
    CONSTRAINT region_neighbors_level_chk
        CHECK (level IN ('eupmyeondong', 'beopjungri')),
    CONSTRAINT region_neighbors_neq_chk
        CHECK (code <> neighbor_code)
);

CREATE INDEX IF NOT EXISTS idx_region_neighbors_code
    ON region_neighbors (level, code);

CREATE INDEX IF NOT EXISTS idx_region_neighbors_neighbor
    ON region_neighbors (level, neighbor_code);

COMMENT ON TABLE region_neighbors IS
    '동일 레벨 행정구역 위상 인접. 복수 선택 확장 SSOT.';
