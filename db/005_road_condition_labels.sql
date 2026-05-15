-- 도로조건 축약 표기 변경: 저장값을 UI·문서와 동일한 명칭으로 통일
-- (예: '25이' → '25이상', '25미' → '25미만')
-- 새 파이프라인은 pipeline/constants.py ROAD_CONDITION_COMPACT_MAP 과 동일한 값으로 적재된다.
-- 실행: psql -U postgres -d land_stats -f db/005_road_condition_labels.sql

BEGIN;

UPDATE land_transactions
SET road_condition = CASE road_condition::text
    WHEN '25이' THEN '25이상'
    WHEN '25미' THEN '25미만'
    WHEN '12미' THEN '12미만'
    WHEN '8미' THEN '8미만'
    ELSE road_condition::text
END
WHERE road_condition IN ('25이', '25미', '12미', '8미');

-- 유료 분석 로그 요약(array) 내 구 표기 교체 (선택적 이력 정리)
UPDATE paid_analysis_logs p
SET road_conditions = sub.new_vals
FROM (
    SELECT p_inner.id AS id,
           array_agg(
               CASE elem
                   WHEN '25이' THEN '25이상'
                   WHEN '25미' THEN '25미만'
                   WHEN '12미' THEN '12미만'
                   WHEN '8미' THEN '8미만'
                   ELSE elem
               END
               ORDER BY ord
           ) AS new_vals
    FROM paid_analysis_logs p_inner,
         unnest(coalesce(p_inner.road_conditions, '{}')) WITH ORDINALITY AS v(elem, ord)
    GROUP BY p_inner.id
    HAVING bool_or(elem IN ('25이', '25미', '12미', '8미'))
) sub
WHERE p.id = sub.id;

COMMIT;
