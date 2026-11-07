-- 077: account AI allowances. Target: ch2_platform. Additive; no billing changes.
BEGIN;

CREATE TABLE IF NOT EXISTS ai_allowance_accounts (
	user_id SERIAL NOT NULL,
	PRIMARY KEY (user_id)
)

;

CREATE TABLE IF NOT EXISTS ai_allowance_adjustments (
	request_id VARCHAR(36) NOT NULL,
	operator VARCHAR(80) NOT NULL,
	reason TEXT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (request_id)
)

;

CREATE TABLE IF NOT EXISTS ai_allowance_requests (
	id VARCHAR(36) NOT NULL,
	user_id INTEGER NOT NULL,
	key VARCHAR(128) NOT NULL,
	fingerprint VARCHAR(64) NOT NULL,
	feature VARCHAR(40) NOT NULL,
	units INTEGER NOT NULL,
	period_start TIMESTAMP WITH TIME ZONE NOT NULL,
	status VARCHAR(24) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	finished_at TIMESTAMP WITH TIME ZONE,
	error VARCHAR(64),
	PRIMARY KEY (id),
	CONSTRAINT ai_request_idempotency UNIQUE (user_id, key)
)

;
CREATE INDEX IF NOT EXISTS ix_ai_allowance_requests_user_id ON ai_allowance_requests (user_id);

CREATE TABLE IF NOT EXISTS ai_allowance_results (
	request_id VARCHAR(36) NOT NULL,
	payload TEXT NOT NULL,
	PRIMARY KEY (request_id)
)

;

CREATE TABLE IF NOT EXISTS ai_allowances (
	user_id INTEGER NOT NULL,
	feature VARCHAR(40) NOT NULL,
	period_start TIMESTAMP WITH TIME ZONE NOT NULL,
	period_end TIMESTAMP WITH TIME ZONE NOT NULL,
	limit_units INTEGER NOT NULL,
	used INTEGER NOT NULL,
	reserved INTEGER NOT NULL,
	policy VARCHAR(64) NOT NULL,
	PRIMARY KEY (user_id, feature, period_start),
	CONSTRAINT ai_allowance_nonnegative CHECK (used >= 0 AND reserved >= 0)
)

;

CREATE TABLE IF NOT EXISTS ai_provider_calls (
	id VARCHAR(36) NOT NULL,
	request_id VARCHAR(36) NOT NULL,
	stage VARCHAR(32) NOT NULL,
	model VARCHAR(128) NOT NULL,
	input_tokens INTEGER NOT NULL,
	output_tokens INTEGER NOT NULL,
	cached_tokens INTEGER NOT NULL,
	usd FLOAT,
	status VARCHAR(24) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id)
)

;
CREATE INDEX IF NOT EXISTS ix_ai_provider_calls_request_id ON ai_provider_calls (request_id);
COMMIT;
