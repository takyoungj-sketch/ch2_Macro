/** 회귀 예측 결과 카드 언어 — D-069. AVM 선언은 결과 카드에서 한 번만. */

export type EstimateRangeSubject = "거래" | "단지" | "필지";

export const ESTIMATE_COPY = {
  valueLabel: "통계적 추정값",
  valueCaption: "선택한 거래자료와 회귀모형에서 추정된 통계적 중심값입니다.",
  meanRangeLabel: "95% 평균 추정범위",
  meanRangeHint: "이 조건에서 평균적인 가격수준을 추정한 범위",
  avmOnce:
    "이 값은 AVM이나 감정평가액이 아닙니다. 선택한 거래자료에서 나타나는 가격관계를 회귀모형으로 추정한 통계적 참고값입니다.",
  howToUse:
    "실제 대상물건의 가액은 모형에 포함되지 않은 개별 특성이나 거래조건 등에 의해 추정값과 달라질 수 있습니다. 개별 물건의 가격을 판단하기보다는, 해당 지역에서 관찰되는 가격수준과 변수 간 관계를 파악하는 데 활용하세요.",
  rangeFootnote:
    "※ 위 범위는 회귀모형의 통계적 불확실성을 나타내며, 실제 대상물건의 가액을 보증하는 범위가 아닙니다.",
} as const;

export function individualRangeLabel(subject: EstimateRangeSubject = "거래"): string {
  return `95% 개별 ${subject} 예측범위`;
}

export function individualRangeHint(subject: EstimateRangeSubject = "거래"): string {
  if (subject === "단지") return "개별 단지 가격의 변동까지 고려한 통계적 범위";
  if (subject === "필지") return "개별 필지 가격의 변동까지 고려한 통계적 범위";
  return "개별 거래가격의 변동까지 고려한 통계적 범위";
}
