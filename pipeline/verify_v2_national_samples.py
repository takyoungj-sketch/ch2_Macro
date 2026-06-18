#!/usr/bin/env python3
"""
전국 V2 배치 후 무료 API 샘플 검증 (시도별 대표 법정동).

사용:
  python verify_v2_national_samples.py --base-url http://127.0.0.1:8000 --as-of-month 2025-12-01

환경:
  VERIFY_V2_API_BASE (기본 http://127.0.0.1:8000)
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import requests

# 시도별 대표 코드 (원장·region_codes 에 따라 404이면 코드만 조정)
DEFAULT_SAMPLES: list[tuple[str, str]] = [
    ("서울", "1111010100"),
    ("경기", "4113110100"),
    ("부산", "2635010100"),
    ("충북", "4311311300"),
    ("제주", "5011010100"),
]

GHOST_CODE = "9999999999"


def check_one(
    session: requests.Session,
    base: str,
    code: str,
    window_years: int,
    as_of_month: str,
    expect_error: bool = False,
) -> bool:
    url = f"{base.rstrip('/')}/api/free/v2/stats/{code}"
    params: dict[str, Any] = {"window_years": window_years, "as_of_month": as_of_month}
    try:
        r = session.get(url, params=params, timeout=120)
    except requests.RequestException as exc:
        print(f"  [FAIL] network {code} w={window_years}: {exc}")
        return False

    if expect_error:
        if r.status_code == 404:
            print(f"  [OK] expected 404 for {code} w={window_years}")
            return True
        print(f"  [FAIL] expected 404, got {r.status_code} for {code}")
        return False

    if r.status_code == 404:
        detail = ""
        try:
            detail = str(r.json().get("detail", ""))
        except Exception:
            detail = r.text[:200]
        if expect_error or "V2 집계가 없습니다" in detail:
            print(f"  [OK] {code} w={window_years} — no V2 row (404, sparse)")
            return True
        print(f"  [FAIL] {code} w={window_years} unexpected 404 {detail[:200]}")
        return False

    if r.status_code != 200:
        print(f"  [FAIL] {code} w={window_years} HTTP {r.status_code} {r.text[:200]}")
        return False

    data = r.json()
    need = ("as_of_month", "period_start", "period_end", "window_years", "total")
    for k in need:
        if k not in data:
            print(f"  [FAIL] {code} missing key {k}")
            return False
    total = data.get("total") or {}
    if "count" not in total:
        print(f"  [FAIL] {code} total.count missing")
        return False
    print(
        f"  [OK] {code} w={window_years} n={total['count']} "
        f"period={data['period_start']}..{data['period_end']}"
    )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="V2 무료 API 전국 샘플 검증")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("VERIFY_V2_API_BASE", "http://127.0.0.1:8000"),
        help="FastAPI 루트 (프록시 없이 직접 호출)",
    )
    parser.add_argument(
        "--as-of-month",
        default="2025-12-01",
        help="V2 as_of_month (YYYY-MM-01)",
    )
    parser.add_argument(
        "--windows",
        default="3,5",
        help="확인할 window_years (쉼표)",
    )
    args = parser.parse_args()

    try:
        windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    except ValueError:
        raise SystemExit("invalid --windows") from None
    for w in windows:
        if w not in (3, 5):
            raise SystemExit("only 3 and 5 supported for free V2") from None

    session = requests.Session()
    ok_all = True

    print(f"BASE={args.base_url} as_of_month={args.as_of_month} windows={windows}")
    for label, code in DEFAULT_SAMPLES:
        print(f"[{label} {code}]")
        for w in windows:
            if not check_one(session, args.base_url, code, w, args.as_of_month):
                ok_all = False

    print("[유효하지 않은 법정동 코드]")
    for w in windows:
        if not check_one(
            session, args.base_url, GHOST_CODE, w, args.as_of_month, expect_error=True
        ):
            ok_all = False

    if not ok_all:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
