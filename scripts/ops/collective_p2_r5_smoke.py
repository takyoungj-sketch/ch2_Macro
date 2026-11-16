#!/usr/bin/env python3
"""집합 2단계 — 롤백 기준 R5 스모크(런북 8절·6.3): 키 이전 뒤 집합 상세가 옛 키를 맞게 처리하는지.

  python scripts/ops/collective_p2_r5_smoke.py                                   # 기본 http://127.0.0.1:8000
  python scripts/ops/collective_p2_r5_smoke.py --base-url http://127.0.0.1:8017 --collective-db collective_stats_p2r
  # 운영 서버 안(반영 뒤, Codex/Opus): 서버 localhost + 운영 DB 이름, 백엔드 venv 로
  cd /opt/ch2_Macro && backend/.venv/bin/python scripts/ops/collective_p2_r5_smoke.py \\
      --base-url http://127.0.0.1:8000 --collective-db collective_stats --out /tmp/r5_smoke.json

검사(집합 상세 `GET /api/collective/buildings/{key}/stats/rolling?window_years=5`):
  1. C-01 분할 옛 키(연결표 reason split · honam_sido+split)      → 409
  2. C-2 옛 키(판정 표 split base_key = 본 조각 옛 키, 연결표 c2)   → 200 + JSON 본문 최상위 `key_split_c2`(분할 안내)
  3. 일반 키(연결표·판정 표에 없는 키)                            → 200 + `key_split_c2` 없음
  하나라도 다르면 종료 코드 1. 표본 고르기·접속 실패는 2.

- **로컬 전용:** 기준 URL 의 호스트가 localhost·127.0.0.1·::1 이 아니면 실행하지 않는다(종료 코드 2). 운영 반영 뒤 실행은 Codex/Opus 몫.
- 표본 키는 DB(기본 리허설 `collective_stats_p2r`, 읽기 전용 세션)에서 고른다. 출력에는 키 앞 8자만 — 지번·주소·이름은 내지 않는다.
- 의존: sqlalchemy·psycopg2 와 표준 라이브러리만(백엔드 venv). `pipeline/` 을 import 하지 않는다. DB 접속은 환경변수 또는
  `--env-file`(기본 backend/.env)의 COLLECTIVE_DATABASE_URL 에서 서버를 읽고 DB 이름만 바꾼다.
- 토큰이 필요한 서버면 `--token-env <환경변수 이름>`(값은 출력하지 않음, X-Api-Token 헤더).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

REPO = Path(__file__).resolve().parents[2]
# 서버(운영)에는 pipeline/ 이 없을 수 있다 → 이 스크립트는 pipeline 을 import 하지 않는다(sqlalchemy·psycopg2 만, 백엔드 venv 에 있음)
DEFAULT_ENV_FILE = REPO / "backend" / ".env"


def _env_value(name: str, env_file: Path) -> str:
    """환경변수 → 없으면 env 파일의 NAME=값(따옴표 벗김). 값은 출력하지 않는다."""
    v = os.environ.get(name, "").strip()
    if v:
        return v
    if env_file.is_file():
        for ln in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if ln.startswith(f"{name}=") and not ln.startswith("#"):
                return ln.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def read_only_engine(dbname: str, env_file: Path = DEFAULT_ENV_FILE):
    """COLLECTIVE_DATABASE_URL(없으면 DATABASE_URL)의 서버에 dbname 으로, 모든 세션 읽기 전용."""
    url = _env_value("COLLECTIVE_DATABASE_URL", env_file) or _env_value("DATABASE_URL", env_file)
    if not url:
        raise SmokeError(f"COLLECTIVE_DATABASE_URL 이 환경변수·{env_file.name} 에 없음")
    u = make_url(url).set(database=dbname)
    if u.drivername == "postgresql":
        u = u.set(drivername="postgresql+psycopg2")
    return create_engine(u, connect_args={"options": "-c default_transaction_read_only=on -c statement_timeout=60000"})

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
PATH = "/api/collective/buildings/{key}/stats/rolling?window_years=5"
C01_REASONS = ("split", "honam_sido+split")
C2_REASONS = ("c2_split", "honam_sido+c2_split")


class SmokeError(RuntimeError):
    pass


def assert_local(base_url: str) -> str:
    u = urlparse(base_url)
    host = (u.hostname or "").lower()
    if u.scheme not in ("http", "https") or host not in LOCAL_HOSTS:
        raise SmokeError(f"로컬 주소만 허용(localhost·127.0.0.1·::1): {u.scheme}://{host or '?'} — 운영 URL 로는 실행하지 않는다")
    return base_url.rstrip("/")


def pick_samples(conn) -> dict[str, str]:
    """C-01 분할 옛 키 · C-2 옛 키(본 조각) · 일반 키를 하나씩. 통계가 있는(상세가 열리는) 키 중 거래 많은 순."""
    c01 = conn.execute(text("""SELECT old_key FROM collective_building_key_map WHERE reason IN :r
                               GROUP BY old_key ORDER BY sum(coalesce(n_tx, 0)) DESC, old_key LIMIT 1""")
                       .bindparams(r=C01_REASONS)).scalar()
    c2 = conn.execute(text("""SELECT u.base_key FROM collective_building_key_c2_units u
                              JOIN collective_building_key_map m ON m.old_key = u.base_key AND m.reason IN :r
                              WHERE u.decision = 'split'
                                AND EXISTS (SELECT 1 FROM collective_building_stats s WHERE s.building_key = u.base_key)
                              GROUP BY u.base_key ORDER BY sum(coalesce(m.n_tx, 0)) DESC, u.base_key LIMIT 1""")
                      .bindparams(r=C2_REASONS)).scalar()
    normal = conn.execute(text("""SELECT s.building_key FROM collective_building_stats s
                                  WHERE s.asset_type = 'apartment' AND s.window_years = 5
                                    AND NOT EXISTS (SELECT 1 FROM collective_building_key_map m
                                                    WHERE m.old_key = s.building_key OR m.new_key = s.building_key)
                                    AND NOT EXISTS (SELECT 1 FROM collective_building_key_c2_units u WHERE u.base_key = s.building_key)
                                  ORDER BY s.count DESC NULLS LAST, s.building_key LIMIT 1""")).scalar()
    out = {"c01_old": c01, "c2_old": c2, "normal": normal}
    miss = [k for k, v in out.items() if not v]
    if miss:
        raise SmokeError(f"표본 키를 고르지 못함: {miss}")
    return {k: str(v).strip() for k, v in out.items()}


def fetch(url: str, headers: dict[str, str], timeout: float = 30.0) -> tuple[int, object]:
    req = urllib.request.Request(url, headers={"Accept": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as ex:
        status, raw = ex.code, ex.read()
    try:
        body = json.loads(raw.decode("utf-8")) if raw else None
    except ValueError:
        body = None
    return status, body


def judge(kind: str, status: int, body) -> tuple[bool, str]:
    note = body.get("key_split_c2") if isinstance(body, dict) else None
    if kind == "c01_old":
        return status == 409, "409 기대"
    if kind == "c2_old":
        return status == 200 and bool(note), "200 + key_split_c2 기대"
    return status == 200 and not note, "200 · key_split_c2 없음 기대"


def run(base_url: str, samples: dict[str, str], *, headers: dict[str, str] | None = None, fetch_=None) -> list[dict]:
    base = assert_local(base_url)
    fetch_ = fetch_ or fetch
    rows = []
    for kind in ("c01_old", "c2_old", "normal"):
        key = samples[kind]
        status, body = fetch_(base + PATH.format(key=key), headers or {})
        ok, want = judge(kind, status, body)
        rows.append({"kind": kind, "key8": key[:8], "status": status, "want": want, "ok": ok,
                     "key_split_c2": bool(isinstance(body, dict) and body.get("key_split_c2"))})
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--collective-db", default="collective_stats_p2r", help="표본 키를 고를 DB(읽기 전용, 기본 리허설)")
    p.add_argument("--env-file", default=str(DEFAULT_ENV_FILE),
                   help="COLLECTIVE_DATABASE_URL 을 읽을 env 파일(기본 backend/.env, 환경변수가 우선)")
    p.add_argument("--token-env", default="", help="X-Api-Token 값을 담은 환경변수 이름(값은 출력 안 함)")
    p.add_argument("--out", default=str(REPO / "logs" / "collective_p2" / "r5_smoke.json"))
    a = p.parse_args(argv)
    try:
        assert_local(a.base_url)
        eng = read_only_engine(a.collective_db, Path(a.env_file))
        try:
            with eng.connect() as c:
                samples = pick_samples(c)
        finally:
            eng.dispose()
        headers = {}
        if a.token_env:
            tok = os.environ.get(a.token_env, "")
            if not tok:
                raise SmokeError(f"환경변수 {a.token_env} 가 비었음")
            headers["X-Api-Token"] = tok
        rows = run(a.base_url, samples, headers=headers)
    except (SmokeError, OSError) as ex:
        print(f"중단: {ex}", file=sys.stderr)
        return 2
    for r in rows:
        print(f"{'OK ' if r['ok'] else 'NG '} {r['kind']:8s} key {r['key8']}… → {r['status']} "
              f"(key_split_c2 {'있음' if r['key_split_c2'] else '없음'}) · {r['want']}")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"base_url": assert_local(a.base_url), "collective_db": a.collective_db, "rows": rows},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
    bad = [r for r in rows if not r["ok"]]
    print("R5 스모크: " + ("통과" if not bad else f"실패 {len(bad)}건 — 롤백 기준 R5"))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
