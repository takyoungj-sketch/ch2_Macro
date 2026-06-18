-- collective_building_stats mart — 리(addr5) 컬럼 추가 (지번 주소 분리 표시용)

ALTER TABLE collective_building_stats
    ADD COLUMN IF NOT EXISTS addr5 VARCHAR(30);

COMMENT ON COLUMN collective_building_stats.addr5 IS '리(법정리) — 지번 주소 표시용';
