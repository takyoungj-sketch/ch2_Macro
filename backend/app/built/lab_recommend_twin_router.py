"""복합 모형추천 Twin 벤치 랩 API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.built.db import get_built_db
from app.built.lab_recommend_twin_bench import run_recommend_twin_bench
from app.built.schemas import RegressionSelectionRequest

router = APIRouter(prefix="/built/lab/recommend-twin-bench", tags=["Recommend Twin Bench Lab"])

_REPO = Path(__file__).resolve().parents[2]
_FIXTURE_SETS: dict[str, list[Path]] = {
    "chungbuk": [
        _REPO.parent / "pipeline" / "fixtures" / "twin_bench_commercial_chungbuk12.json",
        _REPO.parent / "pipeline" / "fixtures" / "twin_bench_factory_chungbuk8.json",
        _REPO.parent / "pipeline" / "fixtures" / "twin_bench_detached_chungbuk8.json",
    ],
    "gyeonggi": [
        _REPO.parent / "pipeline" / "fixtures" / "twin_bench_commercial_gyeonggi12.json",
        _REPO.parent / "pipeline" / "fixtures" / "twin_bench_factory_gyeonggi8.json",
        _REPO.parent / "pipeline" / "fixtures" / "twin_bench_detached_gyeonggi8.json",
    ],
}
_FIXTURES = [p for paths in _FIXTURE_SETS.values() for p in paths]


class BenchScenario(BaseModel):
    gross_area: float = 120
    land_area: float = 250
    building_age: float = 10
    road_width_label: Optional[str] = "12미터미만"


class RecommendTwinBenchRequest(BaseModel):
    asset_type: Literal["commercial", "factory", "detached"] = "commercial"
    region_code: str
    window_years: int = Field(5, ge=3, le=7)
    profile_twin_neighbors: list[dict[str, Any]] = Field(default_factory=list)
    profile_version: Optional[str] = None
    profile_as_of_month: Optional[str] = None
    profile_window_years: Optional[int] = None
    scenario: BenchScenario = Field(default_factory=BenchScenario)
    contract_year_from: Optional[int] = 2019
    contract_year_to: Optional[int] = None
    as_of_month: Optional[str] = None
    enrich: bool = False


@router.get("/cases")
def list_bench_cases():
    items: list[dict[str, Any]] = []
    for path in _FIXTURES:
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        defaults = data.get("defaults") or {}
        for case in data.get("cases") or []:
            codes = case.get("region_codes") or []
            if not codes:
                continue
            items.append(
                {
                    "case_id": case.get("case_id"),
                    "label": case.get("label") or codes[0],
                    "asset_type": defaults.get("asset_type"),
                    "region_code": codes[0],
                    "sample_group": case.get("sample_group"),
                    "tx_n": (case.get("strata") or {}).get("tx_n"),
                    "sido_prefix": defaults.get("sido_prefix"),
                    "basin": (case.get("strata") or {}).get("basin"),
                    "exclude_general_gu": bool(defaults.get("exclude_general_gu")),
                }
            )
    return {"items": items}


@router.post("")
def run_bench(body: RecommendTwinBenchRequest, db: Session = Depends(get_built_db)):
    code = str(body.region_code or "").strip()
    if len(code) < 8:
        raise HTTPException(400, "읍면동 코드 8자리가 필요합니다.")
    req = RegressionSelectionRequest(
        asset_type=body.asset_type,
        region_codes=[code[:8]],
        region_code_level="eupmyeondong",
        window_years=body.window_years,
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
        as_of_month=body.as_of_month,
        enrich=body.enrich,
        profile_twin_neighbors=list(body.profile_twin_neighbors or []),
        profile_version=body.profile_version,
        profile_as_of_month=body.profile_as_of_month,
        profile_window_years=body.profile_window_years,
        run_stage2=False,
        run_stage2_research=False,
    )
    try:
        return run_recommend_twin_bench(
            db.connection(),
            req=req,
            scenario=body.scenario.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
