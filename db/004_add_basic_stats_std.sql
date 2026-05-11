-- land_basic_stats 에 참고 엑셀 분석표의 표준편차 항목을 추가합니다.
ALTER TABLE land_basic_stats
    ADD COLUMN IF NOT EXISTS std NUMERIC(14,2);
