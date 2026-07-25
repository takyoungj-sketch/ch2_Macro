// build_twin_hybrid.py / build_twin_sigungu_hybrid.py detail_scores.reason_codes (D-023b)
export const REASON_CODE_LABELS: Record<string, string> = {
  LAND_STRUCT_STRONG: "토지 용도·지목 구조가 매우 유사",
  LAND_STRUCT_SIMILAR: "토지 용도·지목 구조가 유사",
  LAND_PRICE_STRONG: "토지 단가 수준이 매우 유사",
  LAND_PRICE_SIMILAR: "토지 단가 수준이 유사",
  COLL_PATTERN_STRONG: "집합부동산 거래 패턴이 매우 유사",
  COLL_PATTERN_SIMILAR: "집합부동산 거래 패턴이 유사",
  COLL_PRICE_STRONG: "집합부동산 단가 수준이 매우 유사",
  COLL_PRICE_SIMILAR: "집합부동산 단가 수준이 유사",
  POP_STRONG: "인구 규모가 매우 유사",
  POP_SIMILAR: "인구 규모가 유사",
};

export function reasonLabel(code: string): string {
  return REASON_CODE_LABELS[code] ?? code;
}
