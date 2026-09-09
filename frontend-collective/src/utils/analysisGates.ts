/** 집합 회귀 표본 게이트 — 백엔드 analysis_gates 와 같은 숫자. */

export const MIN_COUNT_REGRESSION_RECOMMENDED = 30;
export const MIN_COUNT_REGRESSION_RUN = 15;
export const MIN_COUNT_REGRESSION_RECENT = 15;

export const REGRESSION_WINDOW_HINT =
  "왼쪽 통계 창을 3·5·7년으로 넓히면 거래 건수가 늘 수 있습니다.";

export function canRunRegression(countTotal: number | undefined | null): boolean {
  if (countTotal == null) return true;
  return countTotal >= MIN_COUNT_REGRESSION_RUN;
}

export function isRegressionRecommended(countTotal: number | undefined | null): boolean {
  if (countTotal == null) return true;
  return countTotal >= MIN_COUNT_REGRESSION_RECOMMENDED;
}

export function isRegressionRecentThin(
  countRecent: number | undefined | null,
  countTotal: number | undefined | null,
): boolean {
  if (countRecent == null) return false;
  if (!canRunRegression(countTotal)) return false;
  return countRecent < MIN_COUNT_REGRESSION_RECENT;
}

export function regressionTabWarns(
  countTotal: number | undefined | null,
  countRecent?: number | undefined | null,
): boolean {
  return !isRegressionRecommended(countTotal) || isRegressionRecentThin(countRecent, countTotal);
}

export function regressionTabTitle(
  countTotal: number | undefined | null,
  countRecent?: number | undefined | null,
): string | undefined {
  if (!canRunRegression(countTotal)) {
    return `거래 ${MIN_COUNT_REGRESSION_RUN}건 미만 — 실행 불가. ${REGRESSION_WINDOW_HINT}`;
  }
  if (!isRegressionRecommended(countTotal)) {
    return `권장 ${MIN_COUNT_REGRESSION_RECOMMENDED}건 미만 — 참고용 실행. ${REGRESSION_WINDOW_HINT}`;
  }
  if (isRegressionRecentThin(countRecent, countTotal)) {
    return `최근 3년 ${MIN_COUNT_REGRESSION_RECENT}건 미만 — 잠금 조건이 아닙니다. 식은 선택한 창 전체입니다.`;
  }
  return undefined;
}

export function regressionGateMessages(messages: string[] | undefined | null): string[] {
  return (messages ?? []).filter((m) => !m.startsWith("층·동 효용지수"));
}

export function regressionRunLabel(opts: {
  pending: boolean;
  useCohort: boolean;
  hasResult: boolean;
  canRun: boolean;
  recommended: boolean;
}): string {
  if (opts.pending) return "실행 중…";
  if (opts.useCohort) return opts.hasResult ? "통합 회귀 다시 실행" : "통합 회귀 실행";
  if (!opts.canRun) return `거래 ${MIN_COUNT_REGRESSION_RUN}건 미만 — 실행 불가`;
  if (!opts.recommended) return "참고용으로 실행";
  return "회귀 실행";
}
