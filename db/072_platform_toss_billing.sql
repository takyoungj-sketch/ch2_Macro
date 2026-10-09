-- 072: 토스 자동결제(빌링키) · 해지 예약 · 갱신 스케줄
-- 대상 DB: ch2_platform

ALTER TABLE users ADD COLUMN IF NOT EXISTS toss_customer_key VARCHAR(50);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_toss_customer_key
    ON users (toss_customer_key)
    WHERE toss_customer_key IS NOT NULL;

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS plan_id VARCHAR(64);
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS toss_billing_key VARCHAR(200);
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS next_billing_at TIMESTAMPTZ;

ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS subscriptions_status_chk;
ALTER TABLE subscriptions ADD CONSTRAINT subscriptions_status_chk
    CHECK (status IN ('active', 'canceled', 'expired', 'pending', 'past_due'));

COMMENT ON COLUMN subscriptions.toss_billing_key IS '토스 빌링키 — 서버에만 저장, 재조회 불가';
COMMENT ON COLUMN subscriptions.cancel_at_period_end IS 'true면 current_period_end까지 이용 후 갱신 안 함';
COMMENT ON COLUMN subscriptions.next_billing_at IS '다음 자동결제 시각(UTC)';
