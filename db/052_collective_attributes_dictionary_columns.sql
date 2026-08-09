-- 단지 속성 — 사전 적용 부가 컬럼 (P2)
-- `docs/COLLECTIVE_TWO_STAGE_HEDONIC_DESIGN.md` §3 원자료 보존 원칙:
-- builder_raw(원문)는 건드리지 않고, 판단이 들어간 값만 별도 컬럼으로 붙인다.

ALTER TABLE collective_building_attributes
    ADD COLUMN IF NOT EXISTS builder_is_joint  BOOLEAN,
    ADD COLUMN IF NOT EXISTS builder_is_public BOOLEAN,
    ADD COLUMN IF NOT EXISTS brand_is_public   BOOLEAN,
    ADD COLUMN IF NOT EXISTS brand_confidence  VARCHAR(10),
    ADD COLUMN IF NOT EXISTS attr_quality_flags VARCHAR(120),
    ADD COLUMN IF NOT EXISTS dictionary_version VARCHAR(20);

CREATE INDEX IF NOT EXISTS ix_cba_builder_group
    ON collective_building_attributes (builder_group);

CREATE INDEX IF NOT EXISTS ix_cba_brand
    ON collective_building_attributes (brand);

COMMENT ON COLUMN collective_building_attributes.builder_group IS
    '사명변경·계열통합 판단이 반영된 분석 단위 — 판단 불가 시 NULL';
COMMENT ON COLUMN collective_building_attributes.brand IS
    '단지명에서 추출한 브랜드 — NULL은 「사전 미검출」(무브랜드 포함)이며 「브랜드 없음」 확정이 아니다';
COMMENT ON COLUMN collective_building_attributes.attr_quality_flags IS
    'K-apt 원본 이상값 탐지 코드(쉼표 구분). 값을 지우지 않고 표시만 하며, 회귀에서 해당 변수를 결측 처리하고 그 사유를 UI에 노출한다';
