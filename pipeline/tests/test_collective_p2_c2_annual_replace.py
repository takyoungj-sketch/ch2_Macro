# -*- coding: utf-8 -*-
"""집합 2단계 — C-2 분할 키 2019~2020 annual 범위 교체: 계획·적용·검증·멱등·되돌리기·가드."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

PIPE = Path(__file__).resolve().parents[1]
for p in (PIPE, PIPE / "collective"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from collective import building_keys as bk  # noqa: E402
from collective import c2_annual_replace_p2 as car  # noqa: E402
from collective import migrate_p2_keys as mig  # noqa: E402

DB = "ch2c4_p2r_fixture"
K, K1, U = "k" * 64, "m" * 64, "u" * 64

SCHEMA = """
CREATE TABLE collective_transactions (id serial PRIMARY KEY, asset_type text, building_key text, display_name text,
  addr1 text, addr2 text, addr3 text, addr4 text, addr5 text, lot_number text, road_name text, sigungu_code text,
  beopjungri_code text, contract_year int, contract_date date, building_year int, unit_price float, is_valid bool DEFAULT true);
CREATE TABLE collective_building_annual_stats (id bigserial PRIMARY KEY, building_key char(64) NOT NULL,
  asset_type varchar(20) NOT NULL, contract_year smallint NOT NULL, display_name varchar(120) NOT NULL,
  addr1 varchar(30), addr2 varchar(30), addr3 varchar(30), addr4 varchar(30), beopjungri_code char(10),
  count integer NOT NULL DEFAULT 0, mean numeric(14,2), std numeric(14,2), ci_lower numeric(14,2), ci_upper numeric(14,2),
  p25 numeric(14,2), median numeric(14,2), p75 numeric(14,2), computed_at timestamp NOT NULL DEFAULT now(), batch_id text,
  CONSTRAINT grain_uq UNIQUE (building_key, asset_type, contract_year));
CREATE TABLE collective_building_key_map (old_key text, new_key text, asset_type text, reason text, split_part int, n_tx int);
"""


def _seed(c):
    tx = [(K, 2019, 100.0, True), (K, 2019, 200.0, True), (K, 2019, 999.0, False),   # 무효 거래는 빼고 계산
          (K1, 2019, 300.0, True), (K1, 2020, 400.0, True), (K, 2018, 50.0, True), (U, 2019, 70.0, True)]
    c.execute(text("""INSERT INTO collective_transactions (asset_type, building_key, display_name, addr1, addr2, addr3,
        lot_number, beopjungri_code, contract_year, contract_date, unit_price, is_valid)
        VALUES ('apartment', :k, '힐', '서울특별시', '종로구', '청운동', '10', '1111010100', :y, make_date(:y, 3, 1), :p, :v)"""),
              [{"k": k, "y": y, "p": p, "v": v} for k, y, p, v in tx])
    mig._exec_script(c, bk.C2_DDL)
    c.execute(text(f"""INSERT INTO {bk.C2_TABLE} (base_key, asset_type, beopjungri_code, main_lot, building_year, part,
        decision, source) VALUES (:k, 'apartment', '1111010100', '10', 2010, 0, 'split', 't'),
        (:k, 'apartment', '1111010100', '20', 2015, 1, 'split', 't'), (:u, 'apartment', '1168010100', '', NULL, NULL, 'keep', 't')"""),
              {"k": K, "u": U})
    c.execute(text("INSERT INTO collective_building_key_map VALUES (:k, :m, 'apartment', 'c2_split', 1, 2)"), {"k": K, "m": K1})
    c.execute(text("""INSERT INTO collective_building_annual_stats (building_key, asset_type, contract_year, display_name,
        count, mean, median, batch_id) VALUES
        (:k, 'apartment', 2019, '힐', 3, 200, 200, 'OLD'),     -- 합친 옛 값 → 교체
        (:k, 'apartment', 2020, '힐', 1, 400, 400, 'OLD'),     -- 본 조각 거래 없음 → 삭제
        (:k, 'apartment', 2018, '힐', 5, 50, 50, 'LT'),        -- 2010~2018 그대로
        (:k, 'apartment', 2021, '힐', 2, 10, 10, 'NOW'),       -- 2021~ 그대로(빌더 몫)
        (:u, 'apartment', 2019, '래미안', 9, 70, 70, 'OLD')     -- 대상 아님"""), {"k": K, "u": U})


@pytest.fixture(scope="module")
def fx():
    try:
        base = mig.server_url_from_env()
        admin = create_engine(make_url(base).set(database="postgres", drivername="postgresql+psycopg2"),
                              isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {DB}"))
            c.execute(text(f"CREATE DATABASE {DB}"))
    except Exception as ex:  # noqa: BLE001
        pytest.skip(f"로컬 PostgreSQL 임시 DB 생성 불가: {type(ex).__name__}")
    e = mig.engine_for(DB, read_only=False, base_url=base)
    with e.begin() as c:
        mig._exec_script(c, SCHEMA)
        _seed(c)
    yield {"eng": e, "base": base}
    e.dispose()
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)"))
    admin.dispose()


def _rows(e):
    with e.connect() as c:
        return sorted((r[0].strip(), r[1], r[2], float(r[3] or 0), r[4]) for r in c.execute(text(
            "SELECT building_key, contract_year, count, median, batch_id FROM collective_building_annual_stats")))


def test_plan_apply_verify_idempotent_rollback(fx):
    e = fx["eng"]
    before = _rows(e)
    with e.connect() as c:
        s = car.summary(car.plan(c))
        assert (s["target_keys"], s["replace"], s["insert"], s["delete"]) == (2, 1, 2, 1)
        assert not all(r[3] for r in car.verify(c))                      # 적용 전: 합친 값·근거 없는 행이 있어 실패
    out = car.apply(e, DB)
    assert (out["saved_rows"], out["deleted_rows"], out["written_rows"]) == (2, 2, 3)
    after = _rows(e)
    assert (K, 2019, 2, 150.0, car.BATCH) in after                        # 무효 거래 빼고 본 조각만
    assert (K1, 2019, 1, 300.0, car.BATCH) in after and (K1, 2020, 1, 400.0, car.BATCH) in after
    assert not any(r[0] == K and r[1] == 2020 for r in after)            # 유효 거래 0 → 삭제
    assert (K, 2018, 5, 50.0, "LT") in after and (K, 2021, 2, 10.0, "NOW") in after and (U, 2019, 9, 70.0, "OLD") in after
    with e.connect() as c:
        assert all(r[3] for r in car.verify(c))
    assert car.apply(e, DB)["saved_rows"] == 0                           # 멱등: 원래 행을 다시 덮지 않음
    assert sorted((r[0], r[1], r[2], r[3]) for r in _rows(e)) == sorted((r[0], r[1], r[2], r[3]) for r in after)
    assert car.rollback(e, DB) == {"restored": 2, "removed": 3}
    assert _rows(e) == before


def test_write_refused_for_non_rehearsal_names():
    for name in ("collective_stats", "postgres", "collective_stats_p2"):
        with pytest.raises(mig.GuardError):
            car.main(["--collective-db", name, "--apply", "--base-url", "postgresql://u@127.0.0.1/x"])


def test_connected_name_mismatch_refused(fx):
    with pytest.raises(mig.GuardError):
        car.apply(fx["eng"], "other_p2r")
