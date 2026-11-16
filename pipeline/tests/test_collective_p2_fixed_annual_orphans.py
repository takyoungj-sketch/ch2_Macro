# -*- coding: utf-8 -*-
"""집합 2단계 — 고정 연도(2019~2020) annual 원장 근거 없는 행 정리: 계획·적용·검증·멱등·되돌리기·가드."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PIPE = Path(__file__).resolve().parents[1]
for p in (PIPE, PIPE / "collective"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from collective import migrate_p2_keys as mig  # noqa: E402
from collective import prune_fixed_annual_orphans_p2 as po  # noqa: E402

DB = "ch2c5_p2r_fixture"
K, NEW, S, X, Y = "k" * 64, "n" * 64, "s" * 64, "x" * 64, "y" * 64

SCHEMA = """
CREATE TABLE collective_transactions (id serial PRIMARY KEY, asset_type text, building_key text,
  addr1 text, addr2 text, contract_year int, unit_price float, is_valid bool DEFAULT true);
CREATE TABLE collective_building_annual_stats (id bigserial PRIMARY KEY, building_key char(64) NOT NULL,
  asset_type varchar(20) NOT NULL, contract_year smallint NOT NULL, display_name varchar(120) NOT NULL,
  addr1 varchar(30), addr2 varchar(30), count integer NOT NULL DEFAULT 0, mean numeric(14,2),
  computed_at timestamp NOT NULL DEFAULT now(), batch_id text,
  CONSTRAINT grain_uq UNIQUE (building_key, asset_type, contract_year));
"""


def _seed(c):
    tx = [(K, "인천광역시", "서구", 2019, 1.0, True), (K, "인천광역시", "서구", 2019, 2.0, True),
          (S, "세종특별자치시", None, 2020, 3.0, True),                 # addr2 NULL — 근거 있음
          (Y, "서울특별시", "종로구", 2019, 4.0, False),               # 무효 거래만 → 근거 아님
          (K, "인천광역시", "서구", 2021, 5.0, True)]
    c.execute(text("""INSERT INTO collective_transactions (asset_type, building_key, addr1, addr2, contract_year,
        unit_price, is_valid) VALUES ('apartment', :k, :a1, :a2, :y, :p, :v)"""),
              [{"k": k, "a1": a1, "a2": a2, "y": y, "p": p, "v": v} for k, a1, a2, y, p, v in tx])
    c.execute(text("""INSERT INTO collective_building_annual_stats (building_key, asset_type, contract_year, display_name,
        addr1, addr2, count, batch_id) VALUES
        (:k, 'apartment', 2019, 'a', '인천광역시', '서구', 2, 'OLD'),       -- 근거 있음 → 그대로
        (:n, 'apartment', 2019, 'a', '인천광역시', '서해구', 2, 'OLD'),     -- 새 구 옛 계산 행 → 삭제(예상 지역)
        (:n, 'apartment', 2020, 'a', '인천광역시', '서해구', 1, 'OLD'),     -- 삭제
        (:s, 'apartment', 2020, 'a', '세종특별자치시', NULL, 1, 'OLD'),     -- 세종 NULL addr2 → 그대로
        (:y, 'apartment', 2019, 'a', '서울특별시', '종로구', 1, 'OLD'),     -- 무효만 → 삭제(예상 밖 지역)
        (:x, 'apartment', 2018, 'a', '서울특별시', '종로구', 7, 'LT'),      -- 2018 은 대상 아님
        (:x, 'apartment', 2021, 'a', '서울특별시', '종로구', 7, 'NOW')      -- 2021~ 대상 아님"""),
              {"k": K, "n": NEW, "s": S, "y": Y, "x": X})


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


def _keys(c):
    return sorted((r[0].strip(), int(r[1])) for r in c.execute(text(
        "SELECT building_key, contract_year FROM collective_building_annual_stats")))


def test_plan_apply_verify_idempotent_rollback(fx):
    e = fx["eng"]
    before = None
    with e.connect() as c:
        before = _keys(c)
        s = po.summary(po.breakdown(c))
        assert (s["rows"], s["tx"]) == (3, 4)
        assert s["by_region"] == {"서울특별시 종로구": {"rows": 1, "tx": 1}, "인천광역시 서해구": {"rows": 2, "tx": 3}}
        assert s["unexpected_regions"] == ["서울특별시 종로구"]
        assert not all(ok for *_x, ok in po.verify(c))
    out = po.apply(e, DB)
    assert (out["deleted_rows"], out["saved_rows"]) == (3, 3)
    with e.connect() as c:
        left = _keys(c)
        assert left == sorted([(K, 2019), (S, 2020), (X, 2018), (X, 2021)])
        assert all(ok for *_x, ok in po.verify(c))
    assert po.apply(e, DB)["deleted_rows"] == 0                     # 다시 돌려도 그대로
    with e.connect() as c:
        assert c.execute(text(f"SELECT count(*) FROM {po.KEEP}")).scalar() == 3
    assert po.rollback(e, DB) == {"restored": 3}
    with e.connect() as c:
        assert _keys(c) == before
        assert c.execute(text("SELECT to_regclass(:t)"), {"t": po.KEEP}).scalar() is None


def test_write_guard(fx):
    for name in ("collective_stats", "collective_stats_p2"):
        with pytest.raises(mig.GuardError):
            po.main(["--collective-db", name, "--apply", "--base-url", fx["base"]])
    with pytest.raises(mig.GuardError):
        po.apply(fx["eng"], "other_p2r")
