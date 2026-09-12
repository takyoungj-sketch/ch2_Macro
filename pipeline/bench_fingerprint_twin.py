#!/usr/bin/env python3
"""Fingerprint Twin 1차 러너 — 프로필 Twin 우주를 공통식 지문으로 재순위.

같은 Local 식(D-073 diagnose)에 Twin 1위만 붙인다. 승패는 확인 CV.
새 관리자 문은 만들지 않는다. 결과는 Twin Experiment Lab JSON.

  cd pipeline
  python bench_fingerprint_twin.py
  python bench_fingerprint_twin.py --fixture fixtures/twin_bench_commercial_chungbuk12.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "pipeline"))

from app.built.db import get_built_engine  # noqa: E402
from app.built.lab_fingerprint_twin import (  # noqa: E402
    N_MIN_SIGUNGU,
    Fingerprint,
    fit_common_spec,
    parent_sigungu,
    rerank_neighbors,
)
from app.built.schemas import RegressionSelectionRequest  # noqa: E402
from app.recommendation.stage2 import Stage2Input, run_stage2_twin  # noqa: E402
from app.recommendation.stages import _build_stage1  # noqa: E402
from twin_lab.mart import _kpi_for_version, _kpis_by_sample_group  # noqa: E402

import bench_twin_built_recommend_lift as lift  # noqa: E402

DEFAULT_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "twin_bench_commercial_pilot_eup4.json"


def _load_rows(eng, *, sigungu: str, asset: str, y0: int, y1: int) -> pd.DataFrame:
    sql = text(
        """
        SELECT price, gross_area, land_area, road_width_label
        FROM built_transactions
        WHERE asset_type = :asset
          AND price > 0 AND gross_area > 0 AND land_area > 0
          AND contract_year >= :y0 AND contract_year <= :y1
          AND (
            btrim(COALESCE(sigungu_code::text, '')) = :sg
            OR left(btrim(COALESCE(eupmyeondong_code::text, '')), 5) = :sg
          )
        """
    )
    return pd.read_sql(sql, eng, params={"asset": asset, "y0": y0, "y1": y1, "sg": sigungu})


def _collect_parents(anchor: str, neighbors: list[dict[str, object]]) -> set[str]:
    out = {parent_sigungu(anchor)}
    for row in neighbors:
        code = str(row.get("region_code") or "").strip()
        if code:
            out.add(parent_sigungu(code))
    return {c for c in out if c}


def _confirm_from_stage2(stage2) -> tuple[float | None, float | None, int | None, str | None]:
    """(local_confirm, twin1_confirm, twin_n, used_search_fallback_note)."""
    if stage2 is None or not stage2.ran:
        return None, None, None, None
    local_c = stage2.local_confirm_cv_mape
    if local_c is None:
        local_c = stage2.local_cv_mape
    pool = next((p for p in (stage2.pools or []) if int(p.prefix_k or 0) == 1), None)
    twin_c = None
    twin_n = None
    note = None
    if pool is not None:
        twin_n = pool.n
        if pool.confirm_cv_mape is not None:
            twin_c = pool.confirm_cv_mape
        else:
            twin_c = pool.cv_mape
            note = "confirm_missing_used_search"
    return local_c, twin_c, twin_n, note


def _version(
    *,
    cv: float | None,
    local_cv: float | None,
    n: int | None,
    twins: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lift = None
    delta = None
    if local_cv is not None and cv is not None and local_cv > 0:
        delta = round(local_cv - cv, 2)
        lift = round((local_cv - cv) / local_cv, 4)
    out: dict[str, Any] = {
        "cv_mape": cv,
        "delta_pp": delta,
        "lift_rel": lift,
        "hit": bool(lift is not None and lift >= 0.05),
        "n": n,
        "twins": twins,
        "stage2_ran": True,
        "metric": "confirm_cv_mape",
    }
    if extra:
        out.update(extra)
    return out


def _winner(versions: dict[str, Any]) -> str | None:
    scores: list[tuple[str, float]] = []
    for key in ("r0", "t1", "fp", "rnd"):
        cv = (versions.get(key) or {}).get("cv_mape")
        if cv is not None:
            scores.append((key, float(cv)))
    if not scores:
        return None
    scores.sort(key=lambda x: x[1])
    return scores[0][0]


def _neighbor_payload(row: dict[str, object] | Any) -> dict[str, object]:
    if hasattr(row, "region_code"):
        return {
            "region_code": row.region_code,
            "similarity_score": row.profile_score,
            "label": row.label,
        }
    return {
        "region_code": str(row.get("region_code")),
        "similarity_score": row.get("similarity_score"),
        "label": row.get("label"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--id", dest="experiment_id", default=None)
    parser.add_argument("--n-min", type=int, default=N_MIN_SIGUNGU)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    defaults = fixture["defaults"]
    cases = fixture["cases"]
    asset = defaults["asset_type"]
    y0 = int(defaults["contract_year_from"])
    y1 = int(defaults["contract_year_to"])
    top_k = int(defaults.get("twin_top_k") or 5)
    sido = str(defaults.get("sido_prefix") or "").strip()
    basin = {"43": "chungbuk", "41": "gyeonggi"}.get(sido, sido or "pilot")
    exp_id = (args.experiment_id or f"fingerprint-twin-{basin}").strip()

    eng = get_built_engine()
    if eng is None:
        raise SystemExit("BUILT_DATABASE_URL missing")

    fingerprints: dict[str, Fingerprint] = {}
    fp_errors: dict[str, str] = {}
    regions_out: list[dict[str, Any]] = []

    with eng.connect() as built_conn:
        for i, case in enumerate(cases, start=1):
            print(f"[{i}/{len(cases)}] {case.get('label') or case['case_id']}", flush=True)
            admin_level = case["admin_level"]
            anchor = case["region_codes"][0]
            neighbors, twin_meta = lift._fetch_v2_pool_neighbors(
                admin_level=admin_level,
                anchor_code=anchor,
                top_k=top_k,
            )
            for sg in _collect_parents(anchor, neighbors):
                if sg in fingerprints or sg in fp_errors:
                    continue
                df = _load_rows(eng, sigungu=sg, asset=asset, y0=y0, y1=y1)
                fp = fit_common_spec(df, sigungu_code=sg, n_min=args.n_min)
                if fp is None:
                    fp_errors[sg] = f"n={len(df)} < {args.n_min} or fit failed"
                else:
                    fingerprints[sg] = fp

            empty_note = None
            if not neighbors:
                gated = (twin_meta.get("universe") or {}).get("gated_out_population")
                empty_note = (
                    f"v2_pool_empty (population_gate_out={gated})"
                    if gated is not None
                    else "v2_pool_empty"
                )
            ranked = rerank_neighbors(
                anchor_code=anchor, neighbors=neighbors, fingerprints=fingerprints
            )
            profile_top = neighbors[0] if neighbors else None
            fp_top = ranked[0] if ranked and ranked[0].fingerprint_distance is not None else None

            h = int(hashlib.md5(str(case["case_id"]).encode("utf-8")).hexdigest()[:8], 16)
            rng = random.Random(args.seed + h)
            exclude = {
                str(profile_top.get("region_code")) if profile_top else "",
                fp_top.region_code if fp_top else "",
            }
            rest = [n for n in neighbors if str(n.get("region_code")) not in exclude]
            rnd_top = rng.choice(rest or neighbors) if (rest or neighbors) else None

            req_base = RegressionSelectionRequest(
                asset_type=asset,
                admin_level=admin_level,
                region_codes=list(case["region_codes"]),
                region_code_level=admin_level,
                contract_year_from=y0,
                contract_year_to=y1,
                profile_version=defaults.get("profile_version"),
                profile_window_years=defaults.get("window_years"),
                profile_twin_neighbors=[],
                run_stage2=False,
            )
            row: dict[str, Any] = {
                "case_id": case["case_id"],
                "region_code": anchor,
                "region_codes": list(case["region_codes"]),
                "region_label": case.get("label") or case["case_id"],
                "admin_level": admin_level,
                "role": case.get("role"),
                "sample_group": case.get("sample_group") or "pilot",
                "twin_meta": twin_meta,
            }
            try:
                analysis_scope, stage1, _primary, _alt, _grade, bundle, _exc = _build_stage1(
                    built_conn, req_base
                )
            except ValueError as exc:
                row["error"] = str(exc)
                row["versions"] = {}
                row["winner"] = None
                regions_out.append(row)
                continue

            local_n = stage1.fit_n
            versions: dict[str, Any] = {}

            def run_arm(neigh: list[dict[str, object]] | None):
                if not neigh:
                    return None
                req = req_base.model_copy(update={"profile_twin_neighbors": neigh, "run_stage2": True})
                return run_stage2_twin(
                    built_conn,
                    Stage2Input(
                        ctx=bundle.ctx,
                        req=req,
                        blocks=list(bundle.pool),
                        primary_raw=bundle.primary_raw,
                        analysis_scope=analysis_scope,
                        region_col=bundle.region_col,
                    ),
                )

            s_profile = run_arm([profile_top] if profile_top else None)
            s_fp = run_arm([_neighbor_payload(fp_top)] if fp_top else None)
            s_rnd = run_arm([rnd_top] if rnd_top else None)

            local_c, t1_c, t1_n, t1_note = _confirm_from_stage2(s_profile)
            if local_c is None:
                local_c = stage1.satisfaction.cv_mape
            versions["r0"] = {
                "cv_mape": local_c,
                "n": local_n,
                "blocks": list(bundle.primary_raw.blocks),
                "response_scale": bundle.primary_raw.fit.response_scale,
                "twins": [],
                "metric": "confirm_cv_mape",
            }
            versions["t1"] = _version(
                cv=t1_c,
                local_cv=local_c,
                n=t1_n,
                twins=[_neighbor_payload(profile_top)] if profile_top else [],
                extra={"note": t1_note or empty_note, "arm": "profile_rank1"},
            )
            _, fp_c, fp_n, fp_note = _confirm_from_stage2(s_fp)
            versions["fp"] = _version(
                cv=fp_c,
                local_cv=local_c,
                n=fp_n,
                twins=[_neighbor_payload(fp_top)] if fp_top else [],
                extra={
                    "note": fp_note or empty_note,
                    "arm": "fingerprint_rank1",
                    "curve_r": fp_top.curve_r if fp_top else None,
                    "beta_cosine": fp_top.beta_cosine if fp_top else None,
                    "fp_distance": fp_top.fingerprint_distance if fp_top else None,
                    "parent_sigungu": fp_top.parent_sigungu if fp_top else None,
                    "anchor_parent": parent_sigungu(anchor),
                    "anchor_fp_n": fingerprints.get(parent_sigungu(anchor)).n
                    if fingerprints.get(parent_sigungu(anchor))
                    else None,
                },
            )
            _, rnd_c, rnd_n, rnd_note = _confirm_from_stage2(s_rnd)
            versions["rnd"] = _version(
                cv=rnd_c,
                local_cv=local_c,
                n=rnd_n,
                twins=[_neighbor_payload(rnd_top)] if rnd_top else [],
                extra={"note": rnd_note or empty_note, "arm": "random_from_same_universe"},
            )
            row["versions"] = versions
            row["winner"] = _winner(versions)
            row["same_pick"] = bool(
                profile_top
                and fp_top
                and str(profile_top.get("region_code")) == fp_top.region_code
            )
            regions_out.append(row)

    version_keys = ["r0", "t1", "fp", "rnd"]
    # mart helper treats v0 as local; alias r0 through a copy named v0 for that function
    kpi_regions = []
    for r in regions_out:
        vers = dict(r.get("versions") or {})
        if "r0" in vers:
            vers = {**vers, "v0": vers["r0"]}
        kpi_regions.append({**r, "versions": vers})
    kpis = {
        "r0": _kpi_for_version(kpi_regions, "v0", hit_threshold_rel=0.05),
        "t1": _kpi_for_version(kpi_regions, "t1", hit_threshold_rel=0.05),
        "fp": _kpi_for_version(kpi_regions, "fp", hit_threshold_rel=0.05),
        "rnd": _kpi_for_version(kpi_regions, "rnd", hit_threshold_rel=0.05),
    }
    kpis_by_group = _kpis_by_sample_group(kpi_regions, ["v0", "t1", "fp", "rnd"], hit_threshold_rel=0.05)
    if "v0" in kpis_by_group.get("all", {}):
        for g, block in kpis_by_group.items():
            if "v0" in block:
                block["r0"] = block.pop("v0")

    n_fp_win = sum(1 for r in regions_out if r.get("winner") == "fp")
    n_t1_win = sum(1 for r in regions_out if r.get("winner") == "t1")
    n_r0_win = sum(1 for r in regions_out if r.get("winner") == "r0")
    n_rnd_win = sum(1 for r in regions_out if r.get("winner") == "rnd")
    n_same = sum(1 for r in regions_out if r.get("same_pick"))

    experiment = {
        "schema_version": "1.0",
        "experiment_id": exp_id,
        "asset_type": asset,
        "period_years": y1 - y0 + 1,
        "contract_year_from": y0,
        "contract_year_to": y1,
        "region_scope": "pool_rerank",
        "anchor_basin": basin,
        "versions": version_keys,
        "hit_threshold_rel": 0.05,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "bench_fingerprint_twin",
        "notes": (
            "공통식=시군구 log(연면적)+log(대지)+도로. Twin 우주는 V2 풀. "
            "t1=프로필 1위, fp=지문 1위, rnd=같은 우주 무작위. "
            "cv_mape 칸은 확인 CV(없으면 탐색 CV). 제품 Twin 선정은 바꾸지 않음."
        ),
        "fingerprint_spec": {
            "grain": "sigungu",
            "formula": "ln(price) ~ ln(gross)+ln(land)+road_dummy",
            "n_min": args.n_min,
            "intercept_in_distance": False,
        },
        "fp_fit_errors": fp_errors,
        "summary": {
            "n_cases": len(regions_out),
            "n_fingerprint_fitted": len(fingerprints),
            "n_same_pick": n_same,
            "n_winner_fp": n_fp_win,
            "n_winner_t1": n_t1_win,
            "n_winner_r0": n_r0_win,
            "n_winner_rnd": n_rnd_win,
        },
        "kpis": kpis,
        "kpis_by_sample_group": kpis_by_group,
        "regions": regions_out,
    }

    out = args.out
    if out is None:
        logs = REPO / "logs" / "twin_lab"
        logs.mkdir(parents=True, exist_ok=True)
        out = logs / f"{exp_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(experiment, ensure_ascii=False, indent=2), encoding="utf-8")
    fixture_copy = REPO / "pipeline" / "fixtures" / f"{exp_id}.json"
    fixture_copy.write_text(json.dumps(experiment, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(experiment["summary"], ensure_ascii=False))
    print("wrote", out)
    print("wrote", fixture_copy)


if __name__ == "__main__":
    main()
