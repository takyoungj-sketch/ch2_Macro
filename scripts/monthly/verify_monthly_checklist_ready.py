#!/usr/bin/env python3
"""월간 체크리스트 사전 점검 — 러너·캐시·문서 경로 존재 여부 (실제 cycle 실행 아님)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

CHECKS: list[tuple[str, Path]] = [
    ("land CSV cycle", REPO / "scripts/monthly/run_land_cycle_csv.py"),
    ("built CSV cycle", REPO / "scripts/monthly/run_built_cycle_csv.py"),
    ("built freeze verify", REPO / "scripts/monthly/verify_built_enrichment_freeze.py"),
    ("collective CSV cycle", REPO / "scripts/monthly/run_collective_cycle_csv.py"),
    ("checklist doc", REPO / "docs/MONTHLY_UPDATE_CHECKLIST.md"),
    ("land SOP", REPO / "docs/MONTHLY_UPDATE_SOP.md"),
    ("built SOP", REPO / "docs/BUILT_MONTHLY_UPDATE_SOP.md"),
    ("collective SOP", REPO / "docs/COLLECTIVE_MONTHLY_UPDATE_SOP.md"),
    ("pipeline cache helper", REPO / "pipeline/run_pipeline.py"),
    ("integrity script", REPO / "pipeline/verify_monthly_integrity.py"),
]


def _land_has_cache_clear(path: Path) -> bool:
    src = path.read_text(encoding="utf-8")
    return "_truncate_paid_caches" in src and "skip-cache-clear" in src and "analysis_cache" in src


def main() -> int:
    ok = True
    print("=== monthly checklist preflight ===")
    for label, path in CHECKS:
        exists = path.is_file()
        mark = "OK" if exists else "MISSING"
        if not exists:
            ok = False
        print(f"[{mark}] {label}: {path.relative_to(REPO)}")

    land = REPO / "scripts/monthly/run_land_cycle_csv.py"
    if land.is_file():
        cache_ok = _land_has_cache_clear(land)
        print(f"[{'OK' if cache_ok else 'FAIL'}] H2 land CSV ends with analysis cache TRUNCATE")
        if not cache_ok:
            ok = False

    built = REPO / "scripts/monthly/run_built_cycle_csv.py"
    coll = REPO / "scripts/monthly/run_collective_cycle_csv.py"
    if built.is_file():
        bsrc = built.read_text(encoding="utf-8")
        skip_ok = "skip-enrich" in bsrc and "should_run_enrich" in bsrc
        mart_ok = "built_transaction_enrichment" not in (
            REPO / "pipeline/built/build_scope_stats.py"
        ).read_text(encoding="utf-8")
        print(f"[{'OK' if skip_ok else 'FAIL'}] built CSV skip-enrich default (opt-in --enrich)")
        print(f"[{'OK' if mart_ok else 'FAIL'}] built_scope_stats is ledger-only")
        if not skip_ok or not mart_ok:
            ok = False
    if coll.is_file():
        csrc = coll.read_text(encoding="utf-8")
        c_ok = "enrich-new-keys" in csrc and "should_run_enrich" in csrc
        print(f"[{'OK' if c_ok else 'FAIL'}] collective CSV skip-enrich default (opt-in --enrich-new-keys)")
        if not c_ok:
            ok = False
    if land.is_file():
        src = land.read_text(encoding="utf-8")
        win_ok = '"3,5,7"' in src or "'3,5,7'" in src
        print(f"[{'OK' if win_ok else 'FAIL'}] land V2 windows include 3,5,7")
        if not win_ok:
            ok = False

    print("=== result:", "PASS" if ok else "FAIL", "===")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
