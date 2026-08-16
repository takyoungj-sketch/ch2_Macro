-- 지역프로필 주거 전월세 연간 집계용 (eup/시군구 × 달력 연도)
-- btrim 조건은 플래너가 등호 질의와 매칭하지 못해 Seq Scan 으로 떨어진다.
DROP INDEX IF EXISTS ix_rent_tx_eup_year;
DROP INDEX IF EXISTS ix_rent_tx_sg_year;

CREATE INDEX IF NOT EXISTS ix_rent_tx_eup_year
    ON rent_transactions (eupmyeondong_code, contract_year)
    WHERE is_valid;

CREATE INDEX IF NOT EXISTS ix_rent_tx_sg_year
    ON rent_transactions (sigungu_code, contract_year)
    WHERE is_valid;
