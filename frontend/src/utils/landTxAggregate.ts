import type { MatrixCellTransactionItem } from "../types";
import { landTxAdminCols, type LandTxSortKey } from "./landTxDisplay";

/** 거래목록 집계(피벗 Lite) — 행·열 그룹 축 */
export type LandTxAggregateDimension =
  | "eupmyeondong"
  | "ri"
  | "road"
  | "deal_type"
  | "contract_year"
  | "land_category";

export type LandTxDrillDownFilters = Partial<Record<LandTxSortKey, Set<string>>>;

export const LAND_TX_AGGREGATE_DIMENSIONS: {
  id: LandTxAggregateDimension;
  label: string;
  hint?: string;
}[] = [
  { id: "eupmyeondong", label: "읍·면·동", hint: "하위 행정구역별 비교(주 사용)" },
  { id: "ri", label: "동·리", hint: "법정리·동 단위" },
  { id: "road", label: "도로", hint: "도로조건별 단가 차이" },
  { id: "deal_type", label: "거래유형", hint: "매매·분양 등" },
  { id: "contract_year", label: "계약연도" },
  { id: "land_category", label: "지목", hint: "지목군 모드" },
];

/** Phase 2 — 자주 쓰는 2축 preset (행 × 열) */
export const LAND_TX_CROSS_PRESETS: {
  id: string;
  label: string;
  row: LandTxAggregateDimension;
  col: LandTxAggregateDimension;
}[] = [
  { id: "emd_deal", label: "읍·면·동 × 거래유형", row: "eupmyeondong", col: "deal_type" },
  { id: "emd_road", label: "읍·면·동 × 도로", row: "eupmyeondong", col: "road" },
  { id: "emd_year", label: "읍·면·동 × 연도", row: "eupmyeondong", col: "contract_year" },
  { id: "emd_jimok", label: "읍·면·동 × 지목", row: "eupmyeondong", col: "land_category" },
];

export interface LandTxAggregateRow {
  key: string;
  label: string;
  count: number;
  sumAreaSqm: number;
  meanUnitPrice: number | null;
  medianUnitPrice: number | null;
}

export interface LandTxCrossCell {
  count: number;
  medianUnitPrice: number | null;
  meanUnitPrice: number | null;
}

export interface LandTxCrossTab {
  rowDim: LandTxAggregateDimension;
  colDim: LandTxAggregateDimension;
  rowLabels: string[];
  colLabels: string[];
  /** `${rowLabel}\x1e${colLabel}` → cell */
  cells: Record<string, LandTxCrossCell>;
  rowTotals: Record<string, LandTxCrossCell>;
  colTotals: Record<string, LandTxCrossCell>;
}

export function crossCellKey(row: string, col: string): string {
  return `${row}\x1e${col}`;
}

function median(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 0) {
    return (sorted[mid - 1]! + sorted[mid]!) / 2;
  }
  return sorted[mid]!;
}

function mean(values: number[]): number | null {
  if (!values.length) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function finalizeCrossCell(prices: number[], count: number): LandTxCrossCell {
  return {
    count,
    medianUnitPrice: median(prices),
    meanUnitPrice: mean(prices),
  };
}

export function landTxAggregateDimensionLabel(dim: LandTxAggregateDimension): string {
  return LAND_TX_AGGREGATE_DIMENSIONS.find((d) => d.id === dim)?.label ?? dim;
}

/** 집계 축 → 거래목록 컬럼 필터 키 */
export function landTxAggregateDrillDownKey(
  dim: LandTxAggregateDimension,
): "eupmyeondong" | "ri" | "road" | "deal_type" | "contract_date" | "land_category" {
  if (dim === "contract_year") return "contract_date";
  return dim;
}

/** 드릴다운 필터 맵 생성 (1~2축) */
export function buildLandTxDrillDownFilters(
  parts: { dimension: LandTxAggregateDimension; value: string }[],
): LandTxDrillDownFilters {
  const out: LandTxDrillDownFilters = {};
  for (const { dimension, value } of parts) {
    const key = landTxAggregateDrillDownKey(dimension);
    out[key] = new Set([value]);
  }
  return out;
}

function dimensionValue(item: MatrixCellTransactionItem, dim: LandTxAggregateDimension): string {
  const admin = landTxAdminCols(item);
  switch (dim) {
    case "eupmyeondong":
      return admin.eupmyeondong?.trim() || "—";
    case "ri":
      return admin.ri?.trim() || "—";
    case "road":
      return item.road_condition?.trim() || "—";
    case "deal_type":
      return item.deal_type?.trim() || "—";
    case "contract_year":
      return String(item.contract_year);
    case "land_category":
      return item.land_category?.trim() || "—";
    default:
      return "—";
  }
}

export function aggregateLandTransactions(
  items: MatrixCellTransactionItem[],
  dimension: LandTxAggregateDimension,
): LandTxAggregateRow[] {
  const buckets = new Map<
    string,
    { label: string; prices: number[]; areas: number[]; count: number }
  >();

  for (const item of items) {
    const label = dimensionValue(item, dimension);
    const key = label;
    let bucket = buckets.get(key);
    if (!bucket) {
      bucket = { label, prices: [], areas: [], count: 0 };
      buckets.set(key, bucket);
    }
    bucket.count += 1;
    if (item.unit_price_per_sqm != null && Number.isFinite(item.unit_price_per_sqm)) {
      bucket.prices.push(Number(item.unit_price_per_sqm));
    }
    if (item.area_sqm != null && Number.isFinite(item.area_sqm)) {
      bucket.areas.push(Number(item.area_sqm));
    }
  }

  const rows: LandTxAggregateRow[] = [];
  for (const bucket of buckets.values()) {
    rows.push({
      key: bucket.label,
      label: bucket.label,
      count: bucket.count,
      sumAreaSqm: bucket.areas.reduce((a, b) => a + b, 0),
      meanUnitPrice: mean(bucket.prices),
      medianUnitPrice: median(bucket.prices),
    });
  }

  rows.sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, "ko"));
  return rows;
}

/** Phase 2 — 2축 교차 집계 (행 × 열) */
export function aggregateLandTransactionsCross(
  items: MatrixCellTransactionItem[],
  rowDim: LandTxAggregateDimension,
  colDim: LandTxAggregateDimension,
): LandTxCrossTab {
  const empty: LandTxCrossTab = {
    rowDim,
    colDim,
    rowLabels: [],
    colLabels: [],
    cells: {},
    rowTotals: {},
    colTotals: {},
  };
  if (rowDim === colDim) return empty;

  const cellBuckets = new Map<string, number[]>();
  const rowCounts = new Map<string, number>();
  const colCounts = new Map<string, number>();
  const rowPriceBuckets = new Map<string, number[]>();
  const colPriceBuckets = new Map<string, number[]>();
  const cellCounts = new Map<string, number>();

  for (const item of items) {
    const rv = dimensionValue(item, rowDim);
    const cv = dimensionValue(item, colDim);
    const ck = crossCellKey(rv, cv);

    rowCounts.set(rv, (rowCounts.get(rv) ?? 0) + 1);
    colCounts.set(cv, (colCounts.get(cv) ?? 0) + 1);
    cellCounts.set(ck, (cellCounts.get(ck) ?? 0) + 1);

    let cellPrices = cellBuckets.get(ck);
    if (!cellPrices) {
      cellPrices = [];
      cellBuckets.set(ck, cellPrices);
    }

    let rowPrices = rowPriceBuckets.get(rv);
    if (!rowPrices) {
      rowPrices = [];
      rowPriceBuckets.set(rv, rowPrices);
    }

    let colPrices = colPriceBuckets.get(cv);
    if (!colPrices) {
      colPrices = [];
      colPriceBuckets.set(cv, colPrices);
    }

    if (item.unit_price_per_sqm != null && Number.isFinite(item.unit_price_per_sqm)) {
      const p = Number(item.unit_price_per_sqm);
      cellPrices.push(p);
      rowPrices.push(p);
      colPrices.push(p);
    }
  }

  const sortLabels = (counts: Map<string, number>) =>
    [...counts.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "ko"))
      .map(([label]) => label);

  const rowLabels = sortLabels(rowCounts);
  const colLabels = sortLabels(colCounts);

  const cells: Record<string, LandTxCrossCell> = {};
  for (const [key, prices] of cellBuckets) {
    cells[key] = finalizeCrossCell(prices, cellCounts.get(key) ?? 0);
  }

  const rowTotals: Record<string, LandTxCrossCell> = {};
  for (const row of rowLabels) {
    rowTotals[row] = finalizeCrossCell(rowPriceBuckets.get(row) ?? [], rowCounts.get(row) ?? 0);
  }

  const colTotals: Record<string, LandTxCrossCell> = {};
  for (const col of colLabels) {
    colTotals[col] = finalizeCrossCell(colPriceBuckets.get(col) ?? [], colCounts.get(col) ?? 0);
  }

  return {
    rowDim,
    colDim,
    rowLabels,
    colLabels,
    cells,
    rowTotals,
    colTotals,
  };
}
