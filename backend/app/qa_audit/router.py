"""관리자 전용 QA API. 공개 앱에 링크하지 않음. QA_AUDIT_TOKEN 필수."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.qa_audit.engine import run_random, run_specified

router = APIRouter(prefix="/admin/qa", tags=["admin-qa"], include_in_schema=False)


def _require_token(x_qa_audit_token: str | None) -> None:
    expected = (settings.qa_audit_token or "").strip()
    if not expected:
        return
    if (x_qa_audit_token or "").strip() != expected:
        raise HTTPException(status_code=401, detail="X-Qa-Audit-Token 이 없거나 잘못되었습니다.")


def _engine_for(domain: str | None):
    from app.qa_audit.engine import _normalize_domain

    try:
        d = _normalize_domain(domain)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if d == "built_enriched":
        from app.built.db import get_built_engine

        engine = get_built_engine()
        if engine is None:
            raise HTTPException(status_code=503, detail="BUILT_DATABASE_URL 없음")
        return engine, d
    from app.collective.db import get_collective_engine

    engine = get_collective_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="COLLECTIVE_DATABASE_URL 없음")
    return engine, d


class SpecifiedBody(BaseModel):
    calendar_year: int = Field(..., ge=2006, le=2100)
    region_code: str | None = None
    region_name: str | None = None
    region_level: str | None = None
    asset_type: str | None = None
    domain: str | None = "collective_apt"
    save_db: bool = False


class RandomBody(BaseModel):
    calendar_year: int | None = Field(default=None, ge=2006, le=2100)
    asset_type: str | None = None
    domain: str | None = "collective_apt"
    n: int = Field(1, ge=1, le=3)
    save_db: bool = False
    seed: int | None = None


@router.post("/specified")
def post_specified(
    body: SpecifiedBody,
    x_qa_audit_token: str | None = Header(default=None, alias="X-Qa-Audit-Token"),
) -> dict[str, Any]:
    _require_token(x_qa_audit_token)
    engine, domain = _engine_for(body.domain)
    try:
        return run_specified(
            engine,
            calendar_year=body.calendar_year,
            region_code=body.region_code,
            region_name=body.region_name,
            region_level=body.region_level,
            asset_type=body.asset_type,
            save_db=body.save_db,
            domain=domain,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/random")
def post_random(
    body: RandomBody,
    x_qa_audit_token: str | None = Header(default=None, alias="X-Qa-Audit-Token"),
) -> dict[str, Any]:
    _require_token(x_qa_audit_token)
    engine, domain = _engine_for(body.domain)
    try:
        runs = run_random(
            engine,
            calendar_year=body.calendar_year,
            asset_type=body.asset_type,
            n=body.n,
            save_db=body.save_db,
            seed=body.seed,
            domain=domain,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"runs": runs, "count": len(runs)}


@router.get("/runs")
def get_runs(
    limit: int = 20,
    domain: str | None = None,
    x_qa_audit_token: str | None = Header(default=None, alias="X-Qa-Audit-Token"),
) -> dict[str, Any]:
    _require_token(x_qa_audit_token)
    from app.qa_audit.store import ensure_table, list_runs

    engine, domain = _engine_for(domain or "collective_apt")
    try:
        with engine.begin() as conn:
            ensure_table(conn)
            items = list_runs(conn, limit=min(max(limit, 1), 50), domain=domain)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"qa_audit_run 조회 실패: {exc}") from exc
    return {"items": items}
