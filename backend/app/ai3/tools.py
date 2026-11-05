"""제품 라우터/엔진 재사용. AI2 픽스처나 자유 SQL 실행 경로 없음."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Any
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.ai3.catalog import validate_arguments


@contextmanager
def database(domain: str):
    if domain == "land":
        from app.db import engine
    elif domain == "built":
        from app.built.db import get_built_engine
        engine = get_built_engine()
    elif domain == "rent":
        from app.rent.db import get_rent_engine
        engine = get_rent_engine()
    else:
        from app.collective.db import get_collective_engine
        engine = get_collective_engine()
    if engine is None:
        raise HTTPException(503, "이 분석의 DB 연결이 설정되지 않았습니다.")
    with Session(engine) as db:
        # SET TRANSACTION은 첫 쿼리여야 한다. raw 거래는 이 세션 밖으로 내보내지 않는다.
        db.execute(text("SET TRANSACTION READ ONLY"))
        db.execute(text("SET LOCAL statement_timeout = '90s'"))
        yield db


def run_tool(tool_id: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    args = validate_arguments(tool_id, arguments)
    limits: list[str] = []
    if tool_id == "regions.search":
        with database("land") as db:
            rows = db.execute(text("""
                SELECT DISTINCT beopjungri_code, sigungu_code, sido_name, sigungu_name,
                       eupmyeondong_name, beopjungri_name
                FROM region_codes
                WHERE sigungu_name = :name OR eupmyeondong_name = :name OR beopjungri_name = :name
                ORDER BY beopjungri_code LIMIT 21
            """), {"name": args["name"]}).mappings().all()
        if not rows:
            raise HTTPException(404, "같은 이름의 행정구역이 없습니다. 공식 명칭으로 입력해 주세요.")
        raw = {"matches": [dict(r) for r in rows[:20]], "truncated": len(rows) > 20}
        limits.append("동명이 지역은 상위 행정경로와 코드로 구별해 선택해 주세요.")
    elif tool_id == "targets.search":
        commercial = args["domain"] == "commercial"
        table = "collective_commercial_transactions" if commercial else "collective_transactions"
        key = "cluster_key" if commercial else "building_key"
        name = "road_name" if commercial else "display_name"
        with database("collective") as db:
            rows = db.execute(text(f"""
                SELECT {key} AS target_key, MAX({name}) AS name, COUNT(*)::int AS n
                FROM {table}
                WHERE is_valid = true AND addr1 = :a1 AND addr2 = :a2 AND addr4 = :a4
                  AND position(:name in {name}) > 0
                GROUP BY {key} ORDER BY n DESC LIMIT 21
            """), dict(a1=args["addr1"], a2=args["addr2"], a4=args["addr4"], name=args["name"])).mappings().all()
        if not rows:
            raise HTTPException(404, "정확한 행정경로에서 해당 이름의 대상을 찾지 못했습니다.")
        raw = {"matches": [dict(r) for r in rows[:20]], "truncated": len(rows) > 20}
        limits.append("여기 건수는 대상 검색용 전체 거래 건수입니다. 분석 표본 게이트는 승인 기간으로 다시 확인합니다.")
    elif tool_id == "land.basic_stats":
        from app.routers.free_v2 import get_basic_stats_v2
        with database("land") as db:
            raw = get_basic_stats_v2(db=db, **{**args, "as_of_month": date.fromisoformat(args["as_of_month"])})
    elif tool_id == "built.predict":
        from app.built.schemas import RegressionPredictRequest
        from app.built.router import regression_predict
        with database("built") as db:
            raw = regression_predict(RegressionPredictRequest.model_validate(args), db=db)
        limits.append("과거 거래에 적합한 통계적 예측이며 개별 적정가격이 아닙니다.")
    elif tool_id.startswith("collective."):
        common = dict(contract_year_from=args["year_from"], contract_year_to=args["year_to"],
                      dimension=args["dimension"], floor_mode=args["floor_mode"], experiment=False)
        with database("collective") as db:
            if tool_id == "collective.residential.index":
                from app.collective.router import building_floor_index
                raw = building_floor_index(building_key=args["target_key"], db=db,
                                           contract_date_from=None, contract_date_to=None, **common)
            else:
                from app.collective_commercial.router import cluster_floor_index
                raw = cluster_floor_index(cluster_key=args["target_key"], db=db, addr1=None,
                                          addr2=None, addr3_list=[], addr4_list=[], **common)
        limits.append("단지 또는 도로명 cluster의 지수이며 다른 모집단의 Insight 지수와 합치지 않습니다.")
    elif tool_id == "rent.conversion":
        from app.rent.conversion_query import list_conversion_compare
        with database("rent") as db:
            items = list_conversion_compare(db.connection(), as_of=date.fromisoformat(args["as_of_month"]),
                                            addr1=args["addr1"], asset_types=[args["asset_type"]],
                                            window_years=[args["window_years"]])
        items = [item for item in items if item.addr2 == args["addr2"]]
        if not items:
            raise HTTPException(404, "지정한 지역·유형·기준월·기간의 전환율이 없습니다.")
        if len(items) != 1:
            raise HTTPException(409, "같은 조건의 전환율이 둘 이상입니다. 데이터 배치를 확인해야 합니다.")
        if not items[0].gate_passed or items[0].r_selected is None:
            raise HTTPException(422, "지정 조건은 전환율 표본 게이트를 통과하지 못했습니다.")
        raw = dict(as_of_month=args["as_of_month"], **items[0].model_dump(mode="json"))
        limits.append("분석용 전환율이며 전세 시세가 아닙니다.")
    elif tool_id == "profile.twins":
        from app.regional_profile.router import get_profile_twin_sigungu
        with database("collective") as db:
            raw = get_profile_twin_sigungu(db=db, **args)
        if raw.window_years != args["window_years"]:
            raise HTTPException(422, "제품 서비스가 다른 기간으로 대체했습니다. 새 기간을 지정하고 다시 승인해 주세요.")
        if not raw.neighbors:
            raise HTTPException(404, "해당 프로필·기간·범위의 Twin 배치가 없습니다.")
        limits.append("쌍둥이는 결론으로 쓰지 않음. 회귀 pool 채택이나 투자 추천이 아닙니다.")
    else:
        raise HTTPException(422, "지원하지 않는 도구입니다.")
    result = raw.model_dump(mode="json") if hasattr(raw, "model_dump") else raw
    # 외삽 중심값은 클라이언트·LLM 양쪽에서 보이지 않게 제거한다.
    if result.get("y_hat_suppressed"):
        result["y_hat"] = None
        limits.append("외삽으로 중심값을 숨겼습니다. 예측구간과 엔진 경고를 확인하세요.")
    for warning in result.get("warnings") or []:
        if isinstance(warning, str):
            limits.append(warning)
    explain = result.get("explain") or {}
    limits.extend(x for x in explain.get("limitations", []) if isinstance(x, str))
    return result, list(dict.fromkeys(limits))
