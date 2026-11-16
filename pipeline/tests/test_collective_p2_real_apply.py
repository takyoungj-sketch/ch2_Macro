# -*- coding: utf-8 -*-
"""집합 2단계 실제 적용 모드(--real-apply) — 플래그 + DB 이름 재입력 + 동기화 확인 통과 파일이 모두 있어야 실제 DB 에 쓴다.
리허설 모드의 가드는 그대로다. (DB 에 접속하지 않는 단위 테스트)"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "pipeline", ROOT / "pipeline" / "collective"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from collective import migrate_p2_keys as mig  # noqa: E402


@pytest.fixture(autouse=True)
def _reset():
    mig._REAL_ALLOWED.clear()
    yield
    mig._REAL_ALLOWED.clear()


OPS = ROOT / "scripts" / "ops" / "collective_p2_verify"
if str(OPS) not in sys.path:
    sys.path.insert(0, str(OPS))
import _common as C  # noqa: E402


_N = [0]


def _result(tmp_path, db, status="pass", hours_ago=1, kind="prod_sync_check", **over):
    """prod_sync_check compare --result-out 과 같은 형식(make_result)."""
    obj = C.make_result(kind=kind, status=status, left_db=db, right_db=db, diff=0, unverified=[], failures=[])
    obj["created_at"] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours_ago)).isoformat()
    obj.update(over)
    _N[0] += 1
    f = tmp_path / f"sync_{db}_{status}_{_N[0]}.json"
    f.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return f


class _Conn:
    def __init__(self, db):
        self.db = db

    def execute(self, *_a, **_k):
        db = self.db

        class R:
            def scalar(self_inner):
                return db
        return R()


def test_rehearsal_guard_unchanged_without_real_mode():
    assert mig.assert_rehearsal_db(_Conn("collective_stats_p2r"), "collective_stats_p2r") == "collective_stats_p2r"
    with pytest.raises(mig.GuardError):
        mig.assert_rehearsal_db(_Conn("collective_stats"), "collective_stats")


def test_real_apply_needs_all_three_conditions(tmp_path):
    ok = [_result(tmp_path, "collective_stats"), _result(tmp_path, "rent_stats"), _result(tmp_path, "built_stats")]
    names = ["collective_stats", "built_stats", "rent_stats"]
    with pytest.raises(mig.GuardError, match="다시 입력"):
        mig.enable_real_apply(names, ["collective_stats", "built_stats"], ok)                      # 재입력 빠짐
    with pytest.raises(mig.GuardError, match="다시 입력"):
        mig.enable_real_apply(names, ["collective_stats", "built_stats", "rent_stats_p2r"], ok)    # 재입력 다름
    with pytest.raises(mig.GuardError, match="통과 결과가 없는"):
        mig.enable_real_apply(names, names, ok[:2])                                               # built 결과 없음
    with pytest.raises(mig.GuardError, match="통과가 아님"):
        mig.enable_real_apply(["collective_stats"], ["collective_stats"], [_result(tmp_path, "collective_stats", "unverified")])
    with pytest.raises(mig.GuardError, match="통과가 아님"):
        mig.enable_real_apply(["collective_stats"], ["collective_stats"], [_result(tmp_path, "collective_stats", "diff")])
    with pytest.raises(mig.GuardError, match="오래됨"):
        mig.enable_real_apply(["collective_stats"], ["collective_stats"], [_result(tmp_path, "collective_stats", hours_ago=72)])
    with pytest.raises(mig.GuardError, match="결과 파일이 아님"):
        mig.enable_real_apply(["collective_stats"], ["collective_stats"],
                              [_result(tmp_path, "collective_stats", kind="prod_hash_compare")])
    with pytest.raises(mig.GuardError, match="파일 없음"):
        mig.enable_real_apply(["collective_stats"], ["collective_stats"], [tmp_path / "none.json"])
    with pytest.raises(mig.GuardError, match="실제 적용 대상이 아닌"):
        mig.enable_real_apply(["land_stats"], ["land_stats"], [_result(tmp_path, "land_stats")])
    with pytest.raises(mig.GuardError, match="실제 적용 대상이 아닌"):
        mig.enable_real_apply(["collective_stats_p2r"], ["collective_stats_p2r"], [_result(tmp_path, "collective_stats_p2r")])
    # validate_result: 미래 시각·실패 기록·diff·unverified·대상 불일치·필드 빠짐 → 모두 통과 아님
    one = (["collective_stats"], ["collective_stats"])
    for bad in (dict(hours_ago=-2), dict(failures=["q 시간 초과"]), dict(diff=1), dict(unverified=["rent_transactions"]),
                dict(targets=["collective_stats", "rent_stats"]), dict(right_db="rent_stats"), dict(created_at="어제")):
        kw = {k: v for k, v in bad.items() if k == "hours_ago"}
        with pytest.raises(mig.GuardError, match="통과가 아님"):
            mig.enable_real_apply(*one, [_result(tmp_path, "collective_stats", **kw, **{k: v for k, v in bad.items() if k != "hours_ago"})])
    f = _result(tmp_path, "collective_stats")
    d = json.loads(f.read_text(encoding="utf-8"))
    del d["failures"]
    f.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(mig.GuardError, match="통과가 아님"):
        mig.enable_real_apply(*one, [f])
    assert mig._REAL_ALLOWED == set()
    assert mig.enable_real_apply(names, list(reversed(names)), ok) == set(names)
    assert mig.assert_rehearsal_db(_Conn("collective_stats"), "collective_stats") == "collective_stats"
    with pytest.raises(mig.GuardError):                       # 허가된 이름이어도 접속 DB ≠ 지정 DB 는 거부
        mig.assert_rehearsal_db(_Conn("collective_stats"), "rent_stats")
    with pytest.raises(mig.GuardError):                       # 허가 밖 보호 DB 는 여전히 거부
        mig.assert_rehearsal_db(_Conn("land_stats"), "land_stats")


C2_OK = ["--c2-approved-sha256", "a" * 64, "--c2-approved-rows", "4311"]   # 판정 표 대조 인자(형식만 — 가드가 먼저 막는다)


def test_cli_entrypoints_refuse_real_db_without_real_mode_and_reject_real_rollback(tmp_path):
    from collective import fix_p2_deal_types as fdt
    from collective import prune_split_annual_p2 as pr

    with pytest.raises(mig.GuardError, match="리허설 이름"):
        mig.main(["--collective-db", "collective_stats", "--apply"])
    with pytest.raises(mig.GuardError, match="c2-approved"):          # C-2 판정 승인값 없으면 가장 먼저 거부
        mig.main(["--collective-db", "collective_stats", "--real-apply"])
    with pytest.raises(mig.GuardError, match="다시 입력"):
        mig.main(["--collective-db", "collective_stats", "--real-apply", *C2_OK])
    with pytest.raises(mig.GuardError, match="적용만"):
        mig.main(["--collective-db", "collective_stats", "--real-apply", "--rollback"])
    with pytest.raises(mig.GuardError, match="리허설 이름"):
        fdt.main(["--collective-db", "collective_stats", "--apply"])
    with pytest.raises(mig.GuardError, match="통과 결과가 없는"):
        fdt.main(["--collective-db", "collective_stats", "--real-apply", "--confirm-db", "collective_stats"])
    with pytest.raises(mig.GuardError, match="리허설 이름"):
        pr.main(["--collective-db", "collective_stats", "--apply"])
    with pytest.raises(SystemExit):
        pr.main(["--collective-db", "collective_stats", "--real-apply", "--rollback"])
    with pytest.raises(mig.GuardError, match="통과가 아님"):
        pr.main(["--collective-db", "collective_stats", "--real-apply", "--confirm-db", "collective_stats",
                 "--sync-result", str(_result(tmp_path, "collective_stats", "unverified"))])
    assert mig._REAL_ALLOWED == set()                         # 실패한 시도는 허가를 남기지 않음


def test_sync_result_file_from_prod_sync_check_is_accepted(tmp_path):
    """prod_sync_check compare --result-out 이 만든 파일 형식을 그대로 받는다."""
    ops = str(ROOT / "scripts" / "ops" / "collective_p2_verify")
    if ops not in sys.path:
        sys.path.insert(0, ops)
    import _common as C

    f = tmp_path / "res.json"
    C.write_result(f, kind="prod_sync_check", status="pass", left_db="collective_stats", right_db="collective_stats",
                   detail={"diff": 0})
    assert mig.enable_real_apply(["collective_stats"], ["collective_stats"], [f]) == {"collective_stats"}


def test_real_apply_requires_local_loopback_target(tmp_path, monkeypatch):
    """--real-apply 는 접속 대상이 로컬 루프백이어야 한다 — URL 은 localhost 라도 libpq 최종 인자(PGHOSTADDR 등)가 원격이면 거부."""
    good = [str(_result(tmp_path, "collective_stats"))]
    args = ["--collective-db", "collective_stats", "--real-apply", "--confirm-db", "collective_stats", "--sync-result", *good,
            *C2_OK]
    for k in ("PGHOST", "PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("PGHOSTADDR", "10.0.0.5")
    with pytest.raises(mig.GuardError, match="실제 적용 거부"):
        mig.main(["--base-url", "postgresql+psycopg2://u:p@localhost:5432/postgres", *args])
    monkeypatch.delenv("PGHOSTADDR")
    with pytest.raises(mig.GuardError, match="실제 적용 거부"):
        mig.main(["--base-url", "postgresql+psycopg2://u:p@localhost:5432/postgres?host=13.209.203.178", *args])
    monkeypatch.setenv("PGSERVICE", "prod")
    with pytest.raises(mig.GuardError, match="실제 적용 거부"):
        mig.main(["--base-url", "postgresql+psycopg2://u:p@localhost:5432/postgres", *args])
    assert mig._REAL_ALLOWED == set()
