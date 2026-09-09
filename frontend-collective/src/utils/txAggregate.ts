/** 거래목록 집계(피벗 Lite) — 토지 MatrixCell 집계와 같은 1축·2축 교차. */

export type TxAggregateDimSpec<D extends string> = {
  id: D;
  label: string;
  hint?: string;
};

export type TxCrossPreset<D extends string> = {
  id: string;
  label: string;
  row: D;
  col: D;
};

export interface TxAggregateRow {
  key: string;
  label: string;
  count: number;
  sumAreaSqm: number;
  meanUnitPrice: number | null;
  medianUnitPrice: number | null;
}

export interface TxCrossCell {
  count: number;
  medianUnitPrice: number | null;
  meanUnitPrice: number | null;
}

export interface TxCrossTab {
  rowLabels: string[];
  colLabels: string[];
  cells: Record<string, TxCrossCell>;
  rowTotals: Record<string, TxCrossCell>;
  colTotals: Record<string, TxCrossCell>;
}

export type TxDrillDownFilters<K extends string> = Partial<Record<K, Set<string>>>;

export function txContractYearLabel(r: {
  contract_year?: number | null;
  contract_date?: string | null;
}): string {
  if (r.contract_year != null && Number.isFinite(Number(r.contract_year))) {
    return String(r.contract_year);
  }
  const d = (r.contract_date ?? "").trim();
  if (/^\d{4}/.test(d)) return d.slice(0, 4);
  return "—";
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

function finalizeCrossCell(prices: number[], count: number): TxCrossCell {
  return {
    count,
    medianUnitPrice: median(prices),
    meanUnitPrice: mean(prices),
  };
}

export function buildTxDrillDownFilters<D extends string, K extends string>(
  parts: { dimension: D; value: string }[],
  drillDownKey: (dim: D) => K,
): TxDrillDownFilters<K> {
  const out: TxDrillDownFilters<K> = {};
  for (const { dimension, value } of parts) {
    const key = drillDownKey(dimension);
    out[key] = new Set([value]);
  }
  return out;
}

export function aggregateTransactions<T, D extends string>(
  items: T[],
  dimension: D,
  dimensionValue: (item: T, dim: D) => string,
  unitPrice: (item: T) => number | null,
  area: (item: T) => number | null,
): TxAggregateRow[] {
  const buckets = new Map<
    string,
    { label: string; prices: number[]; areas: number[]; count: number }
  >();

  for (const item of items) {
    const label = dimensionValue(item, dimension);
    let bucket = buckets.get(label);
    if (!bucket) {
      bucket = { label, prices: [], areas: [], count: 0 };
      buckets.set(label, bucket);
    }
    bucket.count += 1;
    const p = unitPrice(item);
    if (p != null && Number.isFinite(p)) bucket.prices.push(p);
    const a = area(item);
    if (a != null && Number.isFinite(a)) bucket.areas.push(a);
  }

  const rows: TxAggregateRow[] = [];
  for (const bucket of buckets.values()) {
    rows.push({
      key: bucket.label,
      label: bucket.label,
      count: bucket.count,
      sumAreaSqm: bucket.areas.reduce((s, v) => s + v, 0),
      meanUnitPrice: mean(bucket.prices),
      medianUnitPrice: median(bucket.prices),
    });
  }
  rows.sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, "ko"));
  return rows;
}

export function aggregateTransactionsCross<T, D extends string>(
  items: T[],
  rowDim: D,
  colDim: D,
  dimensionValue: (item: T, dim: D) => string,
  unitPrice: (item: T) => number | null,
): TxCrossTab {
  const empty: TxCrossTab = {
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
    const p = unitPrice(item);
    if (p != null && Number.isFinite(p)) {
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
  const cells: Record<string, TxCrossCell> = {};
  for (const [key, prices] of cellBuckets) {
    cells[key] = finalizeCrossCell(prices, cellCounts.get(key) ?? 0);
  }
  const rowTotals: Record<string, TxCrossCell> = {};
  for (const row of rowLabels) {
    rowTotals[row] = finalizeCrossCell(rowPriceBuckets.get(row) ?? [], rowCounts.get(row) ?? 0);
  }
  const colTotals: Record<string, TxCrossCell> = {};
  for (const col of colLabels) {
    colTotals[col] = finalizeCrossCell(colPriceBuckets.get(col) ?? [], colCounts.get(col) ?? 0);
  }
  return { rowLabels, colLabels, cells, rowTotals, colTotals };
}
