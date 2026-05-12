import type { MatrixCell, StatsResult, YearlyTradeStat } from "../types";
import type { ComparePayloadV1 } from "../types/comparePayload";

function bomCsv(lines: string[]): string {
  return `\uFEFF${lines.join("\r\n")}`;
}

function escCell(v: string | number | boolean | null | undefined): string {
  if (v == null) return "";
  const s = typeof v === "boolean" ? (v ? "true" : "false") : String(v);
  if (/[",\r\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function download(filename: string, raw: string) {
  const blob = new Blob([raw], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/** 필터 매트릭스: 용도×지목별 통계 플래튼 */
export function downloadMatrixCsv(filename: string, matrix: MatrixCell[]) {
  const header = [
    "zone_type",
    "land_category",
    "count",
    "mean",
    "std",
    "ci_lower",
    "ci_upper",
    "min",
    "p25",
    "median",
    "p75",
    "max",
    "is_reliable",
  ];
  const rows = matrix.map((c) => {
    const st = c.stats;
    return [
      escCell(c.zone_type),
      escCell(c.land_category),
      escCell(st?.count ?? ""),
      escCell(st?.mean ?? ""),
      escCell(st?.std ?? ""),
      escCell(st?.ci_lower ?? ""),
      escCell(st?.ci_upper ?? ""),
      escCell(st?.min ?? ""),
      escCell(st?.p25 ?? ""),
      escCell(st?.median ?? ""),
      escCell(st?.p75 ?? ""),
      escCell(st?.max ?? ""),
      escCell(st?.is_reliable ?? ""),
    ].join(",");
  });
  download(filename, bomCsv([header.join(","), ...rows]));
}

/** 지역별 요약 (법정코드별 StatsResult 한 줄) */
export function downloadByRegionCsv(
  filename: string,
  regions: Record<string, StatsResult>,
  labels?: Record<string, string>
) {
  const header = [
    "beopjungri_code",
    "label",
    "count",
    "mean",
    "std",
    "ci_lower",
    "ci_upper",
    "min",
    "p25",
    "median",
    "p75",
    "max",
    "is_reliable",
  ];
  const keys = Object.keys(regions).sort((a, b) => a.localeCompare(b));
  const rows = keys.map((code) => {
    const st = regions[code];
    const lbl = labels?.[code]?.trim() || code;
    return [
      escCell(code),
      escCell(lbl),
      escCell(st?.count ?? ""),
      escCell(st?.mean ?? ""),
      escCell(st?.std ?? ""),
      escCell(st?.ci_lower ?? ""),
      escCell(st?.ci_upper ?? ""),
      escCell(st?.min ?? ""),
      escCell(st?.p25 ?? ""),
      escCell(st?.median ?? ""),
      escCell(st?.p75 ?? ""),
      escCell(st?.max ?? ""),
      escCell(st?.is_reliable ?? ""),
    ].join(",");
  });
  download(filename, bomCsv([header.join(","), ...rows]));
}

/** 연도별 거래 요약 */
export function downloadYearlyStatsCsv(filename: string, rows: YearlyTradeStat[]) {
  const header = ["year", "count", "total_price_10k_sum", "area_sqm_sum", "unit_price_per_sqm"];
  const lines = rows.map((r) =>
    [
      escCell(r.year),
      escCell(r.count),
      escCell(r.total_price_10k_sum ?? ""),
      escCell(r.area_sqm_sum ?? ""),
      escCell(r.unit_price_per_sqm ?? ""),
    ].join(",")
  );
  download(filename, bomCsv([header.join(","), ...lines]));
}

/** 비교 창 세트 묶음: 매트릭스 + 지역별 */
export function downloadComparePack(payload: ComparePayloadV1, baseName: string) {
  downloadMatrixCsv(`${baseName}_matrix.csv`, payload.matrix);
  downloadByRegionCsv(`${baseName}_by_region.csv`, payload.by_region, payload.regionLabels);
}
