"""통계 개념 KB — Statistics Router (템플릿)."""

from __future__ import annotations

STATS_KB: dict[str, str] = {
    "p-value": (
        "p-value(유의확률)는 귀무가설이 참일 때 현재 데이터 이상으로 극단적인 계수가 "
        "나올 확률을 의미합니다. 보통 0.05 미만이면 '통계적으로 유의'하다고 표현하지만, "
        "표본·모형 설정·다중검정에 따라 해석이 달라집니다."
    ),
    "vif": (
        "VIF(분산팽창계수)는 독립변수 간 다중공선성을 봅니다. "
        "보통 10 이상이면 주의, 5~10은 참고 수준입니다. "
        "VIF가 높으면 개별 계수(예: 연식)의 부호·크기가 불안정해질 수 있습니다."
    ),
    "ols": (
        "OLS(최소자승법)는 선형 회귀의 기본 추정법입니다. "
        "종속·독립변수 관계가 선형에 가깝고, 잔차 가정이 크게 깨지지 않을 때 해석이 수월합니다."
    ),
    "adj r": (
        "Adj R²(수정 결정계수)는 변수 개수를 고려해 R²를 조정한 값입니다. "
        "표본 대비 설명력이 어느 정도인지 보는 참고 지표이며, 인과·예측 정확도를 단독으로 보장하지 않습니다."
    ),
    "신뢰구간": (
        "예측 신뢰구간은 모형·표본 불확실성을 반영한 구간입니다. "
        "구간이 넓을수록 표본이 적거나, 잔차 분산이 크거나, 설명변수가 불확실함을 시사합니다."
    ),
}


def answer_statistics_question(message: str) -> str | None:
    lower = message.lower()
    for key, text in STATS_KB.items():
        if key.lower() in lower:
            return text
    if "p값" in message or "p-value" in lower:
        return STATS_KB["p-value"]
    if "다중공선" in message:
        return STATS_KB["vif"]
    return None
