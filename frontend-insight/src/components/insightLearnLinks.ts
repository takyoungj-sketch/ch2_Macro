/** Macro Insight 본문 → ch2data.com/learn/stats/ 역링크 SSOT */
const LEARN_BASE = "https://ch2data.com/learn/stats";

export type InsightLearnChapter = {
  slug: string;
  label: string;
  anchor?: string;
};

/** FAQ q 번호(문자열) → 관련 Learn 장 */
export const INSIGHT_LEARN_BY_Q: Record<string, InsightLearnChapter[]> = {
  "1": [
    { slug: "correlation", label: "상관관계" },
    { slug: "sample-size", label: "표본수와 신뢰성" },
    { slug: "reading-results", label: "통계 결과 읽기" },
  ],
  "2": [
    { slug: "correlation", label: "상관관계" },
    { slug: "reading-results", label: "통계 결과 읽기" },
  ],
  "3": [
    { slug: "correlation", label: "상관관계" },
    { slug: "quantiles", label: "분위수" },
    { slug: "reading-results", label: "통계 결과 읽기" },
  ],
  "4": [
    { slug: "correlation", label: "상관관계" },
    { slug: "reading-results", label: "통계 결과 읽기" },
  ],
  "5": [
    { slug: "correlation", label: "상관관계" },
    { slug: "reading-results", label: "통계 결과 읽기" },
  ],
  "6": [
    { slug: "regression", label: "회귀분석" },
    { slug: "reading-results", label: "통계 결과 읽기" },
  ],
  "7": [
    { slug: "spread", label: "분산과 표준편차" },
    { slug: "reading-results", label: "통계 결과 읽기" },
  ],
  "8": [
    { slug: "data-and-variables", label: "데이터와 변수" },
    { slug: "reading-results", label: "통계 결과 읽기" },
  ],
  "9": [
    { slug: "regression", label: "회귀분석" },
    { slug: "quantiles", label: "분위수" },
    { slug: "reading-results", label: "통계 결과 읽기" },
  ],
  "10": [
    { slug: "regression", label: "회귀분석" },
    { slug: "quantiles", label: "분위수" },
    { slug: "reading-results", label: "통계 결과 읽기" },
  ],
  "11": [
    { slug: "correlation", label: "상관관계" },
    { slug: "reading-results", label: "통계 결과 읽기" },
  ],
};

export function insightLearnUrl(ch: InsightLearnChapter): string {
  const base = `${LEARN_BASE}/${ch.slug}/`;
  return ch.anchor ? `${base}#${ch.anchor}` : base;
}

export function insightLearnChapters(q: string | null): InsightLearnChapter[] {
  if (!q) return [];
  return INSIGHT_LEARN_BY_Q[q] ?? [{ slug: "reading-results", label: "통계 결과 읽기" }];
}
