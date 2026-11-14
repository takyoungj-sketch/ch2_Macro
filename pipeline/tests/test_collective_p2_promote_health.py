# -*- coding: utf-8 -*-
"""vps_promote_db_sql.sh 의 /health 대기 — 재시작 직후 실패해도 최대 60초 다시 묻고, 끝내 실패하면 종료 코드 1.
스크립트에서 wait_health 함수만 떼어 가짜 curl 로 돌린다(운영 서버·DB 접속 없음)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "deploy" / "scripts" / "vps_promote_db_sql.sh"
RUNBOOK = ROOT / "docs" / "ops" / "COLLECTIVE_P2_RUNBOOK.md"


def _bash() -> str | None:
    for c in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files\Git\usr\bin\bash.exe"):
        if Path(c).is_file():
            return c
    b = shutil.which("bash")
    return None if (b and "system32" in b.lower()) else b   # WSL bash 는 쓰지 않음


def _func() -> str:
    s = SCRIPT.read_text(encoding="utf-8")
    m = re.search(r"(HEALTH_URL=.*?\nwait_health\(\) \{.*?\n\})", s, re.S)
    assert m, "wait_health 함수가 없음"
    return m.group(1)


@pytest.mark.parametrize("fail_times, wait, expect_rc", [(2, 20, 0), (999, 3, 1)])
def test_wait_health_retries_then_succeeds_or_fails(tmp_path, fail_times, wait, expect_rc):
    bash = _bash()
    if not bash:
        pytest.skip("bash 없음")
    fake = tmp_path / "bin"
    fake.mkdir()
    cnt = tmp_path / "n"
    cnt.write_text("0")
    (fake / "curl").write_text(
        "#!/usr/bin/env bash\n"
        f'n=$(cat "{cnt.as_posix()}"); n=$((n+1)); echo $n > "{cnt.as_posix()}"\n'
        f'if [ $n -le {fail_times} ]; then exit 7; fi\n'
        'echo \'{"status":"ok"}\'\n', encoding="utf-8", newline="\n")
    os.chmod(fake / "curl", 0o755)
    code = "set -euo pipefail\n" + _func() + "\nsleep() { :; }\nwait_health\n"   # sleep 은 건너뛰어 빠르게
    env = {**os.environ, "CH2_HEALTH_WAIT_SEC": str(wait)}
    fp = fake.as_posix()
    if re.match(r"^[A-Za-z]:", fp):                       # Git Bash PATH 는 ':' 로 나뉘므로 C:/… → /c/…
        fp = "/" + fp[0].lower() + fp[2:]
    r = subprocess.run([bash, "-c", f'export PATH="{fp}:$PATH"; {code}'], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=60)
    assert r.returncode == expect_rc, r.stderr
    if expect_rc == 0:
        assert '"status":"ok"' in r.stdout and int(cnt.read_text()) == fail_times + 1
    else:
        assert "응답하지 않음" in r.stderr


def test_promote_and_runbook_rollback_use_60s_wait():
    s = SCRIPT.read_text(encoding="utf-8")
    assert 'HEALTH_WAIT="${CH2_HEALTH_WAIT_SEC:-60}"' in s and "sleep 4\ncurl" not in s
    rb = RUNBOOK.read_text(encoding="utf-8")
    assert "curl -sf http://127.0.0.1:8000/health\n" not in rb          # 롤백 명령도 한 번 묻고 끝나지 않음
    assert "for i in $(seq 1 30)" in rb
