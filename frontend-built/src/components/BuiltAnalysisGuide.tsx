import AnalysisGuide, { type AnalysisGuideContent } from "@ch2/macro-shell/AnalysisGuide";
import { useNarrowScreen } from "@ch2/macro-shell/useNarrowScreen";

const content: AnalysisGuideContent = {
  id: "built-analysis-guide",
  storageKey: "ch2-macro:hide-built-analysis-guide",
  title: "복합부동산",
  triggerLabel: "복합 분석 안내",
  actionLabel: "복합 분석 시작하기",
  tagline: "거래자료로 부동산의 가격 형성 요인을 분석합니다.",
  summary: "상업용·공장창고·단독다가구 부동산의 실거래 자료를 바탕으로, 토지와 건물의 특성이 거래가격에 미치는 통계적 영향을 살펴봅니다.",
  features: [
    {
      title: "기본회귀",
      description: "지역과 분석기간, 면적·연식·도로조건 등의 변수를 직접 선택해 가격과의 통계적 관계를 분석합니다.",
    },
    {
      title: "모형추천",
      description: "여러 변수 조합과 회귀모형의 검증 결과를 비교해 분석 목적에 적합한 모형을 탐색합니다.",
    },
    {
      title: "상위지역회귀",
      description: "선택 지역의 거래자료가 부족할 때 분석 범위를 상위 행정구역으로 넓혀 표본을 확보하고 결과를 비교합니다.",
    },
  ],
  steps: [
    "부동산 유형과 지역, 분석기간을 선택합니다.",
    "기본회귀에서 분석 변수와 모형을 설정하거나 모형추천을 이용합니다.",
    "표본이 부족하다면 상위지역회귀를 검토하고, 검증오차·계수·표본 수 등을 비교합니다.",
  ],
  notes: [
    "토지와 건물의 개별 특성 및 거래 조건에 따라 가격 차이가 발생할 수 있습니다.",
    "표본이 적거나 편중되면 회귀계수와 예측 결과가 불안정해질 수 있으며, 모형추천이 항상 정확한 결과를 보장하지는 않습니다.",
    "상위지역 자료를 포함하면 표본은 증가하지만 지역 간 가격 형성 구조의 차이로 분석 결과가 달라질 수 있습니다.",
    "회귀 결과는 통계적 참고자료이며, 개별 부동산의 적정가격이나 미래 거래가격을 직접 의미하지 않습니다.",
  ],
};

export default function BuiltAnalysisGuide() {
  const narrow = useNarrowScreen();
  return narrow ? null : <AnalysisGuide content={content} />;
}
