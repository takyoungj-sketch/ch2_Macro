import type { JimokGroupTop3Item, LandTopItem, RegionalProfileFeatures } from "../types";

/** D-029: land_top{n} object 또는 flat 키에서 Top 리스트 조립. */
export function landTopItems(features: RegionalProfileFeatures): LandTopItem[] {
  const out: LandTopItem[] = [];
  for (let i = 1; i <= 3; i++) {
    const obj = features[`land_top${i}`] as LandTopItem | undefined;
    if (obj?.zone && obj.jimok) {
      out.push(obj);
      continue;
    }
    const zone = features[`land_top${i}_zone`] as string | undefined;
    const jimok = features[`land_top${i}_jimok`] as string | undefined;
    const jimokCode = features[`land_top${i}_jimok_code`] as string | undefined;
    const count = features[`land_top${i}_count`] as number | undefined;
    if (!zone || !jimok || count == null) continue;
    out.push({
      zone,
      jimok,
      jimok_code: jimokCode ?? "",
      count,
      mean_manwon_per_sqm: features[`land_top${i}_mean_manwon_per_sqm`] as number | undefined,
    });
  }
  return out;
}

export function jimokGroupTop3Items(features: RegionalProfileFeatures): JimokGroupTop3Item[] {
  return (features.jimok_group_top3 as JimokGroupTop3Item[] | undefined) ?? [];
}

export function hasLandProfileData(features: RegionalProfileFeatures): boolean {
  return landTopItems(features).length > 0 || jimokGroupTop3Items(features).length > 0;
}

/** D-030: beop grain 분위 표시·Twin mask 최소 표본 (3년 창). */
export const APARTMENT_PERCENTILE_MIN_COUNT = 15;

export function apartmentPercentiles(features: RegionalProfileFeatures): {
  count: number;
  p25?: number;
  median?: number;
  p75?: number;
} | null {
  const count = features.apartment_count as number | undefined;
  if (!count || count <= 0) return null;
  const p25 = features.apartment_p25 as number | undefined;
  const median = features.apartment_median as number | undefined;
  const p75 = features.apartment_p75 as number | undefined;
  if (p25 == null && median == null && p75 == null) return null;
  return { count, p25, median, p75 };
}

export function apartmentTradeCount(features: RegionalProfileFeatures): number {
  const fromMarket = features.apartment_count as number | undefined;
  if (fromMarket != null && fromMarket > 0) return fromMarket;
  const ym = features.yearly_mix as { totals_by_type?: Record<string, { count?: number }> } | undefined;
  return ym?.totals_by_type?.["아파트"]?.count ?? 0;
}
