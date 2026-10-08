#!/usr/bin/env python3
"""쌍둥이 로직 보강 — R0(Local) vs R1(Local+지역특성) 스모크 벤치.

예:
  cd pipeline
  python bench_region_r0r1.py --fixture fixtures/twin_bench_commercial_chungbuk12.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "pipeline"))

from sqlalchemy import text  # noqa: E402

from app.built.db import get_built_engine  # noqa: E402
from app.built.schemas import RegressionSelectionRequest  # noqa: E402
from app.recommendation.stages import run_recommendation  # noqa: E402
from twin_lab.mart import _delta_pp, _kpi_for_version, _kpis_by_sample_group, _lift_rel  # noqa: E402

FIXTURE_DEFAULT = Path(__file__).resolve().parent / "fixtures" / "twin_bench_commercial_chungbuk12.json"


def _load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_case(
    built_conn,
    case: dict[str, Any],
    defaults: dict[str, Any],
    *,
    include_region: bool,
) -> dict[str, Any]:
    admin_level = case["admin_level"]
    req = RegressionSelectionRequest(
        asset_type=defaults["asset_type"],
        admin_level=admin_level,
        region_codes=list(case["region_codes"]),
        region_code_level=admin_level,
        contract_year_from=defaults.get("contract_year_from"),
        contract_year_to=defaults.get("contract_year_to"),
        profile_version=defaults.get("profile_version") or "v2.1-national",
        profile_window_years=defaults.get("window_years") or 3,
        run_stage2=False,
        include_region_features=include_region,
    )
    try:
        resp = run_recommendation(built_conn, req)
    except ValueError as exc:
        return {
            "case_id": case["case_id"],
            "label": case.get("label"),
            "sample_group": case.get("sample_group"),
            "region_codes": case["region_codes"],
            "admin_level": admin_level,
            "include_region_features": include_region,
            "error": str(exc),
        }
    s1 = resp.stage1
    return {
        "case_id": case["case_id"],
        "label": case.get("label"),
        "sample_group": case.get("sample_group") or "pilot",
        "region_codes": case["region_codes"],
        "admin_level": admin_level,
        "include_region_features": include_region,
        "stage1": {
            "selection_n": s1.selection_n,
            "fit_n": s1.fit_n,
            "cv_mape": s1.satisfaction.cv_mape,
            "primary_blocks": list(s1.primary.blocks),
            "response_scale": s1.primary.response_scale,
            "candidate_pool": list(s1.candidate_pool or []),
        },
    }


def _to_lab_mart(report: dict[str, Any], *, experiment_id: str) -> dict[str, Any]:
    defaults = report.get("defaults") or {}
    r0_cases = {c["case_id"]: c for c in (report.get("profiles") or {}).get("r0", {}).get("cases") or []}
    r1_cases = {c["case_id"]: c for c in (report.get("profiles") or {}).get("r1", {}).get("cases") or []}
    regions: list[dict[str, Any]] = []
    for cid in sorted(set(r0_cases) | set(r1_cases)):
        c0 = r0_cases.get(cid) or {}
        c1 = r1_cases.get(cid) or {}
        base = c0 or c1
        s0 = (c0.get("stage1") or {}) if "error" not in c0 else {}
        s1 = (c1.get("stage1") or {}) if "error" not in c1 else {}
        r0_cv = s0.get("cv_mape")
        r1_cv = s1.get("cv_mape")
        versions: dict[str, Any] = {
            "r0": {
                "cv_mape": r0_cv,
                "n": s0.get("fit_n") or s0.get("selection_n"),
                "blocks": s0.get("primary_blocks"),
                "response_scale": s0.get("response_scale"),
                "error": c0.get("error"),
            },
            "r1": {
                "cv_mape": r1_cv,
                "n": s1.get("fit_n") or s1.get("selection_n"),
                "blocks": s1.get("primary_blocks"),
                "response_scale": s1.get("response_scale"),
                "delta_pp": _delta_pp(r0_cv, r1_cv),
                "lift_rel": _lift_rel(r0_cv, r1_cv),
                "hit": bool((_lift_rel(r0_cv, r1_cv) or -1) >= 0.05),
                "error": c1.get("error"),
                "candidate_pool": s1.get("candidate_pool"),
            },
        }
        # Lab Overview 호환: v0=r0, v1 unused, v2=r1 로도 노출
        versions["v0"] = {"cv_mape": r0_cv, "n": versions["r0"]["n"], "blocks": versions["r0"]["blocks"]}
        versions["v2"] = {
            "cv_mape": r1_cv,
            "n": versions["r1"]["n"],
            "blocks": versions["r1"]["blocks"],
            "lift_rel": versions["r1"]["lift_rel"],
            "delta_pp": versions["r1"]["delta_pp"],
            "hit": versions["r1"]["hit"],
            "error": versions["r1"].get("error"),
        }
        winner = None
        if r0_cv is not None and r1_cv is not None:
            winner = "r1" if r1_cv < r0_cv else "r0"
        regions.append(
            {
                "case_id": cid,
                "region_code": (base.get("region_codes") or [None])[0],
                "region_codes": base.get("region_codes") or [],
                "region_label": base.get("label") or cid,
                "admin_level": base.get("admin_level"),
                "sample_group": base.get("sample_group") or "pilot",
                "versions": versions,
                "winner": winner,
            }
        )

    version_keys = ["v0", "v2"]  # Lab UI: Local vs Local+Region
    kpis = {vk: _kpi_for_version(regions, vk, hit_threshold_rel=0.05) for vk in version_keys}
    # r1 lift는 v2 슬롯에 있음
    kpis_by_group = _kpis_by_sample_group(regions, version_keys, hit_threshold_rel=0.05)
    return {
        "schema_version": "1.0",
        "experiment_id": experiment_id,
        "asset_type": defaults.get("asset_type") or "commercial",
        "period_years": 5,
        "contract_year_from": defaults.get("contract_year_from"),
        "contract_year_to": defaults.get("contract_year_to"),
        "region_scope": "local",
        "anchor_basin": "chungcheong",
        "profile_version": defaults.get("profile_version"),
        "window_years": defaults.get("window_years"),
        "pool_variant": "none",
        "hit_threshold_rel": 0.05,
        "versions": version_keys,
        "v1_twin_profile": None,
        "v2_twin_profile": "region_features",
        "notes": "R0=Local(v0) · R1=Local+지역특성(v2). Twin 없음. 단일 읍면동이면 region 블록은 상수로 제외될 수 있음.",
        "generated_at": report.get("generated_at"),
        "source": "bench_region_r0r1",
        "kpis": kpis,
        "kpis_by_sample_group": kpis_by_group,
        "regions": regions,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="R0 vs R1 region-features smoke bench")
    p.add_argument("--fixture", type=Path, default=FIXTURE_DEFAULT)
    p.add_argument("--case", action="append", default=[])
    p.add_argument("--experiment-id", default="pilot-commercial-r0r1")
    p.add_argument(
        "--lab-out",
        type=Path,
        default=REPO / "logs" / "twin_lab" / "pilot-commercial-r0r1.json",
    )
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    fixture = _load_fixture(args.fixture)
    defaults = fixture["defaults"]
    cases = fixture["cases"]
    if args.case:
        want = set(args.case)
        cases = [c for c in cases if c["case_id"] in want]

    eng = get_built_engine()
    profiles: dict[str, Any] = {}
    with eng.connect() as conn:
        for axis, include in (("r0", False), ("r1", True)):
            print(f"axis={axis} include_region_features={include}", flush=True)
            out_cases = []
            for case in cases:
                print(f"  [{axis}] {case['case_id']} …", flush=True)
                out_cases.append(_run_case(conn, case, defaults, include_region=include))
            profiles[axis] = {"cases": out_cases}

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "defaults": defaults,
        "profiles": profiles,
        "meta": {"axis": "r0_r1", "fixture": args.fixture.name},
    }
    raw_path = args.out or (REPO / "logs" / "twin_lab" / f"{args.experiment_id}.raw.json")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {raw_path}")

    mart = _to_lab_mart(report, experiment_id=args.experiment_id)
    args.lab_out.parent.mkdir(parents=True, exist_ok=True)
    args.lab_out.write_text(json.dumps(mart, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (REPO / "logs" / "twin_lab" / f"{args.experiment_id}.json").write_text(
        json.dumps(mart, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"Wrote Lab mart {args.lab_out}")
    print("KPI v0/v2:", json.dumps(mart["kpis"], ensure_ascii=False))


if __name__ == "__main__":
    main()
