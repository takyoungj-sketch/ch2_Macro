-- D-049: 복합 상업·공장 지분거래 플래그 (단독 CSV에는 칸 없음 → 항상 FALSE)
-- 적용: psql "$BUILT_DATABASE_URL" -f db/067_built_partial_ownership.sql

ALTER TABLE built_transactions
    ADD COLUMN IF NOT EXISTS is_partial_ownership BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE built_transactions
    ADD COLUMN IF NOT EXISTS partial_ownership_label VARCHAR(32);

COMMENT ON COLUMN built_transactions.is_partial_ownership IS
    'MOLIT 지분구분에 지분 포함. 상업·공장만 식별. 목록은 표시, 중위·회귀 기본 제외 (D-049)';
COMMENT ON COLUMN built_transactions.partial_ownership_label IS
    'MOLIT 지분구분 원문 (지분). 단독은 NULL';

CREATE INDEX IF NOT EXISTS ix_built_tx_partial
    ON built_transactions (is_partial_ownership)
    WHERE is_partial_ownership;

-- 마트 한 행: 건수는 지분 포함, 중위·평균은 지분 제외. partial_tx_count 로 구분한다.
ALTER TABLE built_scope_stats
    ADD COLUMN IF NOT EXISTS partial_tx_count BIGINT NOT NULL DEFAULT 0;

COMMENT ON COLUMN built_scope_stats.tx_count IS '지분 포함 거래 건수 (D-049)';
COMMENT ON COLUMN built_scope_stats.partial_tx_count IS 'tx_count 중 지분 건수';
COMMENT ON COLUMN built_scope_stats.median_price IS '지분 제외 중위 금액 (D-049)';
COMMENT ON COLUMN built_scope_stats.mean_price IS '지분 제외 평균 금액 (D-049)';
