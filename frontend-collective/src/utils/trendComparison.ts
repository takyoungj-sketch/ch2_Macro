import type { YearlyStatsResponse } from "../types";

/** 비교 대상별 실패를 분리하고 성공한 연도별 자료는 유지한다. */
export async function loadYearlyComparisons(
  targets: Array<{ key: string; label: string }>,
  fetchYearly: (key: string) => Promise<YearlyStatsResponse>,
): Promise<{ series: YearlyStatsResponse[]; failed: string[] }> {
  const results = await Promise.allSettled(targets.map(async target => {
    const data = await fetchYearly(target.key);
    return { ...data, display_name: target.label || data.display_name };
  }));
  const series: YearlyStatsResponse[] = [];
  const failed: string[] = [];
  results.forEach((result, i) => {
    if (result.status === "fulfilled") series.push(result.value);
    else failed.push(targets[i].label || targets[i].key);
  });
  return { series, failed };
}

export function trendAxisOrders(orders: number[], annual: boolean): number[] {
  const sorted = [...new Set(orders)].sort((a, b) => a - b);
  if (!annual || sorted.length < 2) return sorted;
  return Array.from({ length: sorted[sorted.length - 1] - sorted[0] + 1 }, (_, i) => sorted[0] + i);
}

/** 값을 보충하지 않고 연속된 관측점만 같은 선으로 연결한다. */
export function consecutiveTrendSegments<T extends { xOrder: number }>(points: T[]): T[][] {
  const segments: T[][] = [];
  for (const point of [...points].sort((a, b) => a.xOrder - b.xOrder)) {
    const current = segments[segments.length - 1];
    if (!current || point.xOrder !== current[current.length - 1].xOrder + 1) segments.push([point]);
    else current.push(point);
  }
  return segments;
}
