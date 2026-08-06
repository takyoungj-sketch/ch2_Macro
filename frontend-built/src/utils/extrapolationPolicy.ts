import type { ContinuousExtrapolation, ResponseScale } from "../types";

export type ExtrapolationLevel = 0 | 1 | 2 | 3 | 4;

const VAR_UNITS: Record<string, string> = {
  gross_area: "㎡",
  land_area: "㎡",
  building_age: "년",
  road_code: "m",
};

export function extrapolationBadge(level: number): { label: string; className: string } | null {
  if (level <= 1) return null;
  if (level === 2) {
    return { label: "외삽 주의", className: "text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40" };
  }
  if (level === 3) {
    return { label: "참고용", className: "text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-950/40" };
  }
  return { label: "극단 외삽", className: "text-red-800 dark:text-red-300 bg-red-100 dark:bg-red-950/60" };
}

export function inputBorderClass(level: number): string {
  if (level <= 1) return "";
  if (level === 2) return "border-amber-400 dark:border-amber-600";
  return "border-red-400 dark:border-red-600";
}

export function assessmentForName(
  assessments: ContinuousExtrapolation[] | undefined,
  name: string,
): ContinuousExtrapolation | undefined {
  return assessments?.find((a) => a.name === name);
}

export function shouldHidePrediction(level: number, scale: ResponseScale | undefined): boolean {
  return (level ?? 0) >= 4 && scale === "log";
}

export function formatTrainingRange(lo: number, hi: number, name?: string): string {
  const unit = name ? (VAR_UNITS[name] ?? "") : "";
  return `${Math.round(lo).toLocaleString("ko-KR")}~${Math.round(hi).toLocaleString("ko-KR")}${unit}`;
}

/** 변수별 외삽 — 사용자용 설명 문구 */
export function describeExtrapolation(a: ContinuousExtrapolation): string {
  const range = formatTrainingRange(a.min, a.max, a.name);
  const label = a.label || a.name;

  if (a.level === 1) {
    return `${label}이(가) 학습 범위(${range})를 약간 벗어났습니다. 예측값은 참고하되 해석에 유의하세요.`;
  }
  if (a.level === 2) {
    return `${label} 학습 범위(${range})를 벗어난 입력입니다. 예측값 해석에 주의하세요.`;
  }
  if (a.level === 3) {
    return `${label} 학습 범위(${range})를 크게 벗어난 예측입니다. 예측에 주의가 필요합니다.`;
  }
  return `${label} 학습 범위(${range})를 극단적으로 벗어났습니다. 예측 숫자는 신뢰하기 어렵습니다.`;
}

/** 예측 결과 카드용 — 기술적 L3/L4 문구 대신 표시 */
export function buildExtrapolationGuidance(
  assessments: ContinuousExtrapolation[] | undefined,
  aggregateLevel: number,
): string[] {
  if (!assessments?.length) return [];
  const sorted = [...assessments].sort((a, b) => b.level - a.level);
  const lines = sorted.filter((a) => a.level >= 2).map(describeExtrapolation);
  if (!lines.length) {
    return sorted.map(describeExtrapolation);
  }
  if (aggregateLevel >= 3 && sorted.length > 1) {
    return [
      "입력값이 학습 범위를 벗어난 변수가 여러 개 있습니다. 아래 안내를 확인하세요.",
      ...lines,
    ];
  }
  return lines;
}

/** API warnings 중 UI에서 대체하는 기술적 외삽 문구 */
export function isTechnicalExtrapolationWarning(message: string): boolean {
  return (
    message.startsWith("외삽 L") ||
    message.includes("학습 범위를 크게 벗어난") ||
    message.startsWith("극단 외삽 — semi-log")
  );
}

export const RESPONSE_SCALE_LABELS: Record<ResponseScale, string> = {
  linear: "선형",
  log: "log (semi-log)",
  loglog: "log-log",
};
