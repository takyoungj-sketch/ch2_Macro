/** 같은 지목 열에서 거래수 분위로 평균 숫자 강도를 나눈다. */

export type MeanCountBand = "high" | "mid" | "low";

/** 이보다 적은 거래 칸이면 분위를 나누지 않는다. */
export const MEAN_BAND_MIN_CELLS = 5;

export function meanCountBands(
  counts: { key: string; count: number }[],
): Map<string, MeanCountBand> {
  const out = new Map<string, MeanCountBand>();
  const positive = counts.filter((row) => row.count > 0);
  if (positive.length < MEAN_BAND_MIN_CELLS) return out;

  const sorted = [...positive].sort(
    (a, b) => a.count - b.count || a.key.localeCompare(b.key, "ko"),
  );
  const n = sorted.length;
  const spanByCount = new Map<number, { first: number; last: number }>();
  sorted.forEach((row, index) => {
    const span = spanByCount.get(row.count);
    if (!span) spanByCount.set(row.count, { first: index, last: index });
    else span.last = index;
  });

  for (const row of positive) {
    const span = spanByCount.get(row.count);
    if (!span) continue;
    const avgRank = (span.first + span.last) / 2;
    const pct = (avgRank + 0.5) / n;
    const band: MeanCountBand = pct < 0.3 ? "low" : pct >= 0.7 ? "high" : "mid";
    out.set(row.key, band);
  }
  return out;
}

export function meanEmphasisByColumn(
  zones: string[],
  categories: string[],
  countAt: (zone: string, category: string) => number,
): Map<string, MeanCountBand> {
  const out = new Map<string, MeanCountBand>();
  for (const category of categories) {
    const bands = meanCountBands(
      zones.map((zone) => ({
        key: `${zone}|||${category}`,
        count: countAt(zone, category),
      })),
    );
    for (const [key, band] of bands) out.set(key, band);
  }
  return out;
}

export function meanBandClass(band: MeanCountBand | undefined): string {
  if (band === "high") return "matrix-mean-high";
  if (band === "low") return "matrix-mean-low";
  return "matrix-mean-mid";
}

export function meanBandTitle(band: MeanCountBand | undefined): string {
  if (band === "high") return "이 지목에서 거래수 상위 30%";
  if (band === "low") return "이 지목에서 거래수 하위 30%";
  if (band === "mid") return "이 지목에서 거래수 중간 40%";
  return "";
}
