# -*- coding: utf-8 -*-
"""2019~2020 annual 분할 옛 키 행 정리 — 옛 행 count = 새 조각 합일 때만 삭제·보존·되돌리기·가드."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PIPE = Path(__file__).resolve().parents[1]
if str(PIPE) not in sys.path:
    sys.path.insert(0, str(PIPE))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from collective import migrate_p2_keys as mig  # noqa: E402
from collective import prune_split_annual_p2 as pr  # noqa: E402

DB = "ch2_annual_p2r"


@pytest.fixture(scope="module")
def eng():
    try:
        base = make_url(mig.server_url_from_env())
        admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {DB}"))
            c.execute(text(f"CREATE DATABASE {DB}"))
    except Exception as ex:  # noqa: BLE001
        pytest.skip(f"로컬 PostgreSQL 임시 DB 생성 불가: {type(ex).__name__}")
    e = mig.engine_for(DB, read_only=False, base_url=base.render_as_string(hide_password=False))
    with e.begin() as c:
        c.execute(text("""CREATE TABLE collective_building_key_map (old_key text, new_key text, asset_type text, reason text)"""))
        c.execute(text("""CREATE TABLE collective_building_annual_stats (id bigserial PRIMARY KEY, building_key text,
            asset_type text, contract_year smallint, addr1 text, count int, batch_id text)"""))
        c.execute(text("""INSERT INTO collective_building_key_map VALUES
            ('O','N1','apartment','split'), ('O','N2','apartment','split'), ('H','HN','apartment','honam')"""))
        c.execute(text("""INSERT INTO collective_building_annual_stats (building_key, asset_type, contract_year, addr1, count, batch_id) VALUES
            ('O','apartment',2019,'충청북도',5,'OLD'), ('N1','apartment',2019,'충청북도',3,'NOW'), ('N2','apartment',2019,'충청북도',2,'NOW'),
            ('O','apartment',2020,'충청북도',4,'OLD'), ('N1','apartment',2020,'충청북도',1,'NOW'),
            ('O','apartment',2021,'충청북도',9,'OLD'),
            ('H','apartment',2019,'광주광역시',7,'OLD'),
            ('X','apartment',2019,'충청북도',1,'OLD')"""))
    yield e
    e.dispose()
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)"))
    admin.dispose()


def _rows(e):
    with e.connect() as c:
        return sorted((r[0], r[1], r[2]) for r in c.execute(text(
            "SELECT building_key, contract_year, count FROM collective_building_annual_stats")))


def test_plan_apply_rollback(eng):
    before = _rows(eng)
    with eng.connect() as c:
        df = pr.plan(c)
    assert sorted(zip(df["contract_year"], df["old_n"], df["new_n"], df["match"])) == [(2019, 5, 5, True), (2020, 4, 1, False)]
    out = pr.apply(eng, DB)
    assert out["deleted"] == 1 and out["kept"] == 1 and out["mismatch_rows"] == 1 and out["delete_tx"] == 5
    after = _rows(eng)
    assert ("O", 2019, 5) not in after                       # 일치 → 삭제
    assert ("O", 2020, 4) in after                           # 불일치 → 남김
    assert ("O", 2021, 9) in after and ("H", 2019, 7) in after and ("X", 2019, 1) in after   # 다른 연도·호남·분할 아닌 키
    with eng.connect() as c:
        assert c.execute(text(f"SELECT count(*) FROM {pr.KEEP}")).scalar() == 1
    assert pr.apply(eng, DB)["deleted"] == 0                 # 다시 돌려도 더 지우지 않음
    assert pr.rollback(eng, DB) == 1
    assert _rows(eng) == before


def test_refuses_non_rehearsal_db():
    base = make_url(mig.server_url_from_env())
    e = mig.engine_for("postgres", read_only=False, base_url=base.render_as_string(hide_password=False))
    try:
        with pytest.raises(mig.GuardError):
            pr.apply(e, "postgres")
    finally:
        e.dispose()
