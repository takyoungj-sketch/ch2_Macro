/** 공개 목록 순서. q가 화면에 보이는 번호다. panel은 글 파일의 예전 번호다. */
export const INSIGHT_ORDER: { q: string; panel: string }[] = [
  { q: "1", panel: "Insight05" },
  { q: "2", panel: "Insight01" },
  { q: "3", panel: "Insight02" },
  { q: "4", panel: "Insight11" },
  { q: "5", panel: "Insight12" },
  { q: "6", panel: "Insight07" },
  { q: "7", panel: "Insight04" },
  { q: "8", panel: "Insight06" },
  { q: "9", panel: "Insight08" },
  { q: "10", panel: "Insight03" },
  { q: "11", panel: "Insight10" },
];

export function insightPanel(q: string | null): string {
  return INSIGHT_ORDER.find((item) => item.q === q)?.panel ?? "InsightHome";
}
