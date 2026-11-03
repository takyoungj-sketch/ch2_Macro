import type { BuiltTransactionRow } from "../types";
import { allocateRow, type BandMap, type RowOverride } from "./allocationCost";
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

/** 토지 배분단가 범위. 하한·상한·기준을 거래마다 모은 뒤의 요약. */
export interface BuiltTxAllocRange {
  n: number;
  lowMedian: number | null;
  highMedian: number | null;
  lowMean: number | null;
  highMean: number | null;
  midMedian: number | null;
  midMean: number | null;
}

export interface BuiltTxPriceStats {
  count: number;
  landMedian: number | null;
  landMean: number | null;
  grossMedian: number | null;
  grossMean: number | null;
  alloc?: BuiltTxAllocRange;
}

export type BuiltTxAllocEnds = { low: number; high: number; mid: number };

/** 목록의 토지 배분단가와 같은 하한·상한·기준. 산정되지 않으면 null. */
export function allocationAggregateEnds(
  row: BuiltTransactionRow,
  bands: BandMap,
  override?: RowOverride | null,
): BuiltTxAllocEnds | null {
  const outcome = allocateRow(row, bands, override);
  if (!outcome.ok) return null;
  const { landLow, landHigh, landMid } = outcome.view;
  if (
    landLow == null ||
    landHigh == null ||
    landMid == null ||
    !Number.isFinite(landLow) ||
    !Number.isFinite(landHigh) ||
    !Number.isFinite(landMid)
  ) {
    return null;
  }
  return { low: landLow, high: landHigh, mid: landMid };
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

function allocRange(lows: number[], highs: number[], mids: number[]): BuiltTxAllocRange {
  return {
    n: lows.length,
    lowMedian: median(lows),
    highMedian: median(highs),
    lowMean: mean(lows),
    highMean: mean(highs),
    midMedian: median(mids),
    midMean: mean(mids),
  };
}

type AllocLists = { low: number[]; high: number[]; mid: number[] };

function emptyAllocLists(): AllocLists {
  return { low: [], high: [], mid: [] };
}

function pushAlloc(lists: AllocLists, ends: BuiltTxAllocEnds) {
  lists.low.push(ends.low);
  lists.high.push(ends.high);
  lists.mid.push(ends.mid);
}

function stats(count: number, land: number[], gross: number[], alloc?: AllocLists | null): BuiltTxPriceStats {
  const base: BuiltTxPriceStats = {
    count,
    landMedian: median(land),
    landMean: mean(land),
    grossMedian: median(gross),
    grossMean: mean(gross),
  };
  if (!alloc) return base;
  return { ...base, alloc: allocRange(alloc.low, alloc.high, alloc.mid) };
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
  allocOf?: (row: BuiltTransactionRow) => BuiltTxAllocEnds | null,
): BuiltTxAggregateRow[] {
  const buckets = new Map<string, { count: number; land: number[]; gross: number[]; alloc: AllocLists | null }>();
  for (const row of items) {
    const label = builtTxAggregateValue(row, dimension);
    let bucket = buckets.get(label);
    if (!bucket) {
      bucket = { count: 0, land: [], gross: [], alloc: allocOf ? emptyAllocLists() : null };
      buckets.set(label, bucket);
    }
    bucket.count += 1;
    const land = unitPrice(row.price, row.land_area);
    const gross = unitPrice(row.price, row.gross_area);
    if (land != null) bucket.land.push(land);
    if (gross != null) bucket.gross.push(gross);
    if (bucket.alloc && allocOf) {
      const ends = allocOf(row);
      if (ends) pushAlloc(bucket.alloc, ends);
    }
  }
  return [...buckets.entries()]
    .map(([label, bucket]) => ({
      key: label,
      label,
      ...stats(bucket.count, bucket.land, bucket.gross, bucket.alloc),
    }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, "ko"));
}

export function aggregateBuiltTransactionsCross(
  items: BuiltTransactionRow[],
  rowDim: BuiltTxAggregateDimension,
  colDim: BuiltTxAggregateDimension,
  allocOf?: (row: BuiltTransactionRow) => BuiltTxAllocEnds | null,
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
  const cellAlloc = new Map<string, AllocLists>();
  const rowAlloc = new Map<string, AllocLists>();
  const colAlloc = new Map<string, AllocLists>();

  const take = (map: Map<string, number[]>, key: string) => {
    let list = map.get(key);
    if (!list) {
      list = [];
      map.set(key, list);
    }
    return list;
  };

  const takeAlloc = (map: Map<string, AllocLists>, key: string) => {
    let lists = map.get(key);
    if (!lists) {
      lists = emptyAllocLists();
      map.set(key, lists);
    }
    return lists;
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
    if (allocOf) {
      const ends = allocOf(row);
      if (ends) {
        pushAlloc(takeAlloc(cellAlloc, ck), ends);
        pushAlloc(takeAlloc(rowAlloc, rv), ends);
        pushAlloc(takeAlloc(colAlloc, cv), ends);
      }
    }
  }

  const sortLabels = (counts: Map<string, number>) =>
    [...counts.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "ko"))
      .map(([label]) => label);

  const rowLabels = sortLabels(rowCounts);
  const colLabels = sortLabels(colCounts);
  const allocFor = (map: Map<string, AllocLists>, key: string): AllocLists | null => {
    if (!allocOf) return null;
    return map.get(key) ?? emptyAllocLists();
  };
  const cells: Record<string, BuiltTxPriceStats> = {};
  for (const [key, count] of cellCounts) {
    cells[key] = stats(count, cellLand.get(key) ?? [], cellGross.get(key) ?? [], allocFor(cellAlloc, key));
  }
  const rowTotals: Record<string, BuiltTxPriceStats> = {};
  for (const row of rowLabels) {
    rowTotals[row] = stats(rowCounts.get(row) ?? 0, rowLand.get(row) ?? [], rowGross.get(row) ?? [], allocFor(rowAlloc, row));
  }
  const colTotals: Record<string, BuiltTxPriceStats> = {};
  for (const col of colLabels) {
    colTotals[col] = stats(colCounts.get(col) ?? 0, colLand.get(col) ?? [], colGross.get(col) ?? [], allocFor(colAlloc, col));
  }
  return { rowDim, colDim, rowLabels, colLabels, cells, rowTotals, colTotals };
}
