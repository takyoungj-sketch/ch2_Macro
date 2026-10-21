/** D-051 동의 문장. 백엔드 `app.built.enrichment_policy.NOTICE` · `MATCH_RATE` 와 같아야 한다. */

export const ENRICH_NOTICE = [
  "이 버튼은 통합 대장에서 부족한 항목을 채웁니다. 상업·공장은 건축물 구조를, 단독·다가구는 계약연도 용도지역을 채웁니다. 개별공시지가는 회귀 변수로 넣을 수 있습니다.",
  "모든 거래를 완벽하게 맞추기는 어려울 수 있습니다. 오류를 줄이기 위해, 연결되지 않은 건은 보강하지 않고 실거래 자료를 그대로 보여 줍니다.",
] as const;

export const ENRICH_MATCH_RATE = "현재 매칭률 75.0% (계약 2019년 이후)";

export const ENRICH_LIST_BADGE = "건축물대장 확인";

/** 백엔드 `MATCH_RULE_LABELS` 와 같아야 한다. */
export const MATCH_RULE_LABELS: Record<string, string> = {
  gross_exact: "법정동·연면적 일치",
  gross_exact_land_tiebreak: "법정동·연면적 일치, 대지면적으로 동률 해소",
};

export function isBuiltTitleMatch(tier?: string | null): boolean {
  const t = (tier ?? "").trim();
  return t === "A1" || t === "A2";
}

export function builtMatchHoverTitle(
  tier?: string | null,
  rule?: string | null,
): string {
  const ruleKey = (rule ?? "").trim();
  const ruleLabel = MATCH_RULE_LABELS[ruleKey] || ruleKey;
  const parts = [ENRICH_LIST_BADGE];
  if (ruleLabel) parts.push(ruleLabel);
  const t = (tier ?? "").trim();
  if (t) parts.push(t);
  return parts.join(" — ");
}
