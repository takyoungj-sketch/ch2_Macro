-- =============================================================================
-- V2 전국 배치 전 프리플라이트 점검 (PostgreSQL)
-- =============================================================================
-- 사용: psql "$DATABASE_URL" -f db/preflight_v2_national.sql
--
-- 선행: db/007 적용, db/008 적용 권장(아래에서 인덱스 존재 확인)
-- =============================================================================

-- 1) 원장 통계 갱신 (배치 planner 정확도)
ANALYZE land_transactions;

-- 2) V2 배치용 인덱스 존재 여부
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'land_transactions'
  AND indexname = 'ix_land_tx_v2_batch_sido_contract';

-- 3) land_basic_stats_v2 인덱스 (007)
SELECT indexname
FROM pg_indexes
WHERE tablename = 'land_basic_stats_v2'
ORDER BY indexname;

-- 4) 현재 V2 행 수·용량 (스냅샷 전 기록용 — as_of / window 는 운영 값으로 바꿔 재실행)
SELECT COUNT(*) AS land_basic_stats_v2_total_rows
FROM land_basic_stats_v2;

SELECT pg_size_pretty(pg_total_relation_size('land_basic_stats_v2'::regclass)) AS lbs_v2_total;
SELECT pg_size_pretty(pg_relation_size('land_basic_stats_v2'::regclass)) AS lbs_v2_heap_only;

-- 예: 특정 스냅샷·창 (값 변경)
-- SELECT COUNT(*) FROM land_basic_stats_v2
-- WHERE as_of_month = DATE '2025-12-01' AND window_years IN (3, 5);
