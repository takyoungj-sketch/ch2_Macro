#!/usr/bin/env python3
"""쌍둥이 로직 보강 — R0 / R1 / T1 / RT 4축 벤치.

R0  Local
R1  Local + 지역특성
T1  Local + Twin (built_commercial 등)
RT  Local + Twin + 지역특성

예:
  cd pipeline
  python bench_region_twin_axes.py \\
    --fixture fixtures/twin_bench_commercial_chungbuk12.json \\
    --reuse-r0r1 ../logs/twin_lab/pilot-commercial-r0r1.raw.json
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

from app.built.db import get_built_engine  # noqa: E402
from app.built.schemas import RegressionSelectionRequest  # noqa: E402
from app.db import engine as land_engine  # noqa: E402
from app.recommendation.stages import run_recommendation  # noqa: E402
from collective.db_utils import get_collective_engine  # noqa: E402
from twin_lab.mart import (  # noqa: E402
    _delta_pp,
    _kpi_for_version,
    _kpis_by_sample_group,
    _lift_rel,
    _median,
)

# twin fetch helpers from existing bench
from bench_twin_built_recommend_lift import (  # noqa: E402
    _best_pool_lift,
    _fetch_twin_neighbors,
    _gate_pass_rate,
)

FIXTURE_DEFAULT = Path(__file__).resolve().parent / "fixtures" / "twin_bench_commercial_chungbuk12.json"
AXES = ("r0", "r1", "t1", "rt")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_local_case(
    built_conn,
    case: dict[str, Any],
    defaults: dict[str, Any],
    *,
    include_region: bool,
    region_tier: str = "full",
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
        region_feature_tier=region_tier if region_tier in ("price", "full") else "full",
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
            "error": str(exc),
        }
    s1 = resp.stage1
    return {
        "case_id": case["case_id"],
        "label": case.get("label"),
        "sample_group": case.get("sample_group") or "pilot",
        "region_codes": case["region_codes"],
        "admin_level": admin_level,
        "stage1": {
            "selection_n": s1.selection_n,
            "fit_n": s1.fit_n,
            "cv_mape": s1.satisfaction.cv_mape,
            "primary_blocks": list(s1.primary.blocks),
            "response_scale": s1.primary.response_scale,
            "candidate_pool": list(s1.candidate_pool or []),
        },
    }


def _run_twin_case(
    built_conn,
    coll_conn,
    land_conn,
    case: dict[str, Any],
    defaults: dict[str, Any],
    *,
    twin_profile: str,
    include_region: bool,
    lift_delta: float,
    region_tier: str = "full",
) -> dict[str, Any]:
    admin_level = case["admin_level"]
    anchor = case["region_codes"][0]
    neighbors, twin_meta = _fetch_twin_neighbors(
        coll_conn,
        land_conn,
        admin_level=admin_level,
        anchor_code=anchor,
        profile_version=defaults["profile_version"],
        window_years=defaults["window_years"],
        top_k=defaults.get("twin_top_k", 5),
        scope_eup=defaults.get("twin_scope_eup", "region"),
        twin_profile=twin_profile,
    )
    req = RegressionSelectionRequest(
        asset_type=defaults["asset_type"],
        admin_level=admin_level,
        region_codes=list(case["region_codes"]),
        region_code_level=admin_level,
        contract_year_from=defaults.get("contract_year_from"),
        contract_year_to=defaults.get("contract_year_to"),
        profile_version=defaults["profile_version"],
        profile_window_years=defaults["window_years"],
        profile_twin_neighbors=neighbors,
        run_stage2=True,
        include_region_features=include_region,
        region_feature_tier=region_tier if region_tier in ("price", "full") else "full",
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
            "error": str(exc),
            "twin_meta": twin_meta,
        }

    stage1 = resp.stage1
    stage2 = resp.stage2
    lift = _best_pool_lift(stage1, stage2)
    lift["lift_hit"] = lift["cv_lift_pp"] is not None and lift["cv_lift_pp"] > lift_delta
    twin_rows = [
        {
            "region_code": n.get("region_code") or n.get("neighbor_code"),
            "label": n.get("label") or n.get("region_label") or n.get("name"),
            "similarity": n.get("similarity") or n.get("score"),
        }
        for n in neighbors[: int(defaults.get("twin_top_k") or 5)]
    ]
    pool_rows: list[dict[str, Any]] = []
    if stage2 and stage2.pools:
        v0_cv = stage1.satisfaction.cv_mape
        for p in stage2.pools:
            if p.cv_mape is None:
                continue
            pool_rows.append(
                {
                    "candidate_id": p.candidate_id,
                    "cv_mape": p.cv_mape,
                    "n": p.n,
                    "cv_lift_pp": None if v0_cv is None else round(float(v0_cv) - float(p.cv_mape), 2),
                    "blocks": list(p.blocks or []),
                }
            )
    return {
        "case_id": case["case_id"],
        "label": case.get("label"),
        "sample_group": case.get("sample_group") or "pilot",
        "region_codes": case["region_codes"],
        "admin_level": admin_level,
        "twins": twin_rows,
        "twin_meta": twin_meta,
        "stage1": {
            "selection_n": stage1.selection_n,
            "fit_n": stage1.fit_n,
            "cv_mape": stage1.satisfaction.cv_mape,
            "primary_blocks": list(stage1.primary.blocks),
            "response_scale": stage1.primary.response_scale,
            "candidate_pool": list(stage1.candidate_pool or []),
        },
        "stage2": {
            "ran": bool(stage2 and stage2.ran),
            "decision": stage2.decision if stage2 else None,
            "twin_gate_pass_rate": _gate_pass_rate(stage2),
            "pools": pool_rows,
            "region_candidate_blocks": list(getattr(stage2, "region_candidate_blocks", None) or [])
            if stage2
            else [],
            "region_feature_tier": getattr(stage2, "region_feature_tier", None) if stage2 else None,
        },
        "lift": lift,
    }


def _axis_cv(case: dict[str, Any]) -> float | None:
    if "error" in case:
        return None
    lift = case.get("lift") or {}
    if lift.get("best_pool_cv_mape") is not None:
        return float(lift["best_pool_cv_mape"])
    s1 = case.get("stage1") or {}
    cv = s1.get("cv_mape")
    return float(cv) if cv is not None else None


def _axis_version(
    case: dict[str, Any],
    *,
    r0_cv: float | None,
    key: str,
    region_tier: str | None,
) -> dict[str, Any]:
    if "error" in case:
        return {"error": case["error"], "cv_mape": None}
    cv = _axis_cv(case)
    s1 = case.get("stage1") or {}
    s2 = case.get("stage2") or {}
    lift = case.get("lift") or {}
    rel = _lift_rel(r0_cv, cv) if key != "r0" else None
    chosen_blocks = list(lift.get("best_pool_blocks") or s1.get("primary_blocks") or [])
    cand_pool = list(s1.get("candidate_pool") or [])
    # Stage2: explicit candidate list > union of researched pool blocks > stage1 pool
    stage2_cand = list(s2.get("region_candidate_blocks") or [])
    stage2_region: list[str] = []
    for p in s2.get("pools") or []:
        for b in p.get("blocks") or []:
            if str(b).startswith("region_") and b not in stage2_region:
                stage2_region.append(b)
    region_candidate = (
        stage2_cand
        or [b for b in cand_pool if str(b).startswith("region_")]
        or stage2_region
    )
    region_selected = [b for b in chosen_blocks if str(b).startswith("region_")]
    n_local = s1.get("fit_n") or s1.get("selection_n")
    n_pool = lift.get("best_pool_n")
    twins = case.get("twins") or []
    tier = s2.get("region_feature_tier") or region_tier
    return {
        "cv_mape": cv,
        "n": n_pool or n_local,
        "n_local": n_local,
        "n_pool": n_pool,
        "n_twins": len(twins),
        "blocks": chosen_blocks,
        "response_scale": s1.get("response_scale"),
        "delta_pp": _delta_pp(r0_cv, cv) if key != "r0" else None,
        "lift_rel": rel,
        "hit": bool(rel is not None and rel >= 0.05) if key != "r0" else None,
        "twins": twins,
        "pool_id": lift.get("best_pool_id"),
        "stage2_ran": bool(s2.get("ran")),
        "candidate_pool": cand_pool,
        "region_blocks_in_pool": region_candidate,  # compat alias
        "region_blocks_candidate": region_candidate,
        "region_blocks_selected": region_selected,
        "region_tier": tier if (region_candidate or region_selected or key in {"r1", "rt"}) else None,
    }


def _lift_t1_to_rt(t1_cv: float | None, rt_cv: float | None) -> float | None:
    if t1_cv is None or rt_cv is None or t1_cv == 0:
        return None
    return round((float(t1_cv) - float(rt_cv)) / float(t1_cv), 4)


def _region_adoption_summary(regions: list[dict[str, Any]]) -> dict[str, Any]:
    """RT에서 블록별 채택 횟수 + RT가 T1보다 나을 때 채택 패턴."""
    counts: dict[str, int] = {}
    when_rt_better: dict[str, int] = {}
    rt_better_n = 0
    rt_ok = 0
    for r in regions:
        vs = r.get("versions") or {}
        rt = vs.get("rt") or {}
        t1 = vs.get("t1") or {}
        if rt.get("cv_mape") is None:
            continue
        rt_ok += 1
        sel = list(rt.get("region_blocks_selected") or [])
        for b in sel:
            counts[b] = counts.get(b, 0) + 1
        t1cv, rtcv = t1.get("cv_mape"), rt.get("cv_mape")
        if t1cv is not None and rtcv is not None and rtcv < t1cv - 1e-9:
            rt_better_n += 1
            for b in sel:
                when_rt_better[b] = when_rt_better.get(b, 0) + 1
    return {
        "rt_cases_ok": rt_ok,
        "rt_better_than_t1": rt_better_n,
        "selected_counts": dict(sorted(counts.items(), key=lambda x: (-x[1], x[0]))),
        "selected_when_rt_beats_t1": dict(
            sorted(when_rt_better.items(), key=lambda x: (-x[1], x[0]))
        ),
    }


def _write_comparison_csv(mart: dict[str, Any], path: Path) -> None:
    """R0/T1/RT + region 채택·식 블록 비교표."""
    rows = mart.get("regions") or []
    headers = [
        "case_id",
        "region_label",
        "sample_group",
        "winner",
        "r0_cv",
        "t1_cv",
        "rt_cv",
        "rt_lift_vs_r0",
        "rt_lift_vs_t1",
        "region_selected",
        "rt_blocks",
        "pool_id",
        "n_local",
        "n_pool",
        "n_twins",
        "region_tier",
    ]
    lines = [",".join(headers)]
    for r in rows:
        vs = r.get("versions") or {}
        r0, t1, rt = vs.get("r0") or {}, vs.get("t1") or {}, vs.get("rt") or {}
        sel = ";".join(rt.get("region_blocks_selected") or [])
        blocks = "+".join(rt.get("blocks") or [])
        label = (r.get("region_label") or "").replace('"', "'")
        cells = [
            r.get("case_id") or "",
            f'"{label}"',
            r.get("sample_group") or "",
            r.get("winner") or "",
            "" if r0.get("cv_mape") is None else str(r0.get("cv_mape")),
            "" if t1.get("cv_mape") is None else str(t1.get("cv_mape")),
            "" if rt.get("cv_mape") is None else str(rt.get("cv_mape")),
            "" if rt.get("lift_rel") is None else str(rt.get("lift_rel")),
            ""
            if _lift_t1_to_rt(t1.get("cv_mape"), rt.get("cv_mape")) is None
            else str(_lift_t1_to_rt(t1.get("cv_mape"), rt.get("cv_mape"))),
            f'"{sel}"',
            f'"{blocks}"',
            rt.get("pool_id") or "",
            "" if rt.get("n_local") is None else str(rt.get("n_local")),
            "" if rt.get("n_pool") is None else str(rt.get("n_pool")),
            "" if rt.get("n_twins") is None else str(rt.get("n_twins")),
            rt.get("region_tier") or mart.get("region_feature_tier") or "",
        ]
        lines.append(",".join(cells))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\ufeff" + "\n".join(lines) + "\n", encoding="utf-8")


def _to_lab_mart(report: dict[str, Any], *, experiment_id: str) -> dict[str, Any]:
    defaults = report.get("defaults") or {}
    profiles = report.get("profiles") or {}
    region_tier = (report.get("meta") or {}).get("region_feature_tier") or "full"
    by_axis = {ax: {c["case_id"]: c for c in (profiles.get(ax) or {}).get("cases") or []} for ax in AXES}
    present = [ax for ax in AXES if by_axis[ax]]
    case_ids = sorted(set().union(*[set(by_axis[ax]) for ax in present])) if present else []

    regions: list[dict[str, Any]] = []
    for cid in case_ids:
        base = next((by_axis[ax].get(cid) for ax in AXES if by_axis[ax].get(cid)), {}) or {}
        r0_cv = _axis_cv(by_axis["r0"].get(cid) or {})
        versions = {
            ax: _axis_version(
                by_axis[ax][cid],
                r0_cv=r0_cv,
                key=ax,
                region_tier=region_tier,
            )
            for ax in AXES
            if cid in by_axis[ax]
        }
        # 판정 승자: R0/T1/RT only (R1은 참고·제외)
        judge_keys = [k for k in ("r0", "t1", "rt") if versions.get(k, {}).get("cv_mape") is not None]
        winner = min(judge_keys, key=lambda k: versions[k]["cv_mape"]) if judge_keys else None

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

    version_keys = [ax for ax in AXES if any((r.get("versions") or {}).get(ax) for r in regions)]
    if not version_keys:
        version_keys = list(AXES)
    kpis = {vk: _kpi_for_version(regions, vk, hit_threshold_rel=0.05) for vk in version_keys}
    kpis_by_group = _kpis_by_sample_group(regions, version_keys, hit_threshold_rel=0.05)
    adoption = _region_adoption_summary(regions)

    rt_pool = sum(
        1
        for r in regions
        if (r["versions"].get("rt") or {}).get("cv_mape") is not None
        and (r["versions"].get("rt") or {}).get("region_blocks_candidate")
    )
    rt_selected = adoption["rt_cases_ok"] and sum(
        1
        for r in regions
        if (r["versions"].get("rt") or {}).get("region_blocks_selected")
    )
    rt_ok = adoption["rt_cases_ok"]

    # T1→RT median lift
    lifts_t1_rt = []
    for r in regions:
        t1 = (r["versions"].get("t1") or {}).get("cv_mape")
        rt = (r["versions"].get("rt") or {}).get("cv_mape")
        lr = _lift_t1_to_rt(t1, rt)
        if lr is not None:
            lifts_t1_rt.append(lr)
    median_lift_t1_rt = _median(lifts_t1_rt) if lifts_t1_rt else None

    tier_label = "price" if region_tier == "price" else "full"
    return {
        "schema_version": "1.1",
        "experiment_id": experiment_id,
        "asset_type": defaults.get("asset_type") or "commercial",
        "period_years": 5,
        "contract_year_from": defaults.get("contract_year_from"),
        "contract_year_to": defaults.get("contract_year_to"),
        "region_scope": defaults.get("twin_scope_eup") or "region",
        "anchor_basin": "chungcheong",
        "profile_version": defaults.get("profile_version"),
        "window_years": defaults.get("window_years"),
        "pool_variant": "engine_best",
        "hit_threshold_rel": 0.05,
        "region_feature_tier": tier_label,
        "versions": version_keys,
        "v2_twin_profile": report.get("meta", {}).get("twin_profile") or "built_commercial",
        "notes": (
            "판정축=R0/T1/RT (R1=참고·식별불가). "
            f"region_tier={tier_label}. "
            f"RT region 후보 {rt_pool}/{rt_ok}, 식 채택 {rt_selected}/{rt_ok}. "
            "R1≡R0는 효과없음이 아니라 상수 식별불가."
        ),
        "generated_at": report.get("generated_at"),
        "source": "bench_region_twin_axes",
        "kpis": kpis,
        "kpis_by_sample_group": kpis_by_group,
        "region_adoption": adoption,
        "regions": regions,
        "meta_summary": {
            "region_feature_tier": tier_label,
            "rt_cases_with_region_candidate": rt_pool,
            "rt_cases_with_region_selected": rt_selected,
            "rt_cases_ok": rt_ok,
            "median_lift_t1": (kpis.get("t1") or {}).get("median_lift_rel"),
            "median_lift_rt": (kpis.get("rt") or {}).get("median_lift_rel"),
            "median_lift_t1_to_rt": median_lift_t1_rt,
            "median_cv_r0": (kpis.get("r0") or {}).get("median_cv_mape"),
            "median_cv_t1": (kpis.get("t1") or {}).get("median_cv_mape"),
            "median_cv_rt": (kpis.get("rt") or {}).get("median_cv_mape"),
            "region_selected_counts": adoption.get("selected_counts"),
        },
    }


def main() -> None:
    p = argparse.ArgumentParser(description="R0/R1/T1/RT four-axis bench")
    p.add_argument("--fixture", type=Path, default=FIXTURE_DEFAULT)
    p.add_argument("--case", action="append", default=[])
    p.add_argument("--twin-profile", default="built_commercial")
    p.add_argument(
        "--region-tier",
        default="price",
        choices=["price", "full"],
        help="RT/R1 region candidate set (default: price = 가격수준만)",
    )
    p.add_argument("--reuse-r0r1", type=Path, default=None, help="prior bench_region_r0r1 raw JSON")
    p.add_argument("--reuse-raw", type=Path, default=None, help="reuse axes from prior four-axis raw JSON")
    p.add_argument(
        "--force-axes",
        default="",
        help="comma axes to re-run even when present in --reuse-raw (e.g. rt)",
    )
    p.add_argument("--experiment-id", default="pilot-commercial-r0-t1-rt-price")
    p.add_argument(
        "--lab-out",
        type=Path,
        default=REPO / "logs" / "twin_lab" / "pilot-commercial-r0-t1-rt-price.json",
    )
    p.add_argument("--out", type=Path, default=None)
    p.add_argument(
        "--skip-axes",
        default="r1",
        help="comma: r0,r1,t1,rt (default skips r1 — 참고축)",
    )
    p.add_argument("--csv-out", type=Path, default=None, help="comparison CSV path")
    args = p.parse_args()

    fixture = _load_json(args.fixture)
    defaults = fixture["defaults"]
    cases = fixture["cases"]
    if args.case:
        want = set(args.case)
        cases = [c for c in cases if c["case_id"] in want]
    lift_delta = float(defaults.get("lift_delta_pp") or 0.5)
    skip = {x.strip() for x in args.skip_axes.split(",") if x.strip()}
    force = {x.strip() for x in args.force_axes.split(",") if x.strip()}
    region_tier = args.region_tier

    profiles: dict[str, Any] = {ax: {"cases": []} for ax in AXES}

    def _reuse_axes(prior_path: Path, axes: tuple[str, ...]) -> None:
        prior = _load_json(prior_path)
        for ax in axes:
            if ax in skip or ax in force:
                continue
            pcases = (prior.get("profiles") or {}).get(ax, {}).get("cases") or []
            if args.case:
                want = set(args.case)
                pcases = [c for c in pcases if c["case_id"] in want]
            if not pcases:
                continue
            profiles[ax] = {"cases": pcases}
            print(f"reuse {ax}: {len(pcases)} cases from {prior_path.name}", flush=True)
            skip.add(ax)

    if args.reuse_raw and args.reuse_raw.is_file():
        _reuse_axes(args.reuse_raw, AXES)
    elif args.reuse_r0r1 and args.reuse_r0r1.is_file():
        _reuse_axes(args.reuse_r0r1, ("r0", "r1"))

    built_eng = get_built_engine()
    coll_eng = get_collective_engine()

    with built_eng.connect() as built_conn, coll_eng.connect() as coll_conn, land_engine.connect() as land_conn:
        for ax, include in (("r0", False), ("r1", True)):
            if ax in skip:
                continue
            print(f"axis={ax} region_tier={region_tier}", flush=True)
            out = []
            for case in cases:
                print(f"  [{ax}] {case['case_id']} …", flush=True)
                out.append(
                    _run_local_case(
                        built_conn,
                        case,
                        defaults,
                        include_region=include,
                        region_tier=region_tier,
                    )
                )
            profiles[ax] = {"cases": out}

        for ax, include in (("t1", False), ("rt", True)):
            if ax in skip:
                continue
            print(
                f"axis={ax} twin={args.twin_profile} region={include} tier={region_tier}",
                flush=True,
            )
            out = []
            for case in cases:
                print(f"  [{ax}] {case['case_id']} …", flush=True)
                out.append(
                    _run_twin_case(
                        built_conn,
                        coll_conn,
                        land_conn,
                        case,
                        defaults,
                        twin_profile=args.twin_profile,
                        include_region=include,
                        lift_delta=lift_delta,
                        region_tier=region_tier,
                    )
                )
            profiles[ax] = {"cases": out}

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "defaults": defaults,
        "profiles": profiles,
        "meta": {
            "twin_profile": args.twin_profile,
            "fixture": args.fixture.name,
            "axes": [ax for ax in AXES if profiles[ax].get("cases")],
            "region_feature_tier": region_tier,
        },
    }
    raw_path = args.out or (REPO / "logs" / "twin_lab" / f"{args.experiment_id}.raw.json")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {raw_path}")

    mart = _to_lab_mart(report, experiment_id=args.experiment_id)
    args.lab_out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(mart, ensure_ascii=False, indent=2, default=str)
    args.lab_out.write_text(payload, encoding="utf-8")
    (REPO / "logs" / "twin_lab" / f"{args.experiment_id}.json").write_text(payload, encoding="utf-8")
    csv_path = args.csv_out or (REPO / "logs" / "twin_lab" / f"{args.experiment_id}.csv")
    _write_comparison_csv(mart, csv_path)
    print(f"Wrote Lab mart {args.lab_out}")
    print(f"Wrote CSV {csv_path}")
    print("summary:", json.dumps(mart.get("meta_summary"), ensure_ascii=False))
    print("adoption:", json.dumps(mart.get("region_adoption"), ensure_ascii=False))
    print(
        "kpis:",
        json.dumps({k: v.get("median_lift_rel") for k, v in mart["kpis"].items()}, ensure_ascii=False),
    )


if __name__ == "__main__":
    main()
