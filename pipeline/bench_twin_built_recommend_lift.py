#!/usr/bin/env python3
"""Twin × 복합 모형추천 lift 벤치 — Local recommend → Twin stage2 → KPI JSON.

예:
  cd pipeline
  python bench_twin_built_recommend_lift.py
  python bench_twin_built_recommend_lift.py --twin-profile general --compare built_commercial
  python bench_twin_built_recommend_lift.py --case okcheon_eup --out /tmp/lift.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "pipeline"))

from sqlalchemy import text  # noqa: E402

from app.built.db import get_built_engine  # noqa: E402
from app.db import engine as land_engine  # noqa: E402
from app.built.regression.candidates.profile_adapter import normalize_profile_twin_neighbors  # noqa: E402
from app.built.schemas import RegressionSelectionRequest  # noqa: E402
from app.recommendation.stages import run_recommendation  # noqa: E402
from collective.db_utils import get_collective_engine  # noqa: E402

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "twin_built_lift_bench.json"
PROFILE_TWIN_ALGO = 21


def _load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_eup_batch(conn, *, profile_version: str, window_years: int, scope: str, twin_profile: str) -> str | None:
    row = conn.execute(
        text(
            """
            SELECT batch_key
            FROM twin_eupmyeondong_neighbor_mvp
            WHERE algorithm_version = :av
              AND detail_scores->>'profile_version' = :pv
              AND (detail_scores->>'window_years')::int = :wy
              AND detail_scores->>'scope' = :scope
              AND COALESCE(detail_scores->>'twin_profile', 'general') = :tp
            GROUP BY batch_key
            ORDER BY MAX(computed_at) DESC
            LIMIT 1
            """
        ),
        {
            "av": PROFILE_TWIN_ALGO,
            "pv": profile_version,
            "wy": window_years,
            "scope": scope,
            "tp": twin_profile,
        },
    ).fetchone()
    return str(row[0]) if row else None


def _latest_beop_batch(conn, *, profile_version: str, window_years: int, twin_profile: str) -> str | None:
    row = conn.execute(
        text(
            """
            SELECT batch_key
            FROM twin_neighbor_v8
            WHERE algorithm_version = :av
              AND region_level = 'beopjungri'
              AND detail_scores->>'profile_version' = :pv
              AND (detail_scores->>'window_years')::int = :wy
              AND detail_scores->>'scope' = 'same_sigungu'
              AND COALESCE(detail_scores->>'twin_profile', 'general') = :tp
            GROUP BY batch_key
            ORDER BY MAX(computed_at) DESC
            LIMIT 1
            """
        ),
        {
            "av": PROFILE_TWIN_ALGO,
            "pv": profile_version,
            "wy": window_years,
            "tp": twin_profile,
        },
    ).fetchone()
    return str(row[0]) if row else None


def _fetch_twin_neighbors(
    coll_conn,
    main_conn,
    *,
    admin_level: str,
    anchor_code: str,
    profile_version: str,
    window_years: int,
    top_k: int,
    scope_eup: str,
    twin_profile: str,
) -> tuple[list[dict[str, object]], dict[str, Any]]:
    meta: dict[str, Any] = {
        "twin_profile": twin_profile,
        "profile_version": profile_version,
        "window_years": window_years,
        "algorithm_version": PROFILE_TWIN_ALGO,
    }
    if admin_level == "beopjungri":
        batch_key = _latest_beop_batch(
            main_conn, profile_version=profile_version, window_years=window_years, twin_profile=twin_profile
        )
        if not batch_key:
            return [], {**meta, "batch_key": None, "error": "beop twin batch 없음"}
        rows = main_conn.execute(
            text(
                """
                SELECT rank, twin_region_code AS twin_code, similarity_score, detail_scores
                FROM twin_neighbor_v8
                WHERE batch_key = :bk AND anchor_region_code = :ac AND region_level = 'beopjungri'
                ORDER BY rank
                LIMIT :top_k
                """
            ),
            {"bk": batch_key, "ac": anchor_code, "top_k": top_k},
        ).mappings().all()
        payload = {
            "algorithm_version": PROFILE_TWIN_ALGO,
            "profile_version": profile_version,
            "window_years": window_years,
            "neighbors": [
                {
                    "rank": int(r["rank"]),
                    "twin_beopjungri_code": str(r["twin_code"]).strip(),
                    "similarity_score": float(r["similarity_score"]),
                }
                for r in rows
            ],
        }
        meta["batch_key"] = batch_key
        if rows:
            detail = rows[0].get("detail_scores") or {}
            if isinstance(detail, dict):
                meta["weight_version"] = detail.get("weight_version")
                meta["catalog_version"] = detail.get("catalog_version")
        return normalize_profile_twin_neighbors(payload, admin_level="beopjungri"), meta

    batch_key = _latest_eup_batch(
        coll_conn,
        profile_version=profile_version,
        window_years=window_years,
        scope=scope_eup,
        twin_profile=twin_profile,
    )
    if not batch_key:
        return [], {**meta, "batch_key": None, "error": "eup twin batch 없음"}
    rows = coll_conn.execute(
        text(
            """
            SELECT rank, twin_eupmyeondong_code AS twin_code, similarity_score, detail_scores
            FROM twin_eupmyeondong_neighbor_mvp
            WHERE batch_key = :bk AND anchor_eupmyeondong_code = :ac
            ORDER BY rank
            LIMIT :top_k
            """
        ),
        {"bk": batch_key, "ac": anchor_code, "top_k": top_k},
    ).mappings().all()
    payload = {
        "algorithm_version": PROFILE_TWIN_ALGO,
        "profile_version": profile_version,
        "window_years": window_years,
        "neighbors": [
            {
                "rank": int(r["rank"]),
                "twin_eupmyeondong_code": str(r["twin_code"]).strip(),
                "similarity_score": float(r["similarity_score"]),
            }
            for r in rows
        ],
    }
    meta["batch_key"] = batch_key
    meta["scope"] = scope_eup
    if rows:
        detail = rows[0].get("detail_scores") or {}
        if isinstance(detail, dict):
            meta["weight_version"] = detail.get("weight_version")
            meta["catalog_version"] = detail.get("catalog_version")
    return normalize_profile_twin_neighbors(payload, admin_level="eupmyeondong"), meta


def _fetch_v2_pool_neighbors(
    *,
    admin_level: str,
    anchor_code: str,
    top_k: int,
) -> tuple[list[dict[str, object]], dict[str, Any]]:
    """D-044 풀 Twin. 제품 adapter(algo 21)를 속이지 않고 region_code 리스트를 직접 만든다."""
    from app.collective.db import get_collective_session_factory
    from app.db import SessionLocal
    from app.regional_profile.twin_v2 import rank_twins_v2

    factory = get_collective_session_factory()
    if factory is None:
        return [], {"engine": "v2", "twin_profile": "engine_v2", "error": "collective_stats 미연결"}
    coll = factory()
    land = SessionLocal()
    try:
        payload = rank_twins_v2(
            coll,
            land,
            region_level=admin_level,
            region_code=anchor_code,
            role="pool",
            top_k=top_k,
            include_v1=False,
        )
    except (LookupError, ValueError) as exc:
        return [], {"engine": "v2", "twin_profile": "engine_v2", "error": str(exc)}
    finally:
        coll.close()
        land.close()

    neighbors: list[dict[str, object]] = []
    for row in payload.get("neighbors") or []:
        code = str(row.get("region_code") or "").strip()
        if not code:
            continue
        neighbors.append(
            {
                "region_code": code,
                "similarity_score": row.get("twin_score"),
                "label": row.get("region_name"),
            }
        )
    return neighbors, {
        "engine": "v2",
        "twin_profile": "engine_v2",
        "role": "pool",
        "weight_version": payload.get("weight_version"),
        "profile_version": payload.get("profile_version"),
        "as_of_month": payload.get("as_of_month"),
        "universe": payload.get("universe"),
    }


def _gate_pass_rate(stage2) -> float | None:
    gates = stage2.twin_gates if stage2 else []
    if not gates:
        return None
    passed = sum(1 for g in gates if g.accepted)
    return round(passed / len(gates), 4)


def _best_pool_lift(stage1, stage2) -> dict[str, Any]:
    local_cv = stage1.satisfaction.cv_mape
    local_n = stage1.fit_n
    out: dict[str, Any] = {
        "local_cv_mape": local_cv,
        "local_fit_n": local_n,
        "cv_lift_pp": None,
        "n_gain": None,
        "lift_hit": None,
        "best_pool_id": None,
        "best_pool_cv_mape": None,
        "best_pool_n": None,
        "best_pool_blocks": [],
    }
    if not stage2 or not stage2.ran or not stage2.pools:
        return out
    best = min(
        (p for p in stage2.pools if p.cv_mape is not None),
        key=lambda p: p.cv_mape,
        default=None,
    )
    if best is None:
        return out
    out["best_pool_id"] = best.candidate_id
    out["best_pool_cv_mape"] = best.cv_mape
    out["best_pool_n"] = best.n
    out["best_pool_blocks"] = list(best.blocks or [])
    if local_cv is not None and best.cv_mape is not None:
        out["cv_lift_pp"] = round(local_cv - best.cv_mape, 2)
    if local_n is not None and best.n is not None:
        out["n_gain"] = best.n - local_n
    return out


def _run_case(
    built_conn,
    coll_conn,
    land_conn,
    case: dict[str, Any],
    defaults: dict[str, Any],
    *,
    twin_profile: str,
    lift_delta: float,
    engine: str = "v1",
) -> dict[str, Any]:
    admin_level = case["admin_level"]
    anchor = case["region_codes"][0]
    if engine == "v2":
        neighbors, twin_meta = _fetch_v2_pool_neighbors(
            admin_level=admin_level,
            anchor_code=anchor,
            top_k=int(defaults.get("twin_top_k") or 5),
        )
    else:
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
    )
    try:
        resp = run_recommendation(built_conn, req)
    except ValueError as exc:
        return {
            "case_id": case["case_id"],
            "label": case.get("label"),
            "role": case.get("role"),
            "sample_group": case.get("sample_group"),
            "error": str(exc),
            "twin_meta": twin_meta,
        }

    stage1 = resp.stage1
    stage2 = resp.stage2
    lift = _best_pool_lift(stage1, stage2)
    delta = lift_delta
    lift_hit = (
        lift["cv_lift_pp"] is not None and lift["cv_lift_pp"] > delta
    )
    lift["lift_hit"] = lift_hit

    twin_rows: list[dict[str, Any]] = []
    for n in neighbors[: int(defaults.get("twin_top_k") or 5)]:
        twin_rows.append(
            {
                "region_code": n.get("region_code") or n.get("neighbor_code"),
                "label": n.get("label") or n.get("region_label") or n.get("name"),
                "similarity": n.get("similarity") or n.get("score"),
            }
        )
    # best pool에 실제로 들어간 코드 표시 + pool ablation 원천
    pool_rows: list[dict[str, Any]] = []
    if stage2 and stage2.pools:
        best = min(
            (p for p in stage2.pools if p.cv_mape is not None),
            key=lambda p: p.cv_mape,
            default=None,
        )
        if best is not None:
            lift["best_pool_region_codes"] = list(best.region_codes or [])
        v0_cv = stage1.satisfaction.cv_mape
        for p in stage2.pools:
            if p.cv_mape is None:
                continue
            delta = None if v0_cv is None else round(float(v0_cv) - float(p.cv_mape), 2)
            pool_rows.append(
                {
                    "candidate_id": p.candidate_id,
                    "cv_mape": p.cv_mape,
                    "n": p.n,
                    "cv_lift_pp": delta,
                    "blocks": list(p.blocks or []),
                }
            )

    return {
        "case_id": case["case_id"],
        "label": case.get("label"),
        "role": case.get("role"),
        "sample_group": case.get("sample_group"),
        "admin_level": admin_level,
        "region_codes": case["region_codes"],
        "twin_neighbors_n": len(neighbors),
        "twins": twin_rows,
        "twin_meta": twin_meta,
        "stage1": {
            "selection_n": stage1.selection_n,
            "fit_n": stage1.fit_n,
            "cv_mape": stage1.satisfaction.cv_mape,
            "grade": stage1.satisfaction.grade,
            "primary_blocks": list(stage1.primary.blocks),
            "response_scale": stage1.primary.response_scale,
        },
        "stage2": {
            "ran": bool(stage2 and stage2.ran),
            "skipped_reason": stage2.skipped_reason if stage2 else None,
            "decision": stage2.decision if stage2 else None,
            "pools_n": len(stage2.pools) if stage2 else 0,
            "twin_gate_pass_rate": _gate_pass_rate(stage2),
            "gates_rejected_n": sum(1 for g in (stage2.twin_gates if stage2 else []) if not g.accepted),
            "pools": pool_rows,
        },
        "lift": lift,
    }


def _aggregate_kpis(cases: list[dict[str, Any]], *, lift_delta: float) -> dict[str, Any]:
    valid = [c for c in cases if "error" not in c and c.get("stage2", {}).get("ran")]
    lifts = [c["lift"]["cv_lift_pp"] for c in valid if c["lift"].get("cv_lift_pp") is not None]
    hits = [c["lift"]["lift_hit"] for c in valid if c["lift"].get("lift_hit") is not None]
    gate_rates = [
        c["stage2"]["twin_gate_pass_rate"]
        for c in valid
        if c["stage2"].get("twin_gate_pass_rate") is not None
    ]
    n_gains = [c["lift"]["n_gain"] for c in valid if c["lift"].get("n_gain") is not None]
    return {
        "cases_total": len(cases),
        "cases_ran_stage2": len(valid),
        "cases_error": sum(1 for c in cases if "error" in c),
        "twin_gate_pass_rate_mean": round(sum(gate_rates) / len(gate_rates), 4) if gate_rates else None,
        "n_gain_mean": round(sum(n_gains) / len(n_gains), 1) if n_gains else None,
        "cv_lift_mean_pp": round(sum(lifts) / len(lifts), 2) if lifts else None,
        "cv_lift_median_pp": round(sorted(lifts)[len(lifts) // 2], 2) if lifts else None,
        "lift_hit_rate": round(sum(1 for h in hits if h) / len(hits), 4) if hits else None,
        "lift_delta_pp": lift_delta,
    }


def _run_profile(
    fixture: dict[str, Any],
    *,
    twin_profile: str,
    case_filter: set[str] | None,
    lift_delta: float,
    engine: str = "v1",
) -> dict[str, Any]:
    defaults = fixture["defaults"]
    cases = fixture["cases"]
    if case_filter:
        cases = [c for c in cases if c["case_id"] in case_filter]

    built_eng = get_built_engine()
    if built_eng is None:
        raise SystemExit("BUILT_DATABASE_URL not configured")
    coll = get_collective_engine()
    results: list[dict[str, Any]] = []
    with (
        built_eng.connect() as built_conn,
        coll.connect() as coll_conn,
        land_engine.connect() as land_conn,
    ):
        for case in cases:
            print(f"  [{engine}/{twin_profile}] {case['case_id']} …", flush=True)
            results.append(
                _run_case(
                    built_conn,
                    coll_conn,
                    land_conn,
                    case,
                    defaults,
                    twin_profile=twin_profile,
                    lift_delta=lift_delta,
                    engine=engine,
                )
            )

    return {
        "twin_profile": twin_profile,
        "engine": engine,
        "cases": results,
        "kpis": _aggregate_kpis(results, lift_delta=lift_delta),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Twin built recommend lift bench")
    p.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    p.add_argument(
        "--twin-profile",
        default="general",
        help="general | built_commercial | built_factory | built_detached",
    )
    p.add_argument(
        "--compare",
        default=None,
        help="두 번째 twin_profile과 비교 (예: built_commercial | built_factory)",
    )
    p.add_argument(
        "--v2x",
        default=None,
        help="V2x ablation twin_profile (예: built_all) — Lab v2x 열",
    )
    p.add_argument(
        "--compare-engine",
        default=None,
        help="v2 이면 V1 마트 풀과 Twin Engine V2 풀을 같은 케이스로 비교",
    )
    p.add_argument("--case", action="append", default=[], help="case_id 필터 (반복 가능)")
    p.add_argument("--lift-delta", type=float, default=None, help="lift_hit delta (percent points)")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument(
        "--lab-out",
        type=Path,
        default=None,
        help="Twin Experiment Lab mart JSON (V0/V1/V2[/V2x]). --compare 권장",
    )
    p.add_argument("--experiment-id", default=None, help="lab mart experiment_id")
    args = p.parse_args()

    fixture = _load_fixture(args.fixture)
    lift_delta = args.lift_delta if args.lift_delta is not None else fixture["defaults"].get("lift_delta_pp", 0.5)
    case_filter = set(args.case) if args.case else None

    # Lab mart는 general + built_commercial 비교가 기본. V2 엔진 비교 시에는 건너뛴다.
    if args.lab_out and not args.compare and args.compare_engine != "v2":
        args.compare = "built_commercial"
        if args.twin_profile == "built_commercial":
            args.twin_profile = "general"

    print(f"bench fixture={args.fixture.name} twin_profile={args.twin_profile}", flush=True)
    primary = _run_profile(
        fixture,
        twin_profile=args.twin_profile,
        case_filter=case_filter,
        lift_delta=lift_delta,
        engine="v1",
    )

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixture_version": fixture.get("version"),
        "defaults": fixture["defaults"],
        "meta": {
            "profile_version": fixture["defaults"]["profile_version"],
            "window_years": fixture["defaults"]["window_years"],
            "asset_type": fixture["defaults"]["asset_type"],
            "as_of": date.today().isoformat(),
        },
        "profiles": {args.twin_profile: primary},
    }

    if args.compare:
        print(f"compare twin_profile={args.compare}", flush=True)
        secondary = _run_profile(
            fixture, twin_profile=args.compare, case_filter=case_filter, lift_delta=lift_delta
        )
        report["profiles"][args.compare] = secondary
        # per-case cv_lift diff (secondary - primary)
        by_id = {c["case_id"]: c for c in primary["cases"]}
        diffs: list[dict[str, Any]] = []
        for c2 in secondary["cases"]:
            c1 = by_id.get(c2["case_id"])
            if not c1 or "error" in c1 or "error" in c2:
                continue
            l1 = c1["lift"].get("cv_lift_pp")
            l2 = c2["lift"].get("cv_lift_pp")
            if l1 is not None and l2 is not None:
                diffs.append(
                    {
                        "case_id": c2["case_id"],
                        "cv_lift_diff_pp": round(l2 - l1, 2),
                        "general_lift_pp": l1,
                        "compare_lift_pp": l2,
                    }
                )
        report["profile_compare"] = {
            "primary": args.twin_profile,
            "secondary": args.compare,
            "cv_lift_diffs": diffs,
            "secondary_better_cases": sum(1 for d in diffs if d["cv_lift_diff_pp"] > 0),
        }

    if args.compare_engine == "v2":
        print("compare engine=v2 pool", flush=True)
        secondary = _run_profile(
            fixture,
            twin_profile="engine_v2",
            case_filter=case_filter,
            lift_delta=lift_delta,
            engine="v2",
        )
        report["profiles"]["engine_v2"] = secondary
        if not args.compare:
            args.compare = "engine_v2"

    if args.v2x:
        print(f"v2x twin_profile={args.v2x}", flush=True)
        report["profiles"][args.v2x] = _run_profile(
            fixture, twin_profile=args.v2x, case_filter=case_filter, lift_delta=lift_delta
        )

    text_out = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text_out, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text_out)
    print("KPI:", json.dumps(primary["kpis"], ensure_ascii=False))

    if args.lab_out:
        from twin_lab.mart import bench_report_to_lab_mart

        exp_id = args.experiment_id or f"pilot-{fixture['defaults']['asset_type']}-{date.today().isoformat()}"
        mart = bench_report_to_lab_mart(
            report,
            experiment_id=exp_id,
            v1_profile=args.twin_profile,
            v2_profile=args.compare or "built_commercial",
            v2x_profile=args.v2x,
        )
        args.lab_out.parent.mkdir(parents=True, exist_ok=True)
        args.lab_out.write_text(json.dumps(mart, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        # 기본 Lab 디렉터리에도 복사 (API 기본 경로)
        lab_dir = REPO / "logs" / "twin_lab"
        lab_dir.mkdir(parents=True, exist_ok=True)
        (lab_dir / f"{exp_id}.json").write_text(
            json.dumps(mart, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        print(f"Wrote Lab mart {args.lab_out} and {lab_dir / (exp_id + '.json')}")


if __name__ == "__main__":
    main()
