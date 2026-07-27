-- 047: 생활권(권역) scope SSOT — Twin Candidate Filtering (D-029 §12.4.2)
-- pipeline/region_scope.py 가 테이블을 우선 조회, 없으면 코드 fallback.

CREATE TABLE IF NOT EXISTS region_scope_master (
    sido_code       CHAR(2)         NOT NULL,
    scope_id        VARCHAR(32)     NOT NULL,
    scope_label     VARCHAR(32)     NOT NULL,
    scheme_version  VARCHAR(32)     NOT NULL DEFAULT '7region-v1',
    PRIMARY KEY (sido_code, scheme_version)
);

CREATE INDEX IF NOT EXISTS ix_region_scope_master_scope
    ON region_scope_master (scheme_version, scope_id);

COMMENT ON TABLE region_scope_master IS
    'Twin Candidate region_scope — 시도→생활권 매핑 (7region-v1)';

-- Bootstrap seed (REGION_GROUPS 와 동기)
INSERT INTO region_scope_master (sido_code, scope_id, scope_label, scheme_version) VALUES
    ('11', 'capital',      '수도권', '7region-v1'),
    ('28', 'capital',      '수도권', '7region-v1'),
    ('41', 'capital',      '수도권', '7region-v1'),
    ('30', 'chungcheong',  '충청권', '7region-v1'),
    ('36', 'chungcheong',  '충청권', '7region-v1'),
    ('43', 'chungcheong',  '충청권', '7region-v1'),
    ('44', 'chungcheong',  '충청권', '7region-v1'),
    ('12', 'honam',        '호남권', '7region-v1'),
    ('45', 'honam',        '호남권', '7region-v1'),
    ('52', 'honam',        '호남권', '7region-v1'),
    ('29', 'honam',        '호남권', '7region-v1'),
    ('46', 'honam',        '호남권', '7region-v1'),
    ('27', 'daegyeong',    '대경권', '7region-v1'),
    ('47', 'daegyeong',    '대경권', '7region-v1'),
    ('26', 'dongnam',      '동남권', '7region-v1'),
    ('31', 'dongnam',      '동남권', '7region-v1'),
    ('48', 'dongnam',      '동남권', '7region-v1'),
    ('42', 'gangwon',      '강원권', '7region-v1'),
    ('51', 'gangwon',      '강원권', '7region-v1'),
    ('50', 'jeju',         '제주권', '7region-v1')
ON CONFLICT (sido_code, scheme_version) DO NOTHING;
