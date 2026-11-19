#!/usr/bin/env python3
"""임대 C-2 스모크. pipeline 을 import 하지 않고 백엔드 venv 와 env 파일만 쓴다.

로컬 주소가 아니면 종료 코드 2. 비로그인 임대 경로는 401 과 '로그인이 필요합니다.' 만 확인한다.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse

from sqlalchemy import text

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
LOGIN = "로그인이 필요합니다."
PENDING = "확인되지 않은 거래 포함"


class SmokeError(RuntimeError):
    pass


def assert_local(base_url: str) -> str:
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or host not in LOCAL_HOSTS:
        raise SmokeError("로컬 주소만 허용한다")
    return base_url.rstrip("/")


def anon_ok(status: int, body: str) -> bool:
    return status == 401 and LOGIN in body and PENDING not in body


def table_state(conn) -> str:
    if not conn.execute(text("SELECT to_regclass('public.rent_building_key_c2_units')")).scalar():
        return "missing"
    count = int(conn.execute(text("SELECT count(*) FROM rent_building_key_c2_units")).scalar() or 0)
    return "empty" if count == 0 else "present"


def list_ok(state: str, status: int, body: str) -> bool:
    if status != 200:
        return False
    if state in ("missing", "empty"):
        return PENDING not in body
    return True


def fetch_anon(base_url: str) -> tuple[int, str]:
    url = assert_local(base_url) + "/api/rent/buildings"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="임대 C-2 스모크")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--skip-http", action="store_true")
    args = parser.parse_args(argv)
    try:
        assert_local(args.base_url)
    except SmokeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.skip_http:
        print(json.dumps({"local": True}))
        return 0
    status, body = fetch_anon(args.base_url)
    if not anon_ok(status, body):
        print("비로그인 응답이 401 이 아니다", file=sys.stderr)
        return 1
    print(json.dumps({"anon": status}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
