"""테스트 공통 설정."""

import ctypes
import threading
from pathlib import Path

import pytest

_DB_FIXTURE_LIMIT_S = 30
_DB_FIXTURE_FILES = {
    "test_rent_c2_pending.py",
    "test_collective_p2_key_remap.py",
}


class DbFixtureTimeout(AssertionError):
    def __init__(self, *_args):
        super().__init__(
            "DB fixture 테스트가 30초 안에 끝나지 않았다. "
            "로컬 PostgreSQL 사용자와 권한을 확인한다."
        )


def _interrupt(ident: int) -> None:
    tid = ctypes.c_ulong(ident)
    exc = ctypes.py_object(DbFixtureTimeout)
    count = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, exc)
    if count == 0:
        return
    if count > 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    if Path(str(item.fspath)).name not in _DB_FIXTURE_FILES:
        yield
        return
    ident = threading.get_ident()
    done = threading.Event()

    def _watch() -> None:
        if not done.wait(_DB_FIXTURE_LIMIT_S):
            _interrupt(ident)

    watcher = threading.Thread(target=_watch, daemon=True)
    watcher.start()
    try:
        yield
    finally:
        done.set()
        watcher.join(timeout=1)


@pytest.fixture(autouse=True)
def _isolated_ai_usage_log(tmp_path_factory, monkeypatch):
    """AI 사용량·질문 장부를 저장소 logs/ 가 아니라 임시 폴더에 쓴다."""
    from app.config import settings

    monkeypatch.setattr(settings, "ai_usage_log_dir", str(tmp_path_factory.mktemp("ai_usage")))
    # 미지원 파라미터 경고 JSONL 도 저장소 logs/ 가 아니라 임시 폴더에 쓴다(집합 1단계 C-05).
    monkeypatch.setattr(
        settings, "api_param_warn_path", str(tmp_path_factory.mktemp("api_param_warn") / "api_param_warn.jsonl")
    )
