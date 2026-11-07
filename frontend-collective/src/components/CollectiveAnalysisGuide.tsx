import AnalysisGuide, { type AnalysisGuideContent } from "@ch2/macro-shell/AnalysisGuide";

const guides: Record<"residential" | "commercial", AnalysisGuideContent> = {
  residential: {
    id: "collective-residential-analysis-guide",
    storageKey: "ch2-macro:hide-collective-residential-analysis-guide",
    title: "주거형 집합부동산",
    triggerLabel: "주거 분석 안내",
    actionLabel: "주거 분석 시작하기",
    tagline: "지역과 거래조건에 따라 주거형 집합부동산 시장을 분석합니다.",
    summary: "아파트·연립다세대·오피스텔·분양권 등의 실거래 자료를 건물·단지 단위로 묶어 가격 수준과 거래 특성을 살펴볼 수 있습니다.",
    features: [
      {
        title: "기본통계",
        description: "선택한 유형과 지역의 건물·단지별 거래량, 가격 수준과 분포를 비교합니다.",
      },
      {
        title: "조건별 분석",
        description: "부동산 유형과 분석기간을 선택하고, 층·동·면적 등 다양한 조건에 따른 가격 차이를 살펴봅니다.",
      },
      {
        title: "상세분석",
        description: "거래목록과 기간별 추이를 확인하고, 층·동·면적 효용지수 및 회귀분석을 통해 가격 차이와 통계적 관계를 탐색합니다.",
      },
    ],
    steps: [
      "분석할 부동산 유형, 지역, 분석기간을 선택합니다.",
      "통계분석을 눌러 건물·단지별 거래 통계를 확인합니다.",
      "목록에서 건물·단지를 선택해 상세분석을 열거나, 지역회귀를 통해 여러 단지의 가격 형성 요인을 분석합니다.",
    ],
    notes: [
      "같은 건물·단지라도 거래 시기, 층, 동, 면적 및 개별 특성에 따라 가격 차이가 발생할 수 있습니다.",
      "거래 건수가 적거나 특정 조건에 표본이 편중되면 효용지수와 회귀분석 결과의 안정성이 낮아질 수 있습니다.",
      "평균·중앙단가와 통계모형의 추정 결과는 시장을 이해하기 위한 참고자료입니다. 개별 호의 적정가격이나 미래 거래가격을 직접 나타내지는 않습니다.",
    ],
  },
  commercial: {
    id: "collective-commercial-analysis-guide",
    storageKey: "ch2-macro:hide-collective-commercial-analysis-guide",
    title: "상업·업무 집합부동산",
    triggerLabel: "비주거 분석 안내",
    actionLabel: "비주거 분석 시작하기",
    tagline: "지역과 거래조건에 따라 비주거형 집합부동산 시장을 분석합니다.",
    summary: "집합상가·집합공장 등의 실거래 자료를 도로명별 거래 묶음으로 구분하여 가격 수준과 거래 특성을 살펴볼 수 있습니다.",
    features: [
      {
        title: "기본통계",
        description: "선택한 유형과 지역의 도로명별 거래량, 가격 수준과 분포를 비교합니다.",
      },
      {
        title: "조건별 분석",
        description: "부동산 유형과 분석기간을 선택하고, 층·면적 등 다양한 조건에 따른 가격 차이를 살펴봅니다.",
      },
      {
        title: "상세분석",
        description: "거래목록과 기간별 추이를 확인하고, 층·면적 효용지수 및 회귀분석을 통해 가격 차이와 통계적 관계를 탐색합니다.",
      },
    ],
    steps: [
      "분석할 부동산 유형, 지역, 분석기간을 선택합니다.",
      "통계분석을 눌러 도로명별 거래 통계를 확인합니다.",
      "목록에서 도로명별 거래 묶음을 선택해 상세분석을 열고, 효용지수와 회귀분석으로 가격 차이와 통계적 관계를 살펴봅니다.",
    ],
    notes: [
      "같은 도로명별 거래 묶음에도 서로 다른 건물과 호가 포함됩니다. 거래 시기, 층, 면적 및 개별 특성에 따라 가격 차이가 발생할 수 있습니다.",
      "거래 건수가 적거나 특정 조건에 표본이 편중되면 효용지수와 회귀분석 결과의 안정성이 낮아질 수 있습니다.",
      "평균·중앙단가와 통계모형의 추정 결과는 시장을 이해하기 위한 참고자료입니다. 개별 호의 적정가격이나 미래 거래가격을 직접 나타내지는 않습니다.",
    ],
  },
};

export default function CollectiveAnalysisGuide({ kind }: { kind: "residential" | "commercial" }) {
  return <AnalysisGuide content={guides[kind]} />;
}
