/** 통계분석 mart 창 또는 연도 필터 → API period 파라미터 */

export type AnalysisPeriodParams = {
  contract_date_from?: string;
  contract_date_to?: string;
  contract_year_from?: number;
  contract_year_to?: number;
};

export function buildAnalysisPeriodParams(
  yearFrom?: number,
  yearTo?: number,
  periodStart?: string | null,
  periodEnd?: string | null,
): AnalysisPeriodParams {
  if (yearFrom != null || yearTo != null) {
    return {
      contract_year_from: yearFrom,
      contract_year_to: yearTo,
    };
  }
  if (periodStart && periodEnd) {
    return {
      contract_date_from: periodStart,
      contract_date_to: periodEnd,
    };
  }
  return {};
}

export function formatPeriodLabel(periodStart?: string | null, periodEnd?: string | null): string | null {
  if (!periodStart || !periodEnd) return null;
  return `${periodStart} ~ ${periodEnd}`;
}
