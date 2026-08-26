/** D-051 동의 문장. 백엔드 `app.built.enrichment_policy.NOTICE` 와 같아야 한다. */

export const ENRICH_NOTICE = [
  "계약 2019년 이후 거래의 75.0%만 건축물대장과 연결됩니다.",
  "표제부는 계약 시점이 아닌 이후 대장(2024-09·2025-07·2026-07) 기준이며, 최대 7년 6개월 차이가 날 수 있습니다.",
  "필지에 용도지역이 여럿이면 빈도 최다 대표 1개만 씁니다(2019년 이후 거래 기준 49.4%).",
  "매칭 정확도 인증은 서울·충북뿐입니다. 다른 시도는 같은 규칙을 씁니다.",
] as const;

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
