-- 집합 장기 추세 연도 마트에 25%·75% 칸.
-- 2019~ 는 건별 원장, 2010~2018 은 raw/raw long term CSV 재집계로 채운다.
-- 중앙값·건수·평균은 이 파일에서 바꾸지 않는다.

ALTER TABLE collective_building_annual_stats
    ADD COLUMN IF NOT EXISTS p25 NUMERIC(14, 2),
    ADD COLUMN IF NOT EXISTS p75 NUMERIC(14, 2);

ALTER TABLE collective_commercial_cluster_annual_stats
    ADD COLUMN IF NOT EXISTS p25 NUMERIC(14, 2),
    ADD COLUMN IF NOT EXISTS p75 NUMERIC(14, 2);

COMMENT ON COLUMN collective_building_annual_stats.p25 IS
    '같은 연도·단지 표본의 25% 분위 (만원/㎡, 소수 첫째 자리)';
COMMENT ON COLUMN collective_building_annual_stats.p75 IS
    '같은 연도·단지 표본의 75% 분위 (만원/㎡, 소수 첫째 자리)';
COMMENT ON COLUMN collective_commercial_cluster_annual_stats.p25 IS
    '같은 연도·cluster 표본의 25% 분위 (만원/㎡, 소수 첫째 자리)';
COMMENT ON COLUMN collective_commercial_cluster_annual_stats.p75 IS
    '같은 연도·cluster 표본의 75% 분위 (만원/㎡, 소수 첫째 자리)';
