-- FieldNote AI quota: short / long / sheet 분리
ALTER TABLE device_ai_usage
    ADD COLUMN IF NOT EXISTS short_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE device_ai_usage
    ADD COLUMN IF NOT EXISTS long_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE device_ai_usage
    ADD COLUMN IF NOT EXISTS sheet_count INTEGER NOT NULL DEFAULT 0;

-- 기존 call_count만 있던 행: short에 흡수(보수적 — 이미 쓴 분량으로 취급)
UPDATE device_ai_usage
SET short_count = GREATEST(short_count, call_count)
WHERE short_count = 0 AND call_count > 0;

COMMENT ON COLUMN device_ai_usage.short_count IS 'FieldNote AI 단문(vision short) 월간 사용';
COMMENT ON COLUMN device_ai_usage.long_count IS 'FieldNote AI 장문(vision long) 월간 사용';
COMMENT ON COLUMN device_ai_usage.sheet_count IS 'FieldNote 주소표 AI 월간 사용';
