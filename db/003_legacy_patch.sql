-- 기존 DB에 001_init.sql 초기 버전만 적용된 경우 보완용 (멱등 실행 가능)

ALTER TABLE land_transactions
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW();

CREATE TABLE IF NOT EXISTS population_stats (
    id                  BIGSERIAL PRIMARY KEY,
    stats_year          SMALLINT     NOT NULL,
    stats_month         SMALLINT,
    admin_code          VARCHAR(10)  NOT NULL,
    admin_level         VARCHAR(20)  NOT NULL,
    total_population    INTEGER,
    household_count     INTEGER,
    pop_change_rate     NUMERIC(8, 4),
    density_per_km2     NUMERIC(14, 4),
    source              VARCHAR(80),
    loaded_at           TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_pop_stats_admin
    ON population_stats (admin_code, stats_year);

COMMENT ON TABLE population_stats IS '추후 행정구역 인구 레이어 (행안부·KOSIS·SGIS 등 연동)';
