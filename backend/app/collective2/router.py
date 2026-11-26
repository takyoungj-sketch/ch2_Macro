"""집합2 전용 API. 기존 집합 목록의 응답 규칙은 바꾸지 않는다."""

from fastapi import APIRouter, Depends

from app.collective2.access import require_collective_next

router = APIRouter(prefix="/collective2", tags=["collective2"])


@router.get("/access", dependencies=[Depends(require_collective_next)])
def collective2_access() -> dict:
    return {"ok": True}
