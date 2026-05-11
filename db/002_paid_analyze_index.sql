-- 유료 필터 분석: beopjungri_code + contract_year 조건에 맞춘 부분 인덱스
-- 대용량 DB는 다운타임을 피하려면 CREATE INDEX CONCURRENTLY 로 바꿔 단독 실행하세요.

CREATE INDEX IF NOT EXISTS ix_lt_paid_region_year
  ON land_transactions (beopjungri_code, contract_year)
  WHERE is_valid
    AND NOT is_cancelled
    AND unit_price_per_sqm IS NOT NULL;
