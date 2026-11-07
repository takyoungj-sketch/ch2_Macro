/** 공개 목록 순서. q가 화면에 보이는 번호다. panel은 글 파일의 예전 번호다. */
import catalog from "../../shared/insight-catalog.json";
export const INSIGHT_ORDER = catalog;

export function insightPanel(q: string | null): string {
  return INSIGHT_ORDER.find((item) => item.q === q)?.panel ?? "InsightHome";
}
