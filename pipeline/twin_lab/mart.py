"""Bench JSON → Twin Experiment Lab mart (파일 SSOT)."""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any


def _lift_rel(v0: float | None, twin: float | None) -> float | None:
    if v0 is None or twin is None or v0 <= 0:
        return None
    return round((v0 - twin) / v0, 4)


def _delta_pp(v0: float | None, twin: float | None) -> float | None:
    if v0 is None or twin is None:
        return None
    return round(v0 - twin, 2)


def _median(xs: list[float]) -> float | None:
    if not xs:
        return None
    return round(float(statistics.median(xs)), 4)


def _kpi_for_version(
    regions: list[dict[str, Any]],
    version: str,
    *,
    hit_threshold_rel: float,
) -> dict[str, Any]:
    if version == "v0":
        mapes = [
            r["versions"]["v0"]["cv_mape"]
            for r in regions
            if r.get("versions", {}).get("v0", {}).get("cv_mape") is not None
        ]
        return {
            "n_regions": len(mapes),
            "median_cv_mape": _median(mapes),
            "mean_cv_mape": round(sum(mapes) / len(mapes), 2) if mapes else None,
            "median_lift_rel": None,
            "hit_rate": None,
            "worsened_rate": None,
        }

    lifts: list[float] = []
    mapes: list[float] = []
    hits = 0
    worsened = 0
    n = 0
    for r in regions:
        ver = r.get("versions", {}).get(version) or {}
        if ver.get("error") or ver.get("cv_mape") is None:
            continue
        n += 1
        mapes.append(float(ver["cv_mape"]))
        lr = ver.get("lift_rel")
        if lr is None:
            continue
        lifts.append(float(lr))
        if lr >= hit_threshold_rel:
            hits += 1
        if lr < 0:
            worsened += 1
    return {
        "n_regions": n,
        "median_cv_mape": _median(mapes),
        "mean_cv_mape": round(sum(mapes) / len(mapes), 2) if mapes else None,
        "median_lift_rel": _median(lifts),
        "mean_lift_rel": round(sum(lifts) / len(lifts), 4) if lifts else None,
        "hit_rate": round(hits / len(lifts), 4) if lifts else None,
        "worsened_rate": round(worsened / len(lifts), 4) if lifts else None,
        "hit_threshold_rel": hit_threshold_rel,
    }


def _kpis_by_sample_group(
    regions: list[dict[str, Any]],
    version_keys: list[str],
    *,
    hit_threshold_rel: float,
) -> dict[str, dict[str, Any]]:
    """all / dev / holdout 등 sample_group별 KPI (V3 holdout 검증용)."""
    groups: dict[str, list[dict[str, Any]]] = {"all": list(regions)}
    for r in regions:
        g = str(r.get("sample_group") or "unspecified").strip() or "unspecified"
        groups.setdefault(g, []).append(r)
    out: dict[str, dict[str, Any]] = {}
    for g, rows in sorted(groups.items(), key=lambda x: (0 if x[0] == "all" else 1, x[0])):
        out[g] = {
            vk: _kpi_for_version(rows, vk, hit_threshold_rel=hit_threshold_rel) for vk in version_keys
        }
    return out


def _winner(versions: dict[str, Any]) -> str | None:
    scores: list[tuple[str, float]] = []
    for key in ("v1", "v2", "v2x", "v3"):
        cv = (versions.get(key) or {}).get("cv_mape")
        if cv is not None:
            scores.append((key, float(cv)))
    if not scores:
        return None
    scores.sort(key=lambda x: x[1])
    return scores[0][0]


def _pool_fixed_version(
    case: dict[str, Any],
    *,
    pool_id: str,
    v0_cv: float | None,
    version_key: str,
) -> dict[str, Any] | None:
    """stage2.pools에서 고정 pool_id의 CV로 lift 산출 (ablation)."""
    if "error" in case:
        return None
    pools = (case.get("stage2") or {}).get("pools") or []
    hit = next((p for p in pools if p.get("candidate_id") == pool_id and p.get("cv_mape") is not None), None)
    if not hit:
        return None
    twin_cv = float(hit["cv_mape"])
    rel = _lift_rel(v0_cv, twin_cv)
    return {
        "cv_mape": twin_cv,
        "delta_pp": _delta_pp(v0_cv, twin_cv),
        "lift_rel": rel,
        "hit": bool(rel is not None and rel >= 0.05),
        "n": hit.get("n"),
        "blocks": hit.get("blocks") or [],
        "pool_id": pool_id,
        "stage2_ran": True,
        "twin_profile": (case.get("twin_meta") or {}).get("twin_profile"),
        "fixed_pool": True,
        "version_key_ref": version_key,
    }


def summarize_pool_ablation(
    regions_source_cases: list[dict[str, Any]],
    *,
    hit_threshold_rel: float = 0.05,
    pool_ids: tuple[str, ...] = ("twin_pool_n1", "twin_pool_n3"),
) -> dict[str, Any]:
    """케이스 목록에서 고정 pool별 median lift (V0 대비)."""
    out: dict[str, Any] = {}
    for pid in pool_ids:
        faux_regions: list[dict[str, Any]] = []
        for case in regions_source_cases:
            if "error" in case:
                continue
            v0 = (case.get("stage1") or {}).get("cv_mape")
            ver = _pool_fixed_version(case, pool_id=pid, v0_cv=v0, version_key="pool")
            if not ver:
                continue
            faux_regions.append({"versions": {"pool": ver}})
        out[pid] = _kpi_for_version(faux_regions, "pool", hit_threshold_rel=hit_threshold_rel)
    return out


def _version_from_profile_case(
    case: dict[str, Any],
    *,
    v0_cv: float | None,
    v0_blocks: list[str] | None,
    v0_scale: str | None,
    v0_n: int | None,
    version_key: str,
) -> dict[str, Any]:
    if "error" in case:
        return {"error": case["error"], "cv_mape": None}

    stage1 = case.get("stage1") or {}
    lift = case.get("lift") or {}
    twins = case.get("twins") or []
    twin_cv = lift.get("best_pool_cv_mape")
    # stage2 미실행/실패 시 Local만
    if twin_cv is None:
        twin_cv = stage1.get("cv_mape")

    delta = _delta_pp(v0_cv, twin_cv)
    rel = _lift_rel(v0_cv, twin_cv)
    return {
        "cv_mape": twin_cv,
        "delta_pp": delta,
        "lift_rel": rel,
        "hit": bool(rel is not None and rel >= 0.05) if version_key != "v0" else None,
        "n": lift.get("best_pool_n") or stage1.get("fit_n"),
        "blocks": lift.get("best_pool_blocks") or stage1.get("primary_blocks"),
        "response_scale": stage1.get("response_scale"),
        "twins": twins,
        "pool_id": lift.get("best_pool_id"),
        "local_n": v0_n,
        "stage2_ran": bool((case.get("stage2") or {}).get("ran")),
        "gate_pass_rate": (case.get("stage2") or {}).get("twin_gate_pass_rate"),
        "twin_profile": (case.get("twin_meta") or {}).get("twin_profile"),
        # V0 참고용 (동일 케이스 stage1)
        "v0_ref_cv_mape": v0_cv,
        "v0_ref_blocks": v0_blocks,
        "v0_ref_scale": v0_scale,
    }


def bench_report_to_lab_mart(
    report: dict[str, Any],
    *,
    experiment_id: str,
    v1_profile: str = "general",
    v2_profile: str = "built_commercial",
    v2x_profile: str | None = None,
    hit_threshold_rel: float = 0.05,
    sample_group: str = "pilot",
    anchor_basin: str = "chungcheong",
) -> dict[str, Any]:
    """`--compare` 벤치 리포트를 Lab mart JSON으로 변환."""
    defaults = report.get("defaults") or {}
    profiles = report.get("profiles") or {}
    p1 = profiles.get(v1_profile) or {}
    p2 = profiles.get(v2_profile) or {}
    p2x = profiles.get(v2x_profile) if v2x_profile else None
    cases1 = {c["case_id"]: c for c in p1.get("cases") or []}
    cases2 = {c["case_id"]: c for c in p2.get("cases") or []}
    cases2x = {c["case_id"]: c for c in (p2x or {}).get("cases") or []}
    case_ids = sorted(set(cases1) | set(cases2) | set(cases2x))

    regions: list[dict[str, Any]] = []
    for cid in case_ids:
        c1 = cases1.get(cid) or {}
        c2 = cases2.get(cid) or {}
        c2x = cases2x.get(cid) or {}
        base = c1 or c2 or c2x
        stage1 = (c1.get("stage1") or c2.get("stage1") or c2x.get("stage1") or {})
        v0_cv = stage1.get("cv_mape")
        v0_blocks = stage1.get("primary_blocks")
        v0_scale = stage1.get("response_scale")
        v0_n = stage1.get("fit_n") or stage1.get("selection_n")

        versions: dict[str, Any] = {
            "v0": {
                "cv_mape": v0_cv,
                "n": v0_n,
                "blocks": v0_blocks,
                "response_scale": v0_scale,
                "twins": [],
            },
        }
        if c1:
            versions["v1"] = _version_from_profile_case(
                c1,
                v0_cv=v0_cv,
                v0_blocks=v0_blocks,
                v0_scale=v0_scale,
                v0_n=v0_n,
                version_key="v1",
            )
        if c2 and v2_profile in profiles:
            versions["v2"] = _version_from_profile_case(
                c2,
                v0_cv=v0_cv,
                v0_blocks=v0_blocks,
                v0_scale=v0_scale,
                v0_n=v0_n,
                version_key="v2",
            )
        if c2x and v2x_profile and v2x_profile in profiles:
            versions["v2x"] = _version_from_profile_case(
                c2x,
                v0_cv=v0_cv,
                v0_blocks=v0_blocks,
                v0_scale=v0_scale,
                v0_n=v0_n,
                version_key="v2x",
            )

        case_sg = base.get("sample_group") or sample_group
        regions.append(
            {
                "case_id": cid,
                "region_code": (base.get("region_codes") or [None])[0],
                "region_codes": base.get("region_codes") or [],
                "region_label": base.get("label") or cid,
                "admin_level": base.get("admin_level"),
                "role": base.get("role"),
                "sample_group": case_sg,
                "versions": versions,
                "winner": _winner(versions),
            }
        )

    version_keys = ["v0", "v1"]
    if v2_profile in profiles:
        version_keys.append("v2")
    if v2x_profile and v2x_profile in profiles:
        version_keys.append("v2x")

    kpis = {
        vk: _kpi_for_version(regions, vk, hit_threshold_rel=hit_threshold_rel)
        for vk in version_keys
    }
    kpis_by_group = _kpis_by_sample_group(
        regions, version_keys, hit_threshold_rel=hit_threshold_rel
    )

    # 프로토콜 권장: top3 고정 vs 엔진 best — V2 케이스 기준
    v2_cases = list(cases2.values()) if v2_profile in profiles else []
    pool_ablation = summarize_pool_ablation(v2_cases, hit_threshold_rel=hit_threshold_rel)

    return {
        "schema_version": "1.0",
        "experiment_id": experiment_id,
        "asset_type": defaults.get("asset_type") or (report.get("meta") or {}).get("asset_type") or "commercial",
        "period_years": 5,
        "contract_year_from": defaults.get("contract_year_from"),
        "contract_year_to": defaults.get("contract_year_to"),
        "region_scope": defaults.get("twin_scope_eup") or "region",
        "anchor_basin": anchor_basin,
        "profile_version": defaults.get("profile_version"),
        "window_years": defaults.get("window_years"),
        "pool_variant": "engine_best",
        "hit_threshold_rel": hit_threshold_rel,
        "versions": version_keys,
        "v1_twin_profile": v1_profile,
        "v2_twin_profile": v2_profile if v2_profile in profiles else None,
        "v2x_twin_profile": v2x_profile if v2x_profile and v2x_profile in profiles else None,
        "generated_at": report.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "source": "bench_twin_built_recommend_lift",
        "kpis": kpis,
        "kpis_by_sample_group": kpis_by_group,
        "pool_ablation_v2": pool_ablation,
        "regions": regions,
    }
