"""토지(land) — AI Explain presets."""

from __future__ import annotations

from app.ai.schemas import AnalysisExplain, AnalysisExplainPreset


def land_matrix_regression_explain_from_facts(
    *,
    scope_label: str,
    zone_type: str | None = None,
    land_category: str | None = None,
    model_type: str | None = None,
) -> AnalysisExplain:
    cell = ""
    if zone_type and land_category:
        cell = f" ({zone_type} × {land_category})"
    mt = "log(단가)" if model_type == "log" else "단가(선형)"
    return AnalysisExplain(
        spec_id="land_matrix_regression_v1",
        spec_version="1",
        title="토지 매트릭스 칸 OLS 회귀",
        summary=(
            f"**{scope_label}**{cell} 필터 표본에 대해 {mt} OLS 회귀를 추정합니다. "
            "계수는 선택 필터·기간 내 **통계적 패턴**이며 인과·적정가격을 의미하지 않습니다."
        ),
        formula=f"{mt} ~ 면적·도로·거래유형·지분·연도추세·법정동 FE (칸 필터 동일)",
        interpretation=[
            "Adj R²: 모형이 단가 변동을 설명하는 참고 비율입니다.",
            "유의 계수(p<0.05): 해당 변수와 단가 간 연관이 칸·필터 scope 내에서 관찰됨을 뜻합니다.",
            "법정동 FE·연도추세는 지역·시점 고정효과로, 순수 변수 효과 분리에 도움이 됩니다.",
        ],
        limitations=[
            "매트릭스 칸·필터 조합에 한정된 표본입니다.",
            "표본이 작으면(n<30) 계수 부호·크기가 불안정할 수 있습니다.",
            "감정평가·투자·적정가격 판단이 아닙니다.",
        ],
        presets=[
            AnalysisExplainPreset(
                id="interpret",
                question="이 결과를 어떻게 해석하나요?",
                answer="",
            ),
            AnalysisExplainPreset(
                id="area",
                question="면적 계수는 어떻게 봐야 하나요?",
                answer=(
                    "면적(또는 log 면적) 계수는 다른 변수를 통제한 상태에서 "
                    "면적 1단위 증가와 단가 변화의 **연관**을 뜻합니다. "
                    "log 모형이면 **비율(%)** 해석에 가깝고, 선형 모형이면 **㎡당 단가(만원)** 변화량 해석입니다."
                ),
            ),
        ],
    )


def land_trend_explain(*, scope_label: str, is_long: bool = False) -> AnalysisExplain:
    title = "토지 장기추세" if is_long else "토지 매트릭스 칸 추이"
    return AnalysisExplain(
        spec_id="land_trend_v1",
        spec_version="1",
        title=title,
        summary=(
            f"**{scope_label}** · 선택 용도×지목 칸의 **㎡당 단가·거래량** 구간별 추이입니다. "
            "전망·인과가 아닌 **과거 패턴** 설명입니다."
        ),
        interpretation=[
            "단가: 만원/㎡ 평균(또는 중앙값).",
            "거래량: 해당 구간 valid 거래 건수.",
            "구간 n이 작으면 단가가 요동칠 수 있습니다.",
        ],
        limitations=[
            "필터·이상치 정책은 동일 모달 scope와 공유됩니다.",
            "감정평가·투자·적정가 판단이 아닙니다.",
        ],
        presets=[
            AnalysisExplainPreset(
                id="interpret",
                question="이 결과를 어떻게 해석하나요?",
                answer="",
            ),
            AnalysisExplainPreset(
                id="volume",
                question="거래량 감소 패턴이 보이나요?",
                answer="",
            ),
        ],
    )
