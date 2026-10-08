#!/usr/bin/env python3
"""복합 recommend Stage2 twin_validation 실응답 스모크 (okcheon_eup)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "pipeline"))

from app.built.db import get_built_engine  # noqa: E402
from app.db import engine as land_engine  # noqa: E402
from app.built.schemas import RegressionSelectionRequest  # noqa: E402
from app.recommendation.stages import run_recommendation  # noqa: E402
from bench_twin_built_recommend_lift import (  # noqa: E402
    _fetch_twin_neighbors,
    _load_fixture,
)
from collective.db_utils import get_collective_engine  # noqa: E402


def main() -> int:
    fixture = _load_fixture(
        REPO / "pipeline/fixtures/twin_bench_commercial_pilot_eup4.json"
    )
    case = next(c for c in fixture["cases"] if c["case_id"] == "okcheon_eup")
    defaults = fixture["defaults"]
    twin_profile = "built_commercial"

    built = get_built_engine()
    coll = get_collective_engine()
    land = land_engine

    with built.connect() as built_conn, coll.connect() as coll_conn, land.connect() as land_conn:
        neighbors, twin_meta = _fetch_twin_neighbors(
            coll_conn,
            land_conn,
            admin_level=case["admin_level"],
            anchor_code=case["region_codes"][0],
            profile_version=defaults["profile_version"],
            window_years=defaults["window_years"],
            top_k=defaults.get("twin_top_k", 5),
            scope_eup=defaults.get("twin_scope_eup", "region"),
            twin_profile=twin_profile,
        )
        req = RegressionSelectionRequest(
            asset_type=defaults["asset_type"],
            admin_level=case["admin_level"],
            region_codes=list(case["region_codes"]),
            region_code_level=case["admin_level"],
            contract_year_from=defaults.get("contract_year_from"),
            contract_year_to=defaults.get("contract_year_to"),
            profile_version=defaults["profile_version"],
            profile_window_years=defaults["window_years"],
            profile_twin_neighbors=neighbors,
            run_stage2=True,
        )
        resp = run_recommendation(built_conn, req)

    stage2 = resp.stage2
    tv = stage2.twin_validation if stage2 else None
    out = {
        "case_id": case["case_id"],
        "label": case.get("label"),
        "twin_meta": twin_meta,
        "neighbors_n": len(neighbors),
        "stage2_ran": bool(stage2 and stage2.ran),
        "decision": stage2.decision if stage2 else None,
        "twin_validation": tv.model_dump() if tv else None,
        "local_cv_mape": stage2.local_cv_mape if stage2 else None,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if tv is None:
        print("FAIL: twin_validation missing", file=sys.stderr)
        return 1
    if tv.verdict not in {"improved", "tie", "worse", "skipped"}:
        print("FAIL: bad verdict", file=sys.stderr)
        return 1
    # okcheon golden: expect improved
    if tv.verdict != "improved" or not tv.twin_adopt_recommended:
        print(
            f"WARN: expected improved for okcheon, got {tv.verdict}",
            file=sys.stderr,
        )
    print("SMOKE_OK", tv.verdict, tv.label_ko)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
