-- K-apt 단지_필지고유번호 → builder_master.pnu
-- 같은 PNU를 여러 단지가 공유할 수 있다(단지 분할). 첫째 행 대표값으로 쓰지 않는다.

ALTER TABLE builder_master
    ADD COLUMN IF NOT EXISTS pnu CHAR(19);

CREATE INDEX IF NOT EXISTS ix_builder_master_pnu
    ON builder_master (pnu)
    WHERE pnu IS NOT NULL;

COMMENT ON COLUMN builder_master.pnu IS
    'K-apt 단지 필지고유번호 19자리. 단지 1행 = PNU 1개. 여러 단지가 같은 PNU를 가질 수 있음';
