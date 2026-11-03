import type { BuiltTransactionRow } from "../types";
import {
  builtTxSortValue,
  formatBuiltTxContractDate,
  formatBuiltTxStructure,
  type BuiltTxSortKey,
} from "./builtTxDisplay";

/** 거래목록 집계. 계약연도는 목록의 계약일 필터로 돌아간다. */
export type BuiltTxAggregateDimension =
  | "gu_eup"
  | "dong_ri"
  | "ri"
  | "zone_type"
  | "building_use"
  | "road_width"
  | "contract_year"
  | "structure_group"
  | "asset_type";

export type BuiltTxDrillDownFilters = Partial<Record<BuiltTxSortKey, Set<string>>>;

export const BUILT_TX_AGGREGATE_DIMENSIONS: {
  id: BuiltTxAggregateDimension;
  label: string;
  hint?: string;
}[] = [
  { id: "gu_eup", label: "구·읍" },
  { id: "dong_ri", label: "읍·면·동" },
  { id: "ri", label: "리" },
  { id: "zone_type", label: "용도지역" },
  { id: "building_use", label: "건축물용도" },
  { id: "road_width", label: "도로조건" },
  { id: "contract_year", label: "계약연도" },
  { id: "structure_group", label: "구조", hint: "건축물대장 연결이 켜져 있을 때" },
  { id: "asset_type", label: "유형", hint: "유형을 둘 이상 고른 때" },
];

export interface BuiltTxPriceStats {
  count: number;
  landMedian: number | null;
  landMean: number | null;
  grossMedian: number | null;
  grossMean: number | null;
}

export interface BuiltTxAggregateRow extends BuiltTxPriceStats {
  key: string;
  label: string;
}

export interface BuiltTxCrossTab {
  rowDim: BuiltTxAggregateDimension;
  colDim: BuiltTxAggregateDimension;
  rowLabels: string[];
  colLabels: string[];
  cells: Record<string, BuiltTxPriceStats>;
  rowTotals: Record<string, BuiltTxPriceStats>;
  colTotals: Record<string, BuiltTxPriceStats>;
}

export function crossCellKey(row: string, col: string): string {
  return `${row}\x1e${col}`;
}

function median(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 0) return (sorted[mid - 1]! + sorted[mid]!) / 2;
  return sorted[mid]!;
}

function mean(values: number[]): number | null {
  if (!values.length) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function unitPrice(price: number | null | undefined, area: number | null | undefined): number | null {
  if (price == null || !Number.isFinite(price) || area == null || !(area > 0)) return null;
  return price / area;
}

function stats(count: number, land: number[], gross: number[]): BuiltTxPriceStats {
  return {
    count,
    landMedian: median(land),
    landMean: mean(land),
    grossMedian: median(gross),
    grossMean: mean(gross),
  };
}

export function builtTxAggregateDimensionLabel(
  dim: BuiltTxAggregateDimension,
  useLabel = "건축물용도",
): string {
  if (dim === "building_use") return useLabel;
  return BUILT_TX_AGGREGATE_DIMENSIONS.find((d) => d.id === dim)?.label ?? dim;
}

/** 목록 필터에 쓰는 표기와 같은 문자열. */
export function builtTxAggregateValue(row: BuiltTransactionRow, dim: BuiltTxAggregateDimension): string {
  if (dim === "contract_year") return row.contract_year != null ? String(row.contract_year) : "—";
  if (dim === "structure_group") return formatBuiltTxStructure(row.structure_group);
  const v = builtTxSortValue(row, dim);
  if (v == null || v === "") return "—";
  return String(v);
}

export function buildBuiltTxDrillDownFilters(
  items: BuiltTransactionRow[],
  parts: { dimension: BuiltTxAggregateDimension; value: string }[],
): BuiltTxDrillDownFilters {
  const out: BuiltTxDrillDownFilters = {};
  for (const { dimension, value } of parts) {
    if (dimension === "contract_year") {
      const dates = new Set<string>();
      for (const row of items) {
        if (builtTxAggregateValue(row, "contract_year") === value) dates.add(formatBuiltTxContractDate(row));
      }
      out.contract_date = dates;
      continue;
    }
    out[dimension] = new Set([value]);
  }
  return out;
}

export function aggregateBuiltTransactions(
  items: BuiltTransactionRow[],
  dimension: BuiltTxAggregateDimension,
): BuiltTxAggregateRow[] {
  const buckets = new Map<string, { count: number; land: number[]; gross: number[] }>();
  for (const row of items) {
    const label = builtTxAggregateValue(row, dimension);
    let bucket = buckets.get(label);
    if (!bucket) {
      bucket = { count: 0, land: [], gross: [] };
      buckets.set(label, bucket);
    }
    bucket.count += 1;
    const land = unitPrice(row.price, row.land_area);
    const gross = unitPrice(row.price, row.gross_area);
    if (land != null) bucket.land.push(land);
    if (gross != null) bucket.gross.push(gross);
  }
  return [...buckets.entries()]
    .map(([label, bucket]) => ({
      key: label,
      label,
      ...stats(bucket.count, bucket.land, bucket.gross),
    }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, "ko"));
}

export function aggregateBuiltTransactionsCross(
  items: BuiltTransactionRow[],
  rowDim: BuiltTxAggregateDimension,
  colDim: BuiltTxAggregateDimension,
): BuiltTxCrossTab {
  const empty: BuiltTxCrossTab = {
    rowDim,
    colDim,
    rowLabels: [],
    colLabels: [],
    cells: {},
    rowTotals: {},
    colTotals: {},
  };
  if (rowDim === colDim) return empty;

  const rowCounts = new Map<string, number>();
  const colCounts = new Map<string, number>();
  const cellCounts = new Map<string, number>();
  const cellLand = new Map<string, number[]>();
  const cellGross = new Map<string, number[]>();
  const rowLand = new Map<string, number[]>();
  const rowGross = new Map<string, number[]>();
  const colLand = new Map<string, number[]>();
  const colGross = new Map<string, number[]>();

  const take = (map: Map<string, number[]>, key: string) => {
    let list = map.get(key);
    if (!list) {
      list = [];
      map.set(key, list);
    }
    return list;
  };

  for (const row of items) {
    const rv = builtTxAggregateValue(row, rowDim);
    const cv = builtTxAggregateValue(row, colDim);
    const ck = crossCellKey(rv, cv);
    rowCounts.set(rv, (rowCounts.get(rv) ?? 0) + 1);
    colCounts.set(cv, (colCounts.get(cv) ?? 0) + 1);
    cellCounts.set(ck, (cellCounts.get(ck) ?? 0) + 1);
    const land = unitPrice(row.price, row.land_area);
    const gross = unitPrice(row.price, row.gross_area);
    if (land != null) {
      take(cellLand, ck).push(land);
      take(rowLand, rv).push(land);
      take(colLand, cv).push(land);
    }
    if (gross != null) {
      take(cellGross, ck).push(gross);
      take(rowGross, rv).push(gross);
      take(colGross, cv).push(gross);
    }
  }

  const sortLabels = (counts: Map<string, number>) =>
    [...counts.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "ko"))
      .map(([label]) => label);

  const rowLabels = sortLabels(rowCounts);
  const colLabels = sortLabels(colCounts);
  const cells: Record<string, BuiltTxPriceStats> = {};
  for (const [key, count] of cellCounts) {
    cells[key] = stats(count, cellLand.get(key) ?? [], cellGross.get(key) ?? []);
  }
  const rowTotals: Record<string, BuiltTxPriceStats> = {};
  for (const row of rowLabels) {
    rowTotals[row] = stats(rowCounts.get(row) ?? 0, rowLand.get(row) ?? [], rowGross.get(row) ?? []);
  }
  const colTotals: Record<string, BuiltTxPriceStats> = {};
  for (const col of colLabels) {
    colTotals[col] = stats(colCounts.get(col) ?? 0, colLand.get(col) ?? [], colGross.get(col) ?? []);
  }
  return { rowDim, colDim, rowLabels, colLabels, cells, rowTotals, colTotals };
}
