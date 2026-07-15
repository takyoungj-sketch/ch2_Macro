import type { TrendSeries } from "../components/MultiBuildingTrendChart";

/** 연도(또는 동일 xOrder)별 거래수 가중 평균: Σ(nᵢ·x̄ᵢ)/Σnᵢ — 평균 모드 전용 */
export function buildWeightedMeanCombinedSeries(series: TrendSeries[]): TrendSeries | null {
  if (series.length < 2) return null;

  const byOrder = new Map<number, { sumNx: number; sumN: number; xLabel: string }>();
  for (const s of series) {
    for (const p of s.points) {
      if (p.mean == null || !Number.isFinite(p.mean) || p.count <= 0) continue;
      const cur = byOrder.get(p.xOrder) ?? { sumNx: 0, sumN: 0, xLabel: p.xLabel };
      cur.sumNx += p.count * p.mean;
      cur.sumN += p.count;
      if (!cur.xLabel) cur.xLabel = p.xLabel;
      byOrder.set(p.xOrder, cur);
    }
  }
  if (byOrder.size === 0) return null;

  const points = [...byOrder.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([xOrder, { sumNx, sumN, xLabel }]) => ({
      xLabel,
      xOrder,
      count: sumN,
      mean: Math.round((sumNx / sumN) * 10) / 10,
    }));

  return {
    label: "통합(가중평균)",
    color: "#0f172a",
    points,
  };
}
