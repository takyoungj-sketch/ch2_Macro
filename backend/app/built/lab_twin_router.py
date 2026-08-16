"""Twin Experiment Lab API — R&D 전용 (파일 mart 조회)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.built.lab_twin_store import lab_enabled, list_experiments, load_experiment

router = APIRouter(prefix="/built/lab/twin-experiments", tags=["Twin Experiment Lab"])


def _require_lab() -> None:
    if not lab_enabled():
        raise HTTPException(status_code=404, detail="Twin Experiment Lab disabled (TWIN_LAB_ENABLED=0)")


@router.get("")
def twin_lab_list():
    """실험 런 목록."""
    _require_lab()
    return {"items": list_experiments()}


@router.get("/{experiment_id}")
def twin_lab_get(experiment_id: str):
    """실험 전체 (KPI + 지역 행)."""
    _require_lab()
    data = load_experiment(experiment_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"experiment not found: {experiment_id}")
    return data


@router.get("/{experiment_id}/regions/{region_key}")
def twin_lab_region(
    experiment_id: str,
    region_key: str,
    by: str = Query("case_id", description="case_id | region_code"),
):
    """지역 상세 (Region Explorer)."""
    _require_lab()
    data = load_experiment(experiment_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"experiment not found: {experiment_id}")
    key = region_key.strip()
    for row in data.get("regions") or []:
        if by == "region_code" and str(row.get("region_code")) == key:
            return row
        if str(row.get("case_id")) == key or str(row.get("region_code")) == key:
            return row
    raise HTTPException(status_code=404, detail=f"region not found: {region_key}")
