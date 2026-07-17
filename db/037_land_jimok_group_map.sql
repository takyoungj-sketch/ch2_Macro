-- 지목군(7그룹) 매핑 — D-026 / docs/LAND_JIMOK_GROUP_DESIGN.md
-- Master land_transactions.land_category 는 변경하지 않음.

CREATE TABLE IF NOT EXISTS land_jimok_group_map (
    jimok_key       VARCHAR(20) PRIMARY KEY,
    jimok_label     VARCHAR(40) NOT NULL,
    group_code      VARCHAR(16) NOT NULL,
    group_label     VARCHAR(40) NOT NULL,
    sort_order      SMALLINT NOT NULL DEFAULT 0
);

COMMENT ON TABLE land_jimok_group_map IS
    'DB land_category / land_category_resolved → 지목군(agri|forest|dev|infra|water|special|other). 2026-07-17: 양어장·목장용지=agri';

TRUNCATE land_jimok_group_map;

-- 분류 SSOT: docs/LAND_JIMOK_GROUP_DESIGN.md (2026-07-17: 양어장·목장용지 → agri)
INSERT INTO land_jimok_group_map (jimok_key, jimok_label, group_code, group_label, sort_order) VALUES
    -- ① 농경지
    ('전', '전', 'agri', '농경지', 10),
    ('답', '답', 'agri', '농경지', 11),
    ('과', '과수원', 'agri', '농경지', 12),
    ('과수원', '과수원', 'agri', '농경지', 13),
    ('양', '양어장', 'agri', '농경지', 14),
    ('양어장', '양어장', 'agri', '농경지', 15),
    ('목', '목장용지', 'agri', '농경지', 16),
    ('목장용지', '목장용지', 'agri', '농경지', 17),
    -- ② 산림지
    ('임', '임야', 'forest', '산림지', 20),
    ('임야', '임야', 'forest', '산림지', 21),
    -- ③ 개발지
    ('대', '대', 'dev', '개발지', 30),
    ('장', '공장용지', 'dev', '개발지', 31),
    ('공장용지', '공장용지', 'dev', '개발지', 32),
    ('학', '학교용지', 'dev', '개발지', 33),
    ('학교용지', '학교용지', 'dev', '개발지', 34),
    ('차', '주차장', 'dev', '개발지', 35),
    ('주차장', '주차장', 'dev', '개발지', 36),
    ('주', '주유소용지', 'dev', '개발지', 37),
    ('주유소용지', '주유소용지', 'dev', '개발지', 38),
    ('창', '창고용지', 'dev', '개발지', 39),
    ('창고용지', '창고용지', 'dev', '개발지', 40),
    ('잡', '잡종지', 'dev', '개발지', 43),
    ('잡종지', '잡종지', 'dev', '개발지', 44),
    -- ④ 기반시설
    ('도', '도로', 'infra', '기반시설', 50),
    ('도로', '도로', 'infra', '기반시설', 51),
    ('철', '철도용지', 'infra', '기반시설', 52),
    ('철도용지', '철도용지', 'infra', '기반시설', 53),
    ('제', '제방', 'infra', '기반시설', 54),
    ('제방', '제방', 'infra', '기반시설', 55),
    ('구', '구거', 'infra', '기반시설', 56),
    ('구거', '구거', 'infra', '기반시설', 57),
    ('수', '수도용지', 'infra', '기반시설', 58),
    ('수도용지', '수도용지', 'infra', '기반시설', 59),
    -- ⑤ 수면
    ('천', '하천', 'water', '수면', 60),
    ('하천', '하천', 'water', '수면', 61),
    ('유', '유지', 'water', '수면', 62),
    ('유지', '유지', 'water', '수면', 63),
    -- ⑥ 특수용도
    ('공', '공원', 'special', '특수용도', 70),
    ('공원', '공원', 'special', '특수용도', 71),
    ('체', '체육용지', 'special', '특수용도', 72),
    ('체육용지', '체육용지', 'special', '특수용도', 73),
    ('원', '유원지', 'special', '특수용도', 74),
    ('유원지', '유원지', 'special', '특수용도', 75),
    ('종', '종교용지', 'special', '특수용도', 76),
    ('종교용지', '종교용지', 'special', '특수용도', 77),
    ('사적지', '사적지', 'special', '특수용도', 78),
    ('묘', '묘지', 'special', '특수용도', 79),
    ('묘지', '묘지', 'special', '특수용도', 80),
    ('광천지', '광천지', 'special', '특수용도', 81),
    ('염전', '염전', 'special', '특수용도', 82);

CREATE INDEX IF NOT EXISTS ix_land_jimok_group_map_group
    ON land_jimok_group_map (group_code, sort_order);
