-- 048: CH2 통합 플랫폼 — 회원·게시판·구독·entitlement (platform-auth-phase1 + billing)
-- 대상 DB: ch2_platform (Macro 통계 DB와 분리)

CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    email           VARCHAR(255) NOT NULL,
    provider        VARCHAR(32)  NOT NULL DEFAULT 'google',
    provider_sub    VARCHAR(255) NOT NULL,
    nickname        VARCHAR(80)  NOT NULL,
    role            VARCHAR(32)  NOT NULL DEFAULT 'member',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_sub),
    UNIQUE (nickname),
    CONSTRAINT users_role_chk CHECK (role IN ('member', 'admin'))
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

CREATE TABLE IF NOT EXISTS posts (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id),
    product     VARCHAR(32) NOT NULL,
    category    VARCHAR(32) NOT NULL,
    title       VARCHAR(200) NOT NULL,
    body        TEXT NOT NULL,
    status      VARCHAR(32) NOT NULL DEFAULT 'open',
    is_pinned   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT posts_product_chk CHECK (product IN ('macro', 'fieldnote', 'viewer', 'general')),
    CONSTRAINT posts_category_chk CHECK (category IN ('question', 'bug', 'feature')),
    CONSTRAINT posts_status_chk CHECK (status IN ('open', 'checking', 'answered', 'planned', 'done'))
);

CREATE INDEX IF NOT EXISTS idx_posts_product_category ON posts (product, category, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_user_id ON posts (user_id);

CREATE TABLE IF NOT EXISTS comments (
    id          BIGSERIAL PRIMARY KEY,
    post_id     BIGINT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id     BIGINT NOT NULL REFERENCES users(id),
    body        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments (post_id, created_at);

-- 구독·권한 (FieldNote Play / Macro 웹 PG)
CREATE TABLE IF NOT EXISTS subscriptions (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             BIGINT NOT NULL REFERENCES users(id),
    product             VARCHAR(32) NOT NULL,
    source              VARCHAR(32) NOT NULL,
    external_id         VARCHAR(255),
    status              VARCHAR(32) NOT NULL DEFAULT 'active',
    current_period_end  TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT subscriptions_product_chk CHECK (product IN ('fieldnote', 'macro', 'bundle')),
    CONSTRAINT subscriptions_source_chk CHECK (source IN ('play', 'web_toss', 'admin')),
    CONSTRAINT subscriptions_status_chk CHECK (status IN ('active', 'canceled', 'expired', 'pending'))
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions (user_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_subscriptions_external ON subscriptions (source, external_id)
    WHERE external_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS entitlements (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id),
    product     VARCHAR(32) NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at  TIMESTAMPTZ,
    source_sub  BIGINT REFERENCES subscriptions(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT entitlements_product_chk CHECK (product IN ('fieldnote', 'macro'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_entitlements_user_product ON entitlements (user_id, product);

-- FieldNote AI quota (device_id — 로그인 전에도 사용)
CREATE TABLE IF NOT EXISTS device_ai_usage (
    device_id       VARCHAR(128) NOT NULL,
    usage_month     CHAR(7) NOT NULL,
    call_count      INTEGER NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (device_id, usage_month)
);

COMMENT ON TABLE users IS 'CH2 통합 회원 — Google OAuth (Phase1)';
COMMENT ON TABLE subscriptions IS '결제 원장 — Play / 웹 PG';
COMMENT ON TABLE entitlements IS '제품별 접근 권한 — macro | fieldnote';
COMMENT ON TABLE device_ai_usage IS 'FieldNote AI 월간 호출 (device_id)';
