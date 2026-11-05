"""코드 실행 허용 목록. 설명·안내 범위는 도구 목록보다 넓다."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from pydantic import BaseModel
from app.ai3.schemas import FloorArgs, LandArgs, RentArgs, TwinArgs, RegionSearchArgs, TargetSearchArgs


@dataclass(frozen=True)
class Tool:
    id: str
    label: str
    app: str
    source: str
    schema: type[BaseModel]


def tools() -> dict[str, Tool]:
    from app.built.schemas import RegressionPredictRequest
    specs = [
        Tool("regions.search", "행정구역 코드 확인", "land", "/land/", RegionSearchArgs),
        Tool("targets.search", "단지·도로 대상키 확인", "collective", "/collective/", TargetSearchArgs),
        Tool("land.basic_stats", "토지 기본통계·매트릭스", "land", "/land/", LandArgs),
        Tool("built.predict", "복합 예측", "built", "/built/", RegressionPredictRequest),
        Tool("collective.residential.index", "집합 주거 효용지수", "collective", "/collective/", FloorArgs),
        Tool("collective.commercial.index", "집합 비주거 효용지수", "commercial", "/collective/", FloorArgs),
        Tool("rent.conversion", "임대 전환율", "rent", "/rent/", RentArgs),
        Tool("profile.twins", "지역프로필 시군구 Twin", "profile", "/profile/", TwinArgs),
    ]
    return {t.id: t for t in specs}


def validate_arguments(tool_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    spec = tools().get(tool_id)
    if spec is None:
        raise ValueError("실행 도구가 없습니다. 기능 설명과 화면 안내는 가능합니다.")
    unknown = set(arguments) - set(spec.schema.model_fields)
    if unknown:
        raise ValueError("지원하지 않는 조건: " + ", ".join(sorted(unknown)))
    parsed = spec.schema.model_validate(arguments)
    normalized = parsed.model_dump(mode="json")
    if "as_of_month" in normalized and normalized["as_of_month"]:
        from datetime import date
        date.fromisoformat(normalized["as_of_month"])
    def finite(value):
        import math
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("모든 수치 조건은 유한한 숫자여야 합니다.")
        if isinstance(value, dict):
            for child in value.values(): finite(child)
        elif isinstance(value, list):
            for child in value: finite(child)
    finite(normalized)
    if tool_id.startswith("collective."):
        if parsed.year_from > parsed.year_to:
            raise ValueError("시작 연도는 종료 연도보다 클 수 없습니다.")
        if tool_id == "collective.residential.index" and parsed.floor_mode not in ("relative", "rowhouse"):
            raise ValueError("주거 층 모드는 relative 또는 rowhouse입니다.")
        if tool_id == "collective.commercial.index" and parsed.floor_mode == "rowhouse":
            raise ValueError("비주거에 rowhouse 층 모드를 적용할 수 없습니다.")
    if tool_id == "built.predict":
        # 넓은 지역명 기본값으로 추정하지 않으며, 승인 전 모든 기본값도 노출한다.
        if not parsed.addr1 or not parsed.addr2:
            raise ValueError("복합 예측은 시도·시군구의 정확한 행정 경로가 필요합니다.")
        if parsed.admin_level == "eupmyeondong" and len(parsed.addr4_list) != 1:
            raise ValueError("읍면동 예측은 정확한 읍면동 하나를 지정해 주세요.")
        if parsed.admin_level == "sigungu" and (parsed.addr3 or parsed.addr3_list or parsed.addr4_list):
            raise ValueError("시군구 예측에 하위 지역 조건을 섞지 말아 주세요.")
        if parsed.admin_level == "gu" and (not (parsed.addr3 or len(parsed.addr3_list) == 1) or parsed.addr4_list):
            raise ValueError("구 예측은 정확한 구 하나를 지정해 주세요.")
        if not parsed.contract_year_from or not parsed.contract_year_to:
            raise ValueError("복합 예측의 시작·종료 연도를 지정해 주세요.")
        if parsed.contract_year_from > parsed.contract_year_to:
            raise ValueError("시작 연도는 종료 연도보다 클 수 없습니다.")
        if parsed.as_of_month is not None or parsed.window_years is not None:
            raise ValueError("첫 시험의 복합 예측은 명시한 연도 범위만 사용합니다. 기준월·롤링 창은 생략해 주세요.")
        if parsed.enrich or parsed.time_adjust:
            raise ValueError("첫 시험에서는 보강·시점보정을 실행하지 않습니다.")
        if parsed.region_codes or parsed.region_addrs or parsed.ri_list:
            raise ValueError("첫 시험의 복합 예측은 승인 화면에 표시한 addr 행정 경로만 사용합니다.")
        for name in ("gross_area", "land_area", "building_age"):
            value = getattr(parsed, name)
            if value is None or value < 0 or (name != "building_age" and value == 0):
                raise ValueError("연면적·대지면적은 양수, 연식은 영 이상의 값이 필요합니다.")
        import math
        if any(not math.isfinite(getattr(parsed, n)) for n in ("gross_area", "land_area", "building_age")):
            raise ValueError("입력은 유한한 숫자여야 합니다.")
    return normalized


def public_catalog() -> list[dict[str, Any]]:
    return [dict(id=t.id, label=t.label, app=t.app, source=t.source,
                 execution_ready=True, schema=t.schema.model_json_schema()) for t in tools().values()]
