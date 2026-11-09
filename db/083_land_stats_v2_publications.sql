-- 월간 토지 집계와 검증이 끝난 뒤에만 기준월을 기록한다.
CREATE TABLE IF NOT EXISTS land_stats_v2_publications (
    as_of_month date PRIMARY KEY CHECK (EXTRACT(DAY FROM as_of_month) = 1),
    published_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
