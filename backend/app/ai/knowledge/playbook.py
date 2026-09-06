"""Intent → CH2 분석 경로 Playbook. LLM이 경로를 지어내지 않음."""

from __future__ import annotations

from typing import Any

# path_id → 안내 (기능은 Product Knowledge 카드와 맞춘다)
PATHS: dict[str, dict[str, Any]] = {
    "collective_cohort": {
        "id": "collective_cohort",
        "label": "집합 코호트",
        "app": "collective",
        "purpose": "같은 단지(또는 도로 cluster) 안에서 동·면적·최근 가격 변화를 묶어서 본다",
        "grain_residential": "단지(building_key)",
        "grain_commercial": "도로명 cluster",
        "requires": ["collective_ui"],
    },
    "collective_integrated_regression": {
        "id": "collective_integrated_regression",
        "label": "집합 통합회귀 (유형 더미)",
        "app": "collective",
        "purpose": "서로 다른 유형의 집합부동산 가격수준을 면적·연식 등을 통제해 비교",
        "requires": ["residential", "two_or_more_asset_types", "type_dummy"],
    },
    "collective_building_regression": {
        "id": "collective_building_regression",
        "label": "집합 단일 단지 회귀",
        "app": "collective",
        "purpose": "한 단지의 층·면적 등 거래 패턴",
        "requires": ["one_building"],
    },
    "regional_regression": {
        "id": "regional_regression",
        "label": "지역회귀",
        "app": "collective",
        "purpose": "단지가 아니라 지역 단위에서 유형·규모 효과를 본다",
        "requires": ["region_scope"],
    },
    "expand_adjacent": {
        "id": "expand_adjacent",
        "label": "인접지역 확대",
        "app": "collective",
        "purpose": "현재 지역 표본이 얇을 때 인접을 넣어 같은 식을 비교",
        "requires": ["prior_regression"],
    },
    "profile_twin": {
        "id": "profile_twin",
        "label": "지역프로필 Twin",
        "app": "profile",
        "purpose": "구조가 닮은 지역을 찾은 뒤 그 지역에서 회귀를 반복",
        "requires": ["profile_app"],
    },
    "built_type_compare": {
        "id": "built_type_compare",
        "label": "복합 통합회귀 (유형 더미)",
        "app": "built",
        "purpose": "상업·단독을 같이 고르고 「유형 더미」를 켠 뒤, 계수 표의 기준 유형 대비 값을 읽는다",
        "requires": ["built_ui", "two_or_more_asset_types", "asset_type_dummy"],
    },
    "built_regression": {
        "id": "built_regression",
        "label": "복합 회귀",
        "app": "built",
        "purpose": "단독·상가·공장 등 개별 건물 거래의 규모·연식 패턴",
        "requires": ["built_ui"],
    },
    "land_matrix": {
        "id": "land_matrix",
        "label": "토지 매트릭스·장기추세",
        "app": "land",
        "purpose": "용도지역×지목 칸의 단가·추이",
        "requires": ["land_ui"],
    },
}

INTENTS: dict[str, dict[str, Any]] = {
    "apartment_officetel_price_gap": {
        "id": "apartment_officetel_price_gap",
        "label": "아파트와 오피스텔 가격수준 비교",
        "keywords": (
            "오피스텔",
            "아파트와",
            "아파트 대비",
            "유형 효과",
            "유형효과",
            "가격 차이",
            "가격차이",
            "가격격차",
            "격차",
        ),
        "need_all": (),  # 키워드 중 격차류 + 유형류는 detect에서 조합
        "paths": [
            "collective_integrated_regression",
            "regional_regression",
            "expand_adjacent",
            "profile_twin",
        ],
        "residential": True,
    },
    "same_complex_price": {
        "id": "same_complex_price",
        "label": "같은 단지 내 가격·동/면적 차이",
        "keywords": ("같은 단지", "단지 내", "이 단지", "동일 전용", "동별", "평형"),
        "paths": ["collective_cohort", "collective_building_regression"],
        "residential": True,
    },
    "recent_price_change": {
        "id": "recent_price_change",
        "label": "최근 가격 변화",
        "keywords": ("최근 가격", "어떻게 변했", "가격이 어떻게 변"),
        "paths": ["collective_cohort", "land_matrix"],
    },
    "similar_region": {
        "id": "similar_region",
        "label": "비슷한 지역",
        "keywords": ("비슷한 단지", "유사 지역", "쌍둥이", "twin"),
        "paths": ["profile_twin", "expand_adjacent"],
    },
    "land_zone_jimok": {
        "id": "land_zone_jimok",
        "label": "토지 용도·지목 시세",
        "keywords": ("용도지역", "지목", "토지 단가"),
        "paths": ["land_matrix"],
    },
    "built_type_price_gap": {
        "id": "built_type_price_gap",
        "label": "복합 상가·단독·공장 가격 비교",
        "keywords": ("상가와 단독", "단독과 상가", "복합 유형"),
        "paths": ["built_type_compare", "built_regression"],
    },
    "built_size_age": {
        "id": "built_size_age",
        "label": "복합 규모·연식",
        "keywords": ("단독", "상가 건물", "공장", "연면적"),
        "paths": ["built_regression"],
    },
}


def path_meta(path_id: str) -> dict[str, Any]:
    return dict(PATHS.get(path_id) or {"id": path_id, "label": path_id})
