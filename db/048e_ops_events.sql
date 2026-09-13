-- 운영 이벤트 (방문·다운로드·접수). IP는 저장하지 않는다.
CREATE TABLE IF NOT EXISTS ops_events (
    id              BIGSERIAL PRIMARY KEY,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    product         VARCHAR(32) NOT NULL,
    event_name      VARCHAR(64) NOT NULL,
    visitor_id      VARCHAR(64) NOT NULL,
    user_id         BIGINT REFERENCES users(id) ON DELETE SET NULL,
    path            TEXT,
    meta            JSONB,
    CONSTRAINT ops_events_product_chk CHECK (
        product IN ('hub', 'macro', 'viewer', 'fieldnote', 'board', 'admin')
    ),
    CONSTRAINT ops_events_name_chk CHECK (
        event_name IN ('page_view', 'download', 'ticket_create', 'login')
    )
);

CREATE INDEX IF NOT EXISTS idx_ops_events_occurred ON ops_events (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_ops_events_name_time ON ops_events (event_name, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_ops_events_visitor ON ops_events (visitor_id, occurred_at DESC);
