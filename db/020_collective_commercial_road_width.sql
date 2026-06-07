-- 집합상가 도로폭 구간 (GUKTO 원본 col 7: 12m미만, 25m미만 등)

ALTER TABLE collective_commercial_transactions
    ADD COLUMN IF NOT EXISTS road_width_label VARCHAR(32);

COMMENT ON COLUMN collective_commercial_transactions.road_width_label IS '도로폭 구간 (집합상가 원본)';
