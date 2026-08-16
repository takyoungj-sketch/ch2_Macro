-- 집합 매매 × 주거 임대 정확 키 매핑. rent_stats 전용.
-- 원장 UPDATE 없음. 빌더가 덮어쓴다. 보조(name_dong) 층은 넣지 않음.
-- 설계: docs/RENT_COLLECTIVE_SALE_JOIN_PLAN.md

CREATE TABLE IF NOT EXISTS rent_sale_building_map (
    sale_building_key   CHAR(64)     NOT NULL,
    rent_building_key   CHAR(64)     NOT NULL,
    asset_type          VARCHAR(20)  NOT NULL,
    tier                VARCHAR(16)  NOT NULL DEFAULT 'exact',
    built_on            DATE         NOT NULL DEFAULT CURRENT_DATE,
    PRIMARY KEY (sale_building_key, asset_type)
);

CREATE INDEX IF NOT EXISTS ix_rent_sale_map_rent
    ON rent_sale_building_map (rent_building_key, asset_type);

COMMENT ON TABLE rent_sale_building_map IS
    '집합 매매 building_key → 임대 building_key. exact만. 분석층 조인용.';
