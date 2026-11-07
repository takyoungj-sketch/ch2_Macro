import AnalysisGuide, { type AnalysisGuideContent } from "@ch2/macro-shell/AnalysisGuide";
import { useNarrowScreen } from "@ch2/macro-shell/useNarrowScreen";

const content: AnalysisGuideContent = {
  id: "rent-analysis-guide",
  storageKey: "ch2-macro:hide-rent-analysis-guide",
  title: "임대시장",
  triggerLabel: "임대시장 분석 안내",
  actionLabel: "임대시장 분석 시작하기",
  tagline: "부동산의 임대료와 수익 구조를 통계로 살펴봅니다.",
  summary: "주거용 부동산의 전월세 실거래 자료와 한국부동산원의 상업용 부동산 통계를 통해 임대료 수준, 전월세 관계, 운영수익과 수익률을 분석합니다.",
  features: [
    {
      title: "주거 임대시장",
      description: "아파트·연립다세대·오피스텔·단독다가구의 전세·월세 거래를 분석하고, 전월세전환율과 임대료 수준을 비교합니다.",
    },
    {
      title: "상업 임대시장",
      description: "상업용 부동산의 임대료, 공실률, 순영업소득과 수익률을 지역·상권·건물유형별로 살펴봅니다.",
    },
    {
      title: "시장 비교와 추이",
      description: "지역과 유형별 임대지표를 비교하고, 기간에 따른 변화와 수익성의 차이를 살펴봅니다.",
    },
  ],
  steps: [
    "분석할 부동산 유형과 지역을 선택합니다.",
    "분석기간을 설정하고 통계분석을 눌러 결과를 확인합니다.",
    "주거는 거래 통계와 전월세 관련 지표를, 상업은 상권통계와 수익성 지표를 비교합니다.",
  ],
  notes: [
    "주거 임대통계는 신고된 전월세 거래를 바탕으로 하며, 개별 주택의 임대료나 실제 투자수익을 직접 의미하지 않습니다.",
    "전월세전환율 및 환산 임대료는 계산 방법과 표본 구성에 따라 달라질 수 있습니다.",
    "상업 임대통계는 한국부동산원의 조사·집계 기준에 따른 것으로, 개별 상가의 실제 영업수익이나 투자성과와 차이가 있을 수 있습니다.",
    "주거와 상업의 수익률은 산정 기준이 다를 수 있으므로 직접 비교할 때 주의해야 합니다.",
  ],
};

export default function RentAnalysisGuide() {
  const narrow = useNarrowScreen();
  return narrow ? null : <AnalysisGuide content={content} />;
}
