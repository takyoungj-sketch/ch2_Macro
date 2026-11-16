# -*- coding: utf-8 -*-
"""집합 2단계 — R5 스모크 스크립트(scripts/ops/collective_p2_r5_smoke.py): 로컬 전용 가드·판정·종료 코드."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("r5", ROOT / "scripts" / "ops" / "collective_p2_r5_smoke.py")
r5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r5)

SAMPLES = {"c01_old": "a" * 64, "c2_old": "b" * 64, "normal": "c" * 64}


@pytest.mark.parametrize("url", ["http://127.0.0.1:8000", "http://localhost:8017/", "http://[::1]:8000"])
def test_local_urls_allowed(url):
    assert r5.assert_local(url) == url.rstrip("/")


@pytest.mark.parametrize("url", ["http://13.209.203.178:8000", "https://ch2macro.example.com", "http://127.0.0.1.nip.io",
                                 "ftp://127.0.0.1", "127.0.0.1:8000"])
def test_non_local_urls_refused(url):
    with pytest.raises(r5.SmokeError, match="로컬 주소만"):
        r5.assert_local(url)


def test_cli_refuses_prod_url_before_db_or_http(monkeypatch):
    called = []
    monkeypatch.setattr(r5, "fetch", lambda *a, **k: called.append(a) or (200, {}))
    assert r5.main(["--base-url", "http://13.209.203.178:8000"]) == 2
    assert called == []


def _fake(responses):
    def f(url, headers):
        for kind, key in SAMPLES.items():
            if key in url:
                return responses[kind]
        raise AssertionError(url)
    return f


def test_all_three_pass():
    rows = r5.run("http://127.0.0.1:8000", SAMPLES, fetch_=_fake({
        "c01_old": (409, {"key_status": "split"}), "c2_old": (200, {"key_split_c2": {"new_keys": ["x"]}}),
        "normal": (200, {"rows": []})}))
    assert [r["ok"] for r in rows] == [True, True, True]
    assert all(len(r["key8"]) == 8 for r in rows)                         # 키는 앞 8자만


@pytest.mark.parametrize("kind,resp", [
    ("c01_old", (200, {})),                                   # C-01 옛 키가 열림 → 실패
    ("c01_old", (500, None)),
    ("c2_old", (409, {"key_status": "split"})),               # C-2 옛 키가 409 → 실패
    ("c2_old", (200, {"rows": []})),                          # 안내 없는 200 → 실패
    ("c2_old", (404, None)),
    ("normal", (200, {"key_split_c2": {"new_keys": ["x"]}})),  # 일반 키에 안내 → 실패
    ("normal", (500, None)),
])
def test_any_mismatch_fails(kind, resp):
    good = {"c01_old": (409, {}), "c2_old": (200, {"key_split_c2": {"a": 1}}), "normal": (200, {})}
    rows = r5.run("http://127.0.0.1:8000", SAMPLES, fetch_=_fake({**good, kind: resp}))
    assert [r["kind"] for r in rows if not r["ok"]] == [kind]


def test_main_exit_1_on_mismatch(monkeypatch, tmp_path):
    monkeypatch.setattr(r5, "pick_samples", lambda c: SAMPLES)

    class _E:
        def connect(self):
            class _C:
                def __enter__(self_):
                    return None

                def __exit__(self_, *a):
                    return False
            return _C()

        def dispose(self):
            pass

    monkeypatch.setattr(r5, "read_only_engine", lambda *a, **k: _E())
    monkeypatch.setattr(r5, "fetch", _fake({"c01_old": (200, {}), "c2_old": (200, {"key_split_c2": 1}), "normal": (200, {})}))
    assert r5.main(["--out", str(tmp_path / "o.json")]) == 1
    monkeypatch.setattr(r5, "fetch", _fake({"c01_old": (409, {}), "c2_old": (200, {"key_split_c2": 1}), "normal": (200, {})}))
    assert r5.main(["--out", str(tmp_path / "o.json")]) == 0


def test_script_does_not_need_pipeline_and_reads_env_file(tmp_path, monkeypatch):
    """운영 서버에 pipeline/ 이 없어도 돈다 — 백엔드 venv(sqlalchemy·psycopg2)만. DB 서버는 env 파일에서."""
    src = (ROOT / "scripts" / "ops" / "collective_p2_r5_smoke.py").read_text(encoding="utf-8")
    assert "from collective" not in src and "import collective" not in src and 'REPO / "pipeline"' not in src
    env = tmp_path / ".env"
    env.write_text('# c\nCOLLECTIVE_DATABASE_URL="postgresql://u:p@127.0.0.1:5432/collective_stats"\n', encoding="utf-8")
    monkeypatch.delenv("COLLECTIVE_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)          # 다른 테스트가 남긴 환경변수(대체 키)도 지운다
    e = r5.read_only_engine("collective_stats_p2r", env)
    assert e.url.database == "collective_stats_p2r" and e.url.drivername == "postgresql+psycopg2"
    e.dispose()
    with pytest.raises(r5.SmokeError, match="COLLECTIVE_DATABASE_URL"):
        r5.read_only_engine("x", tmp_path / "none.env")
