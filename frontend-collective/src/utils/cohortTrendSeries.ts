import type { RollingStatsResponse, YearlyStatPoint, YearlyStatsResponse } from "../types";
import type { TrendSeries } from "../components/MultiBuildingTrendChart";

export function rollingToTrendSeries(data: RollingStatsResponse): TrendSeries {
  return {
    label: data.display_name,
    points: [...data.points]
      .sort((a, b) => a.bucket_index - b.bucket_index)
      .map((p) => ({
        xLabel: p.label,
        xOrder: p.bucket_index,
        count: p.count,
        mean: p.mean,
      })),
  };
}

export function yearlyToTrendSeries(displayName: string, points: YearlyStatPoint[]): TrendSeries {
  return {
    label: displayName,
    points: [...points]
      .sort((a, b) => a.year - b.year)
      .map((p) => ({
        xLabel: String(p.year),
        xOrder: p.year,
        count: p.count,
        mean: p.mean,
      })),
  };
}

export function yearlyResponseToTrendSeries(data: YearlyStatsResponse): TrendSeries {
  return yearlyToTrendSeries(data.display_name, data.points);
}
