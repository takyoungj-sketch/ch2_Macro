import type { LongTermTrendPoint, LongTermTrendSeries } from "../types";
import type { TrendSeries } from "../components/MultiRegionTrendChart";

export type LtPriceMetric = "mean" | "median";

/** 연도별 거래수 가중 평균: Σ(nᵢ·x̄ᵢ)/Σnᵢ — 평균 모드 전용 */
export function buildWeightedMeanCombinedSeries(
  series: LongTermTrendSeries[],
): TrendSeries | null {
  if (series.length < 2) return null;

  const byYear = new Map<number, { sumNx: number; sumN: number }>();
  for (const s of series) {
    for (const p of s.points) {
      if (p.mean == null || !Number.isFinite(p.mean) || p.count <= 0) continue;
      const cur = byYear.get(p.year) ?? { sumNx: 0, sumN: 0 };
      cur.sumNx += p.count * p.mean;
      cur.sumN += p.count;
      byYear.set(p.year, cur);
    }
  }
  if (byYear.size === 0) return null;

  const points = [...byYear.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([year, { sumNx, sumN }]) => ({
      xLabel: String(year),
      xOrder: year,
      count: sumN,
      value: Math.round((sumNx / sumN) * 10) / 10,
    }));

  return {
    label: "통합(가중평균)",
    color: "#0f172a",
    emphasize: true,
    points,
  };
}

export function longTermSeriesToTrendSeries(
  series: LongTermTrendSeries[],
  metric: LtPriceMetric,
): TrendSeries[] {
  return series.map((s) => ({
    label: s.region_name,
    points: [...s.points]
      .sort((a: LongTermTrendPoint, b: LongTermTrendPoint) => a.year - b.year)
      .map((p) => ({
        xLabel: String(p.year),
        xOrder: p.year,
        count: p.count,
        value: metric === "median" ? (p.median ?? null) : (p.mean ?? null),
      })),
  }));
}
