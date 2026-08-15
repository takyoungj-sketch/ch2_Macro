-- 주거 전월세 원장 — rent_stats 전용
-- 전환율·환산금액 없음. 신고 보증금·월세 원문 + 면적당 단가 2열만.

CREATE TABLE IF NOT EXISTS region_codes (
    id              SERIAL PRIMARY KEY,
    sido_code       CHAR(2)      NOT NULL,
    sido_name       VARCHAR(20)  NOT NULL,
    sigungu_code    CHAR(5)      NOT NULL,
    sigungu_name    VARCHAR(30)  NOT NULL,
    eupmyeondong_code CHAR(8)    NOT NULL,
    eupmyeondong_name VARCHAR(30) NOT NULL,
    beopjungri_code CHAR(10)     NOT NULL,
    beopjungri_name VARCHAR(30)  NOT NULL,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    updated_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_rent_region_codes_beopjungri
    ON region_codes (beopjungri_code);

CREATE TABLE IF NOT EXISTS rent_transactions (
    id                      BIGSERIAL PRIMARY KEY,
    transaction_hash        CHAR(64)     NOT NULL,
    asset_type              VARCHAR(20)  NOT NULL,
    molit_lease_kind        VARCHAR(20),
    building_key            CHAR(64),
    display_name            VARCHAR(120),
    building_name           VARCHAR(120),
    housing_subtype         VARCHAR(40),
    addr1                   VARCHAR(30),
    addr2                   VARCHAR(30),
    addr3                   VARCHAR(30),
    addr4                   VARCHAR(30),
    addr5                   VARCHAR(30),
    lot_number              VARCHAR(64),
    lot_bun                 VARCHAR(20),
    lot_ji                  VARCHAR(20),
    road_name               VARCHAR(120),
    road_width_label        VARCHAR(40),
    sido_code               CHAR(2),
    sigungu_code            CHAR(5),
    eupmyeondong_code       CHAR(8),
    beopjungri_code         CHAR(10),
    contract_year           SMALLINT,
    contract_month          SMALLINT,
    contract_date           DATE,
    building_year           SMALLINT,
    building_age            NUMERIC(8, 1),
    exclusive_area          NUMERIC(14, 4),
    contract_area           NUMERIC(14, 4),
    floor                   NUMERIC(8, 1),
    deposit_manwon          NUMERIC(14, 2),
    monthly_rent_manwon     NUMERIC(14, 2),
    deposit_per_m2          NUMERIC(14, 4),
    monthly_per_m2          NUMERIC(14, 4),
    prev_deposit_manwon     NUMERIC(14, 2),
    prev_monthly_rent_manwon NUMERIC(14, 2),
    lease_term_raw          VARCHAR(40),
    contract_class_raw      VARCHAR(40),
    renewal_right_raw       VARCHAR(40),
    source_path             VARCHAR(260),
    is_valid                BOOLEAN      NOT NULL DEFAULT TRUE,
    needs_review            BOOLEAN      NOT NULL DEFAULT FALSE,
    mapping_notes           TEXT,
    created_at              TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_rent_tx_hash
    ON rent_transactions (transaction_hash);

CREATE INDEX IF NOT EXISTS ix_rent_tx_asset
    ON rent_transactions (asset_type);

CREATE INDEX IF NOT EXISTS ix_rent_tx_building
    ON rent_transactions (building_key)
    WHERE building_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_rent_tx_addr
    ON rent_transactions (addr1, addr2, addr3);

CREATE INDEX IF NOT EXISTS ix_rent_tx_contract_year
    ON rent_transactions (contract_year);

CREATE INDEX IF NOT EXISTS ix_rent_tx_lease_kind
    ON rent_transactions (molit_lease_kind);

CREATE INDEX IF NOT EXISTS ix_rent_tx_beopjungri
    ON rent_transactions (beopjungri_code)
    WHERE beopjungri_code IS NOT NULL AND btrim(beopjungri_code::text) <> '';

COMMENT ON TABLE rent_transactions IS
    '주거 전월세 원장. deposit/monthly는 신고 만원. 단가는 면적당 2열. 환산 없음.';

CREATE OR REPLACE VIEW rent_transactions_std AS
SELECT
    t.*,
    CASE
        WHEN COALESCE(t.monthly_rent_manwon, 0) = 0 THEN 'jeonse'
        WHEN COALESCE(t.deposit_manwon, 0) = 0 THEN 'monthly'
        ELSE 'mixed'
    END AS contract_structure
FROM rent_transactions t;

COMMENT ON VIEW rent_transactions_std IS
    'contract_structure: jeonse=전세(월세0), monthly=순수월세(보증금0), mixed=보증부월세. 전환율 없음.';
