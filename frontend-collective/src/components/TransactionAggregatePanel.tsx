import { useMemo, useState } from "react";
import clsx from "clsx";
import {
  aggregateTransactions,
  aggregateTransactionsCross,
  buildTxDrillDownFilters,
  crossCellKey,
  type TxAggregateDimSpec,
  type TxCrossCell,
  type TxCrossPreset,
  type TxDrillDownFilters,
} from "../utils/txAggregate";

export type TxSubView = "list" | "aggregate";

export function TxListSubViewToggle({
  value,
  onChange,
}: {
  value: TxSubView;
  onChange: (v: TxSubView) => void;
}) {
  return (
    <div
      className="inline-flex rounded-md border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-800 p-0.5"
      role="tablist"
      aria-label="거래 보기"
    >
      {(
        [
          ["list", "목록"],
          ["aggregate", "집계"],
        ] as const
      ).map(([id, label]) => (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={value === id}
          className={clsx(
            "px-2 py-0.5 text-[11px] rounded transition-colors",
            value === id
              ? "bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-100 shadow-sm border border-slate-100 dark:border-slate-500 font-medium"
              : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200",
          )}
          onClick={() => onChange(id)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function formatPrice(v: number | null): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return v.toLocaleString("ko-KR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function CrossCellDisplay({ cell }: { cell: TxCrossCell }) {
  if (cell.count === 0) {
    return <span className="text-slate-300 dark:text-slate-600">—</span>;
  }
  return (
    <div className="leading-tight">
      <div className="tabular-nums text-slate-700 dark:text-slate-200">{cell.count.toLocaleString("ko-KR")}</div>
      <div className="tabular-nums text-[10px] text-blue-700 dark:text-blue-400 font-medium">
        {formatPrice(cell.medianUnitPrice)}
      </div>
    </div>
  );
}

function DimensionPicker<D extends string>({
  label,
  value,
  exclude,
  options,
  onChange,
}: {
  label: string;
  value: D;
  exclude?: D;
  options: TxAggregateDimSpec<D>[];
  onChange: (dim: D) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-[11px] text-slate-600 dark:text-slate-300 shrink-0 w-8">{label}</span>
      <div className="inline-flex flex-wrap gap-1">
        {options
          .filter((opt) => opt.id !== exclude)
          .map((opt) => (
            <button
              key={opt.id}
              type="button"
              className={clsx(
                "px-2 py-0.5 text-[10px] rounded border transition-colors",
                value === opt.id
                  ? "bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-100 border-slate-200 dark:border-slate-500 shadow-sm font-medium"
                  : "bg-transparent text-slate-500 dark:text-slate-400 border-transparent hover:text-slate-700 dark:hover:text-slate-200 hover:border-slate-100 dark:hover:border-slate-600",
              )}
              onClick={() => onChange(opt.id)}
              title={opt.hint}
            >
              {opt.label}
            </button>
          ))}
      </div>
    </div>
  );
}

type Props<T, D extends string, K extends string> = {
  items: T[];
  total: number;
  truncated: boolean;
  dimensions: TxAggregateDimSpec<D>[];
  presets: TxCrossPreset<D>[];
  defaultDimension: D;
  defaultRow: D;
  defaultCol: D;
  defaultPresetId?: string;
  dimensionValue: (item: T, dim: D) => string;
  unitPrice: (item: T) => number | null;
  area: (item: T) => number | null;
  drillDownKey: (dim: D) => K;
  onDrillDown: (filters: TxDrillDownFilters<K>) => void;
};

export default function TransactionAggregatePanel<T, D extends string, K extends string>({
  items,
  total,
  truncated,
  dimensions,
  presets,
  defaultDimension,
  defaultRow,
  defaultCol,
  defaultPresetId,
  dimensionValue,
  unitPrice,
  area,
  drillDownKey,
  onDrillDown,
}: Props<T, D, K>) {
  type AggregateMode = "single" | "cross";
  const [mode, setMode] = useState<AggregateMode>("single");
  const [dimension, setDimension] = useState<D>(defaultDimension);
  const [rowDim, setRowDim] = useState<D>(defaultRow);
  const [colDim, setColDim] = useState<D>(defaultCol);
  const [activePreset, setActivePreset] = useState<string | null>(defaultPresetId ?? null);

  const dimLabel = dimensions.find((d) => d.id === dimension)?.label ?? String(dimension);
  const dimHint = dimensions.find((d) => d.id === dimension)?.hint;

  const rows = useMemo(
    () => aggregateTransactions(items, dimension, dimensionValue, unitPrice, area),
    [items, dimension, dimensionValue, unitPrice, area],
  );
  const crossTab = useMemo(
    () => aggregateTransactionsCross(items, rowDim, colDim, dimensionValue, unitPrice),
    [items, rowDim, colDim, dimensionValue, unitPrice],
  );

  const applyPreset = (presetId: string) => {
    const preset = presets.find((p) => p.id === presetId);
    if (!preset) return;
    setMode("cross");
    setActivePreset(presetId);
    setRowDim(preset.row);
    setColDim(preset.col);
  };

  const handleRowDimChange = (dim: D) => {
    setActivePreset(null);
    setRowDim(dim);
    if (dim === colDim) {
      const alt = dimensions.find((d) => d.id !== dim);
      if (alt) setColDim(alt.id);
    }
  };

  const handleColDimChange = (dim: D) => {
    setActivePreset(null);
    setColDim(dim);
    if (dim === rowDim) {
      const alt = dimensions.find((d) => d.id !== dim);
      if (alt) setRowDim(alt.id);
    }
  };

  const emptyCrossCell: TxCrossCell = {
    count: 0,
    medianUnitPrice: null,
    meanUnitPrice: null,
  };

  const fireDrill = (parts: { dimension: D; value: string }[]) => {
    onDrillDown(buildTxDrillDownFilters(parts, drillDownKey));
  };

  return (
    <div className="flex flex-col flex-1 min-h-0 gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <div
          className="inline-flex rounded-md border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-800 p-0.5 shrink-0"
          role="tablist"
          aria-label="집계 형식"
        >
          {(
            [
              ["single", "1축"],
              ["cross", "2축 교차"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={mode === id}
              className={clsx(
                "px-2 py-0.5 text-[11px] rounded transition-colors",
                mode === id
                  ? "bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-100 shadow-sm border border-slate-100 dark:border-slate-500 font-medium"
                  : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200",
              )}
              onClick={() => setMode(id)}
            >
              {label}
            </button>
          ))}
        </div>

        {mode === "single" ? (
          <>
            <span className="text-[11px] text-slate-600 dark:text-slate-300 shrink-0">집계 기준</span>
            <div
              className="inline-flex flex-wrap gap-1 rounded-md border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-800 p-0.5"
              role="tablist"
              aria-label="집계 기준"
            >
              {dimensions.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  role="tab"
                  aria-selected={dimension === opt.id}
                  className={clsx(
                    "px-2 py-0.5 text-[11px] rounded transition-colors",
                    dimension === opt.id
                      ? "bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-100 shadow-sm border border-slate-100 dark:border-slate-500 font-medium"
                      : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200",
                  )}
                  onClick={() => setDimension(opt.id)}
                  title={opt.hint}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            {dimHint && <span className="text-[10px] text-slate-400">{dimHint}</span>}
          </>
        ) : (
          <div className="flex flex-wrap gap-1">
            {presets.map((preset) => (
              <button
                key={preset.id}
                type="button"
                className={clsx(
                  "px-2 py-0.5 text-[10px] rounded border transition-colors",
                  activePreset === preset.id
                    ? "bg-blue-50 dark:bg-blue-950/40 text-blue-800 dark:text-blue-300 border-blue-200 dark:border-blue-800 font-medium"
                    : "bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700",
                )}
                onClick={() => applyPreset(preset.id)}
              >
                {preset.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {mode === "cross" && (
        <div className="space-y-1 rounded-md border border-slate-100 dark:border-slate-700 bg-slate-50/60 dark:bg-slate-800/40 px-2 py-1.5">
          <DimensionPicker
            label="행"
            value={rowDim}
            exclude={colDim}
            options={dimensions}
            onChange={handleRowDimChange}
          />
          <DimensionPicker
            label="열"
            value={colDim}
            exclude={rowDim}
            options={dimensions}
            onChange={handleColDimChange}
          />
        </div>
      )}

      {truncated && (
        <p className="text-[10px] text-amber-800 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/30 border border-amber-100 dark:border-amber-800 rounded px-2 py-1">
          전체 {total.toLocaleString("ko-KR")}건 중 {items.length.toLocaleString("ko-KR")}건만
          집계합니다. CSV 내보내기 또는 필터 범위 축소를 권장합니다.
        </p>
      )}

      {mode === "single" ? (
        <div className="flex-1 min-h-[280px] overflow-auto rounded-lg border border-slate-100 dark:border-slate-700">
          <table className="w-full text-[11px] border-collapse min-w-[520px]">
            <thead className="sticky top-0 z-10">
              <tr className="bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                <th className="text-left px-2 py-1.5">{dimLabel}</th>
                <th className="text-right px-2 py-1.5 w-16">건수</th>
                <th className="text-right px-2 py-1.5 w-24">중앙 단가</th>
                <th className="text-right px-2 py-1.5 w-24">평균 단가</th>
                <th className="text-right px-2 py-1.5 w-24">면적합(㎡)</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center text-slate-400 py-6">
                    집계할 거래가 없습니다.
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr
                    key={row.key}
                    className="border-t border-slate-100 dark:border-slate-700 hover:bg-blue-50/40 dark:hover:bg-blue-950/20 cursor-pointer"
                    title="클릭하면 거래 목록에서 해당 구간만 표시"
                    onClick={() => fireDrill([{ dimension, value: row.label }])}
                  >
                    <td className="px-2 py-1 font-medium text-slate-800 dark:text-slate-100">{row.label}</td>
                    <td className="px-2 py-1 text-right tabular-nums">{row.count.toLocaleString("ko-KR")}</td>
                    <td className="px-2 py-1 text-right tabular-nums text-blue-700 dark:text-blue-400 font-semibold">
                      {formatPrice(row.medianUnitPrice)}
                    </td>
                    <td className="px-2 py-1 text-right tabular-nums text-slate-600 dark:text-slate-300">
                      {formatPrice(row.meanUnitPrice)}
                    </td>
                    <td className="px-2 py-1 text-right tabular-nums text-slate-600 dark:text-slate-300">
                      {row.sumAreaSqm > 0
                        ? row.sumAreaSqm.toLocaleString("ko-KR", { maximumFractionDigits: 1 })
                        : "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex-1 min-h-[280px] overflow-auto rounded-lg border border-slate-100 dark:border-slate-700">
          {crossTab.rowLabels.length === 0 || crossTab.colLabels.length === 0 ? (
            <p className="text-center text-slate-400 py-8 text-[11px]">
              교차 집계할 거래가 없거나 행·열 축이 같습니다.
            </p>
          ) : (
            <table className="w-full text-[11px] border-collapse min-w-[480px]">
              <thead className="sticky top-0 z-10">
                <tr className="bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                  <th className="text-left px-2 py-1.5 sticky left-0 z-20 bg-slate-50 dark:bg-slate-800 min-w-[88px]">
                    {dimensions.find((d) => d.id === rowDim)?.label ?? String(rowDim)} ↓ /{" "}
                    {dimensions.find((d) => d.id === colDim)?.label ?? String(colDim)} →
                  </th>
                  {crossTab.colLabels.map((col) => (
                    <th
                      key={col}
                      className="text-center px-1.5 py-1 min-w-[56px] cursor-pointer hover:bg-blue-50/60 dark:hover:bg-blue-950/30"
                      title="열 헤더 클릭 → 해당 열만 목록 필터"
                      onClick={() => fireDrill([{ dimension: colDim, value: col }])}
                    >
                      <div className="font-medium text-slate-700 dark:text-slate-200 truncate max-w-[72px]" title={col}>
                        {col}
                      </div>
                      <div className="text-[9px] text-slate-400 font-normal tabular-nums">
                        {(crossTab.colTotals[col]?.count ?? 0).toLocaleString("ko-KR")}건
                      </div>
                    </th>
                  ))}
                  <th className="text-center px-1.5 py-1 min-w-[56px] bg-slate-100/80 dark:bg-slate-700/80">합계</th>
                </tr>
              </thead>
              <tbody>
                {crossTab.rowLabels.map((row) => (
                  <tr key={row} className="border-t border-slate-100 dark:border-slate-700">
                    <td
                      className="px-2 py-1 font-medium text-slate-800 dark:text-slate-100 sticky left-0 bg-white dark:bg-slate-900 z-[5] cursor-pointer hover:bg-blue-50/40 dark:hover:bg-blue-950/20"
                      title="행 헤더 클릭 → 해당 행만 목록 필터"
                      onClick={() => fireDrill([{ dimension: rowDim, value: row }])}
                    >
                      <div className="truncate max-w-[120px]" title={row}>
                        {row}
                      </div>
                      <div className="text-[9px] text-slate-400 font-normal tabular-nums">
                        {(crossTab.rowTotals[row]?.count ?? 0).toLocaleString("ko-KR")}건
                      </div>
                    </td>
                    {crossTab.colLabels.map((col) => {
                      const cell = crossTab.cells[crossCellKey(row, col)] ?? emptyCrossCell;
                      return (
                        <td
                          key={col}
                          className={clsx(
                            "px-1.5 py-1 text-center align-middle",
                            cell.count > 0 && "cursor-pointer hover:bg-blue-50/50 dark:hover:bg-blue-950/20",
                          )}
                          title={cell.count > 0 ? "셀 클릭 → 행·열 조건 모두 목록 필터" : undefined}
                          onClick={() => {
                            if (cell.count === 0) return;
                            fireDrill([
                              { dimension: rowDim, value: row },
                              { dimension: colDim, value: col },
                            ]);
                          }}
                        >
                          <CrossCellDisplay cell={cell} />
                        </td>
                      );
                    })}
                    <td className="px-1.5 py-1 text-center bg-slate-50/50 dark:bg-slate-800/50 align-middle">
                      <CrossCellDisplay cell={crossTab.rowTotals[row] ?? emptyCrossCell} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <p className="text-[10px] text-slate-400">
        · 단가: 만원/㎡ (중앙값) ·{" "}
        {mode === "single" ? "행 클릭 → 목록 필터" : "셀=행+열 필터 · 행/열 헤더=한 축만 필터"}
      </p>
    </div>
  );
}
