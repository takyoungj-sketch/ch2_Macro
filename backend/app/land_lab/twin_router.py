"""관리자 토지 쌍둥이. 공개 앱·토지 통계 모달에는 연결하지 않는다."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.land_lab.land_twin import list_sigungu, run_sigungu

router = APIRouter(prefix="/admin/land-twin", tags=["admin-land-twin"], include_in_schema=False)


@router.get("/regions")
def land_twin_regions(db: Session = Depends(get_db)):
    try:
        return list_sigungu(db)
    except RuntimeError as exc:
        raise HTTPException(404, detail=str(exc)) from exc


class LandTwinRunRequest(BaseModel):
    region_code: str


@router.post("/run")
def land_twin_run(body: LandTwinRunRequest, db: Session = Depends(get_db)):
    try:
        return run_sigungu(db, body.region_code)
    except KeyError:
        raise HTTPException(404, detail="이 시군구의 토지 통계가 없습니다.") from None
    except RuntimeError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
