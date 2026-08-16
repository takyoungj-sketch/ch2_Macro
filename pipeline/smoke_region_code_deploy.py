# -*- coding: utf-8 -*-
"""Multi-entry-point region-code deploy smoke (D-028).

Exercises land · built · collective · profile · twin · map · search APIs and
asserts user-facing codes are canonical (never raw historical).

Exit 0 = PASS, 1 = FAIL.

Usage:
  cd backend
  .venv/Scripts/python.exe ../pipeline/smoke_region_code_deploy.py
  .venv/Scripts/python.exe ../pipeline/smoke_region_code_deploy.py --base-url https://macro.ch2data.com
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

# Pilot pairs — same as verify_canonical_resolver_migration.py
HIST_EUP = "43770340"
CANON_EUP = "43770256"
HIST_RI = "4377034026"
CANON_RI = "4377025626"
HIST_EUP_YANGJI = "41461360"
CANON_EUP_YANGJI = "41461262"

FORBIDDEN = {HIST_EUP, HIST_RI, HIST_EUP_YANGJI}


@dataclass
class CheckResult:
    name: str
    status: str  # pass | fail | skip
    detail: str = ""


@dataclass
class SmokeReport:
    base_url: str
    results: list[CheckResult] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.results.append(CheckResult(name=name, status=status, detail=detail))

    @property
    def passed(self) -> bool:
        return all(r.status != "fail" for r in self.results)


def _headers(token: str | None) -> dict[str, str]:
    h: dict[str, str] = {"Accept": "application/json"}
    if token:
        h["X-Api-Token"] = token
    return h


def _get_json(
    base: str,
    path: str,
    *,
    token: str | None,
    params: dict[str, Any] | None = None,
    timeout: float = 30,
) -> tuple[int, Any]:
    qs = urllib.parse.urlencode(params or {}, doseq=True)
    url = f"{base.rstrip('/')}{path}"
    if qs:
        url = f"{url}?{qs}"
    req = urllib.request.Request(url, headers=_headers(token), method="GET")
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw) if raw else {"detail": exc.reason}
        except json.JSONDecodeError:
            payload = {"detail": raw.decode("utf-8", errors="replace")}
        return exc.code, payload


def _assert_no_historical(codes: list[str], *, context: str) -> str | None:
    bad = [c for c in codes if c in FORBIDDEN]
    if bad:
        return f"{context}: historical code(s) in response: {bad}"
    return None


def _collect_codes(obj: Any, acc: list[str]) -> None:
    if obj is None:
        return
    if isinstance(obj, str):
        s = obj.strip()
        if s.isdigit() and len(s) >= 5:
            acc.append(s)
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.endswith("_code") or k == "code":
                if isinstance(v, str) and v.strip().isdigit():
                    acc.append(v.strip())
            _collect_codes(v, acc)
    elif isinstance(obj, list):
        for item in obj:
            _collect_codes(item, acc)


def _run_land_free_v2(report: SmokeReport, base: str, token: str | None) -> None:
    name = "land.free_v2.stats(canonical)"
    status, data = _get_json(
        base,
        f"/api/free/v2/stats/{CANON_RI}",
        token=token,
        params={"window_years": 3},
    )
    if status == 404:
        report.add(name, "skip", "no mart row for pilot ri")
        return
    if status != 200:
        report.add(name, "fail", f"HTTP {status}: {data}")
        return
    codes: list[str] = []
    _collect_codes(data, codes)
    err = _assert_no_historical(codes, context=name)
    if err:
        report.add(name, "fail", err)
        return
    total = (data or {}).get("total") or {}
    cnt = total.get("count") if isinstance(total, dict) else None
    report.add(name, "pass", f"count={cnt}")


def _run_land_free_v2_hist_input(report: SmokeReport, base: str, token: str | None) -> None:
    name = "land.free_v2.stats(historical→resolve)"
    status, data = _get_json(
        base,
        f"/api/free/v2/stats/{HIST_RI}",
        token=token,
        params={"window_years": 3},
    )
    if status == 404:
        report.add(name, "skip", "historical path 404 (mart/resolver)")
        return
    if status != 200:
        report.add(name, "fail", f"HTTP {status}: {data}")
        return
    codes: list[str] = []
    _collect_codes(data, codes)
    err = _assert_no_historical(codes, context=name)
    report.add(name, "pass" if not err else "fail", err or "resolved OK")


def _run_upper_stats(report: SmokeReport, base: str, token: str | None) -> None:
    name = "land.paid.upper-stats(hist eup input)"
    status, data = _get_json(
        base,
        f"/api/paid/upper-stats/eupmyeondong/{HIST_EUP}",
        token=token,
        params={"window_years": 3},
    )
    if status == 404:
        report.add(name, "skip", "upper mart missing for pilot")
        return
    if status != 200:
        report.add(name, "fail", f"HTTP {status}: {data}")
        return
    meta_code = (data or {}).get("region_code") or ((data or {}).get("meta") or {}).get("region_code")
    if meta_code != CANON_EUP:
        report.add(name, "fail", f"meta.region_code={meta_code} expected {CANON_EUP}")
        return
    report.add(name, "pass", f"meta.region_code={meta_code}")


def _run_built_lookup(report: SmokeReport, base: str, token: str | None) -> None:
    for label, inp, expect in (
        ("hist", HIST_EUP, CANON_EUP),
        ("canon", CANON_EUP, CANON_EUP),
    ):
        name = f"built.lookup-code({label})"
        status, data = _get_json(
            base,
            "/api/built/regions/lookup-code",
            token=token,
            params={"code": inp, "level": "eupmyeondong"},
        )
        if status == 503:
            report.add(name, "skip", "built DB not configured")
            return
        if status != 200:
            report.add(name, "fail", f"HTTP {status}: {data}")
            continue
        code = (data or {}).get("code")
        if code != expect:
            report.add(name, "fail", f"code={code} expected {expect}")
        else:
            report.add(name, "pass", f"code={code}")


def _run_built_resolve(report: SmokeReport, base: str, token: str | None) -> None:
    name = "built.resolve-codes(대소읍)"
    status, data = _get_json(
        base,
        "/api/built/regions/resolve-codes",
        token=token,
        params={
            "addr1": "충청북도",
            "addr2": "음성군",
            "leaf": "대소읍",
            "asset_type": "commercial",
        },
    )
    if status == 503:
        report.add(name, "skip", "built DB not configured")
        return
    if status != 200:
        report.add(name, "fail", f"HTTP {status}: {data}")
        return
    codes: list[str] = []
    _collect_codes(data, codes)
    err = _assert_no_historical(codes, context=name)
    if err:
        report.add(name, "fail", err)
        return
    if CANON_EUP not in codes and not any(c.startswith(CANON_EUP) for c in codes):
        report.add(name, "fail", f"canonical eup missing in {codes[:8]}")
        return
    report.add(name, "pass", f"codes={len(codes)}")


def _run_built_scope(report: SmokeReport, base: str, token: str | None) -> None:
    name = "built.filters.scope(canon eup)"
    status, data = _get_json(
        base,
        "/api/built/filters/scope",
        token=token,
        params={
            "asset_type": "commercial",
            "region_codes": CANON_EUP,
            "region_code_level": "eupmyeondong",
            "window_years": 3,
        },
    )
    if status == 503:
        report.add(name, "skip", "built DB not configured")
        return
    if status != 200:
        report.add(name, "fail", f"HTTP {status}: {data}")
        return
    total = int((data or {}).get("total") or 0)
    if total < 1:
        report.add(name, "fail", f"total={total} (ledger expand regression?)")
    else:
        report.add(name, "pass", f"total={total}")


def _run_collective_resolve(report: SmokeReport, base: str, token: str | None) -> None:
    name = "collective.resolve-codes(대소읍)"
    status, data = _get_json(
        base,
        "/api/collective/regions/resolve-codes",
        token=token,
        params={"addr1": "충청북도", "addr2": "음성군", "leaf": "대소읍"},
    )
    if status == 503:
        report.add(name, "skip", "collective DB not configured")
        return
    if status != 200:
        report.add(name, "fail", f"HTTP {status}: {data}")
        return
    codes: list[str] = []
    _collect_codes(data, codes)
    err = _assert_no_historical(codes, context=name)
    report.add(name, "pass" if not err else "fail", err or f"codes={len(codes)}")


def _run_profile(report: SmokeReport, base: str, token: str | None) -> None:
    name = "regional-profile(eup canon)"
    status, data = _get_json(
        base,
        "/api/regional-profile",
        token=token,
        params={
            "region_level": "eupmyeondong",
            "region_code": CANON_EUP,
            "profile_version": "v2.1-national",
            "window_years": 3,
        },
    )
    if status in (404, 503):
        report.add(name, "skip", f"HTTP {status}")
        return
    if status != 200:
        report.add(name, "fail", f"HTTP {status}: {data}")
        return
    meta = (data or {}).get("meta") or {}
    rc = meta.get("region_code")
    if rc != CANON_EUP:
        report.add(name, "fail", f"meta.region_code={rc}")
    else:
        report.add(name, "pass", f"features={meta.get('feature_count')}")


def _run_profile_twins(report: SmokeReport, base: str, token: str | None) -> None:
    """Regional Profile Twin (algo 21) only."""
    name = "regional-profile.twins-beop(canon)"
    status, data = _get_json(
        base,
        f"/api/regional-profile/twins-beop/{CANON_RI}",
        token=token,
        params={"top_k": 3, "profile_version": "v2.1-national", "window_years": 3},
    )
    if status == 404:
        report.add(name, "skip", "no twin batch/anchor")
        return
    if status != 200:
        report.add(name, "fail", f"HTTP {status}: {data}")
        return
    codes: list[str] = []
    _collect_codes(data, codes)
    err = _assert_no_historical(codes, context=name)
    algo = (data or {}).get("algorithm_version")
    if algo not in (None, 21):
        report.add(name, "fail", f"algorithm_version={algo}")
    elif err:
        report.add(name, "fail", err)
    else:
        n = len((data or {}).get("neighbors") or [])
        report.add(name, "pass", f"neighbors={n}")

    name_eup = "regional-profile.twins-eup(canon)"
    status, data = _get_json(
        base,
        f"/api/regional-profile/twins/{CANON_EUP}",
        token=token,
        params={"top_k": 3, "profile_version": "v2.1-national", "window_years": 3},
    )
    if status == 404:
        report.add(name_eup, "skip", "no eup twin batch")
        return
    if status != 200:
        report.add(name_eup, "fail", f"HTTP {status}: {data}")
        return
    codes = []
    _collect_codes(data, codes)
    err = _assert_no_historical(codes, context=name_eup)
    report.add(name_eup, "pass" if not err else "fail", err or "OK")


def _run_map_config(report: SmokeReport, base: str, token: str | None) -> None:
    name = "map.config"
    status, data = _get_json(base, "/api/map/config", token=token)
    if status != 200:
        report.add(name, "fail", f"HTTP {status}: {data}")
        return
    report.add(
        name,
        "pass",
        f"vworld={data.get('vworld_configured')} neighbor_edges={data.get('neighbor_edge_count')}",
    )


def _run_region_search(report: SmokeReport, base: str, token: str | None) -> None:
    name = "free.regions.search(대소읍)"
    status, data = _get_json(
        base,
        "/api/free/regions",
        token=token,
        params={"search": "대소읍", "limit": 20},
    )
    if status != 200:
        report.add(name, "fail", f"HTTP {status}: {data}")
        return
    items = data if isinstance(data, list) else []
    eup_codes = {str(it.get("eupmyeondong_code", "")).strip() for it in items}
    if HIST_EUP in eup_codes:
        report.add(name, "fail", f"historical eup {HIST_EUP} in search results")
        return
    if CANON_EUP not in eup_codes and items:
        report.add(name, "fail", f"canonical eup missing; got {sorted(eup_codes)[:5]}")
        return
    report.add(name, "pass", f"rows={len(items)}")


def _run_health(report: SmokeReport, base: str, token: str | None) -> None:
    name = "health"
    status, data = _get_json(base, "/health", token=token)
    if status != 200:
        report.add(name, "fail", f"HTTP {status}")
    else:
        report.add(name, "pass", str(data.get("status") if isinstance(data, dict) else "ok"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Region-code deploy smoke (D-028)")
    ap.add_argument("--base-url", default=os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:8000"))
    ap.add_argument("--token", default=os.environ.get("API_TOKEN", ""))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    token = (args.token or "").strip() or None
    report = SmokeReport(base_url=args.base_url.rstrip("/"))

    _run_health(report, report.base_url, token)
    _run_land_free_v2(report, report.base_url, token)
    _run_land_free_v2_hist_input(report, report.base_url, token)
    _run_upper_stats(report, report.base_url, token)
    _run_built_lookup(report, report.base_url, token)
    _run_built_resolve(report, report.base_url, token)
    _run_built_scope(report, report.base_url, token)
    _run_collective_resolve(report, report.base_url, token)
    _run_profile(report, report.base_url, token)
    _run_profile_twins(report, report.base_url, token)
    _run_map_config(report, report.base_url, token)
    _run_region_search(report, report.base_url, token)

    status = "PASS" if report.passed else "FAIL"
    payload = {
        "status": status,
        "base_url": report.base_url,
        "checks": [
            {"name": r.name, "status": r.status, "detail": r.detail} for r in report.results
        ],
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        text_out = "\n".join([
            f"# Region-code deploy smoke - **{status}**",
            f"- base_url: {report.base_url}",
            *[
                f"- [{({'pass': 'OK', 'fail': 'FAIL', 'skip': 'SKIP'}[r.status])}] {r.name}"
                + (f" - {r.detail}" if r.detail else "")
                for r in report.results
            ],
        ]) + "\n"
        try:
            print(text_out)
        except UnicodeEncodeError:
            sys.stdout.buffer.write(text_out.encode("utf-8", errors="replace"))

    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
