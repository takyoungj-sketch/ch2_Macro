"""전체 기능 지도와 질문별 기존 제품 지식. 제품 코드와 출처를 공유한다."""
from __future__ import annotations

from app.ai.knowledge.product import (
    APP_STRUCTURE, PRODUCT_OVERVIEW, DATA_PIPELINE, REGRESSION_LOGIC,
    product_knowledge_pack, format_domain_card, format_howto_answer,
)
from app.ai3.schemas import Evidence

DOMAINS = {
    "land": ("토지", "필지", "지목", "용도지역"),
    "built": ("복합", "단독", "모형추천", "보강"),
    "collective": ("집합", "아파트", "오피스텔", "층별", "단지", "코호트", "상가", "공장"),
    "rent": ("임대", "전환율", "전세", "월세", "상권"),
    "profile": ("프로필", "쌍둥이", "twin", "전국 순위"),
    "insight": ("insight", "인사이트", "실험 기록"),
}

STATS = {
    "설명력": "설명력은 적합한 표본 안의 변동을 모형이 얼마나 설명하는지 나타냅니다. 새 자료의 예측 성능은 별도 검증이 필요하며 교차검증이나 홀드아웃 오차를 함께 확인해야 합니다.",
    "r²": "R²는 표본 내 변동 중 모형이 설명한 비중입니다. 변수를 늘리면 높아질 수 있으므로 수정 R²와 표본 밖 예측 오차도 함께 봅니다. 인과관계를 뜻하지 않습니다.",
    "mape": "MAPE는 실제값 대비 절대 예측 오차의 평균입니다. 실제값이 작으면 민감하고, 적합 표본의 오차와 교차검증 오차는 구분해야 합니다.",
    "vif": "VIF는 설명변수 사이의 선형 중복 정도를 진단합니다. 높으면 계수의 불확실성이 커질 수 있지만 그것만으로 변수 제거를 자동 결정하지 않습니다.",
    "p-value": "p-value는 귀무가설과 모형 가정 아래 관측한 결과 이상으로 극단적인 결과가 나올 가능성입니다. 귀무가설이 참일 확률이나 효과 크기가 아닙니다.",
    "신뢰구간": "신뢰구간은 정해진 조건의 평균 반응 추정 불확실성을, 예측구간은 새 관측값의 불확실성을 나타냅니다. 같은 조건에서 예측구간이 보통 더 넓습니다.",
    "예측구간": "예측구간은 새 관측값의 불확실성을 포함합니다. 개별 적정가격 범위를 확정하는 도구가 아니며 외삽과 표본 구성을 함께 확인해야 합니다.",
    "로그": "로그 모형은 비율 관계와 분산 변화를 다루는 데 유용합니다. 원척도 예측의 평균을 얻을 때 단순 지수 역변환과 재변환 편향 보정을 구분해야 합니다. CH2의 보정 방식은 모형과 화면 설정을 확인합니다.",
    "표본": "표본 수와 함께 지역·유형·기간의 구성, 변수 결측으로 제외된 건수, 범주별 관측 수를 확인해야 합니다. 실행 가능 여부는 엔진 게이트가 판정합니다.",
    "상관": "상관은 변수들이 함께 움직이는 정도입니다. 시기·지역·다른 변수의 영향을 통제한 인과 효과와 구별해야 합니다.",
    "회귀": "회귀는 다른 설명변수를 통제한 조건부 패턴을 추정합니다. 계수의 방향·단위·기준 범주·표본과 모형 가정을 함께 읽으며 인과관계로 단정하지 않습니다.",
    "평균": "평균은 전체 합을 관측 수로 나눈 수준이고 중앙값은 순서의 가운데 수준입니다. 분포가 비대칭이거나 이상치가 있으면 차이가 커질 수 있습니다.",
}


def retrieve(message: str, app: str) -> tuple[str, list[Evidence]]:
    lower = message.lower()
    matches = [d for d, keys in DOMAINS.items() if any(k in lower for k in keys)]
    current = "collective" if app == "commercial" else app
    domains = list(dict.fromkeys(matches + [current]))[:3]
    parts = [PRODUCT_OVERVIEW, APP_STRUCTURE]
    evidence = [Evidence(id="product", label="CH2 제품 지식·전체 기능 지도", source="backend/app/ai/knowledge/product.py")]
    for domain in domains:
        parts.append(product_knowledge_pack(app=domain))
        evidence.append(Evidence(id=domain, label=f"{domain} 제품 방법·화면 안내", source="backend/app/ai/knowledge/product.py"))
    if any(k in lower for k in ("수집", "데이터", "정제", "출처")):
        parts.append(DATA_PIPELINE)
    if any(k in lower for k in ("회귀", "로그", "검증", "예측", "설명력", "mape")):
        parts.append(REGRESSION_LOGIC)
    parts.append("일반 통계 설명:\n" + "\n".join(STATS.values()))
    evidence.append(Evidence(id="statistics", label="일반 통계 원리 (실측 수치와 구별)", source="backend/app/ai3/knowledge.py"))
    return "\n\n".join(parts)[:28000], evidence


def offline_answer(message: str, app: str) -> str:
    lower = message.lower()
    if any(x in lower for x in ("안녕", "hello")):
        return "CH2 Macro의 기능·데이터·통계 방법을 설명하고, 조건을 확인해 분석을 실행할 수 있습니다."
    if any(x in message for x in ("어디", "누르", "사용법", "화면")):
        # 다른 앱에서 질문하더라도 요청한 기능의 도메인을 먼저 선택한다.
        relevant = "rent" if any(k in lower for k in ("전환율", "전세", "월세")) else next((d for d, keys in DOMAINS.items() if any(k in lower for k in keys)), app)
        howto = format_howto_answer(relevant, message)
        if howto:
            return howto
    for key, answer in STATS.items():
        if key in lower:
            return answer
    matched = [format_domain_card(d) for d, keys in DOMAINS.items() if any(k in lower for k in keys)]
    return "\n\n".join(matched[:2]) if matched else PRODUCT_OVERVIEW.strip() + "\n" + APP_STRUCTURE.strip()
