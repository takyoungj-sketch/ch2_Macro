import AnalysisGuide, { type AnalysisGuideContent } from "@ch2/macro-shell/AnalysisGuide";
import { useNarrowScreen } from "@ch2/macro-shell/useNarrowScreen";

const content: AnalysisGuideContent = {
  id: "profile-analysis-guide",
  storageKey: "ch2-macro:hide-profile-analysis-guide",
  title: "지역프로필",
  triggerLabel: "지역프로필 안내",
  actionLabel: "지역프로필 살펴보기",
  tagline: "지역의 부동산 시장을 한눈에 비교합니다.",
  summary: "전국 지역별 거래자료와 인구지표를 활용해 시장 규모, 거래 구성, 가격 분포 및 유사 지역을 살펴봅니다.",
  features: [
    {
      title: "전국 지역 순위와 시장 규모",
      description: "거래금액·거래건수·인구 대비 지표를 통해 지역의 시장 규모와 전국에서의 상대적 위치를 비교합니다.",
    },
    {
      title: "부동산 시장 구성과 가격 특성",
      description: "8대 부동산 시장의 거래 비중을 비교하고, 대표시장과 토지·아파트의 가격 분포를 살펴봅니다.",
    },
    {
      title: "쌍둥이 지역 탐색",
      description: "시장 구성, 인구, 가격 분포 등이 비슷한 지역을 통계적으로 탐색하고 유사도를 비교합니다.",
    },
  ],
  steps: [
    "검색창에서 지역을 찾거나 전국 지역 순위에서 관심 지역을 선택합니다.",
    "거래 현황과 시장 구성, 대표시장의 가격 분포를 확인합니다.",
    "쌍둥이 지역을 선택해 유사 지역을 비교하거나 각 유형의 상세분석으로 이동합니다.",
  ],
  notes: [
    "거래규모와 순위는 실제 신고된 거래를 바탕으로 하며, 지역의 전체 부동산 자산가치나 시장의 우열을 의미하지 않습니다.",
    "대표시장과 가격 분포는 거래 표본의 구성과 기간에 영향을 받으므로 지역 전체의 가격 수준을 단정하기 어렵습니다.",
    "쌍둥이 지역의 유사도는 선택된 지표로 계산한 통계적 유사성입니다. 지역의 모든 특성이 같거나 미래 가격 움직임이 동일하다는 의미는 아닙니다.",
  ],
};

export default function ProfileAnalysisGuide() {
  const narrow = useNarrowScreen();
  return narrow ? null : <AnalysisGuide content={content} />;
}
