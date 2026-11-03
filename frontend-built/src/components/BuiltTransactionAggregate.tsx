import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import type { BuiltTransactionRow } from "../types";
import {
  aggregateBuiltTransactions,
  aggregateBuiltTransactionsCross,
  BUILT_TX_AGGREGATE_DIMENSIONS,
  buildBuiltTxDrillDownFilters,
  builtTxAggregateDimensionLabel,
  builtTxAggregateValue,
  crossCellKey,
  type BuiltTxAggregateDimension,
  type BuiltTxDrillDownFilters,
  type BuiltTxPriceStats,
} from "../utils/builtTxAggregate";

type Props = {
  items: BuiltTransactionRow[];
  total: number;
  truncated: boolean;
  showStructure: boolean;
  showAsset: boolean;
  useLabel: string;
  onDrillDown: (filters: BuiltTxDrillDownFilters) => void;
};

type AggregateMode = "single" | "cross";

function formatPrice(v: number | null): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return v.toLocaleString("ko-KR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function PricePair({ stats }: { stats: BuiltTxPriceStats }) {
  if (stats.count === 0) return <span className="text-slate-300 dark:text-slate-600">—</span>;
  return (
    <div className="leading-tight">
      <div className="tabular-nums text-slate-700 dark:text-slate-200">{stats.count.toLocaleString("ko-KR")}</div>
      <div className="tabular-nums text-[10px] text-blue-700 dark:text-blue-300" title="중앙 단가 대지 · 연면적 (만원/㎡)">
        {formatPrice(stats.landMedian)} · {formatPrice(stats.grossMedian)}
      </div>
    </div>
  );
}

export default function BuiltTransactionAggregate({
  items,
  total,
  truncated,
  showStructure,
  showAsset,
  useLabel,
  onDrillDown,
}: Props) {
  const options = useMemo(
    () =>
      BUILT_TX_AGGREGATE_DIMENSIONS.filter(
        (d) => (d.id !== "structure_group" || showStructure) && (d.id !== "asset_type" || showAsset),
      ).map((d) => (d.id === "building_use" ? { ...d, label: useLabel } : d)),
    [showAsset, showStructure, useLabel],
  );

  const presets = useMemo(() => {
    const list: { id: string; label: string; row: BuiltTxAggregateDimension; col: BuiltTxAggregateDimension }[] = [
      { id: "gu_use", label: `구·읍 × ${useLabel}`, row: "gu_eup", col: "building_use" },
      { id: "emd_use", label: `읍·면·동 × ${useLabel}`, row: "dong_ri", col: "building_use" },
      { id: "emd_zone", label: "읍·면·동 × 용도지역", row: "dong_ri", col: "zone_type" },
      { id: "emd_road", label: "읍·면·동 × 도로조건", row: "dong_ri", col: "road_width" },
      { id: "emd_year", label: "읍·면·동 × 계약연도", row: "dong_ri", col: "contract_year" },
    ];
    if (showStructure) list.push({ id: "emd_struct", label: "읍·면·동 × 구조", row: "dong_ri", col: "structure_group" });
    if (showAsset) list.push({ id: "asset_use", label: `유형 × ${useLabel}`, row: "asset_type", col: "building_use" });
    return list;
  }, [showAsset, showStructure, useLabel]);

  const [mode, setMode] = useState<AggregateMode>("single");
  const [dimension, setDimension] = useState<BuiltTxAggregateDimension>("dong_ri");
  const [rowDim, setRowDim] = useState<BuiltTxAggregateDimension>("dong_ri");
  const [colDim, setColDim] = useState<BuiltTxAggregateDimension>("building_use");
  const [activePreset, setActivePreset] = useState<string | null>("emd_use");

  useEffect(() => {
    if (!options.some((opt) => opt.id === dimension)) setDimension("dong_ri");
    if (!options.some((opt) => opt.id === rowDim)) setRowDim("dong_ri");
    if (!options.some((opt) => opt.id === colDim) || colDim === rowDim) {
      const next = options.find((opt) => opt.id !== rowDim);
      if (next) setColDim(next.id);
    }
  }, [colDim, dimension, options, rowDim]);

  useEffect(() => {
    const blank = (dim: BuiltTxAggregateDimension) => {
      const values = new Set(items.map((row) => builtTxAggregateValue(row, dim)));
      return values.size === 1 && values.has("—");
    };
    if (blank(dimension)) {
      const fallback = options.find((opt) => !blank(opt.id));
      if (fallback) setDimension(fallback.id);
    }
    if (blank(rowDim)) {
      const fallback = options.find((opt) => opt.id !== colDim && !blank(opt.id));
      if (fallback) {
        setRowDim(fallback.id);
        setActivePreset(null);
      }
    }
  }, [colDim, dimension, items, options, rowDim]);

  const rows = useMemo(() => aggregateBuiltTransactions(items, dimension), [dimension, items]);
  const crossTab = useMemo(
    () => aggregateBuiltTransactionsCross(items, rowDim, colDim),
    [colDim, items, rowDim],
  );

  const drill = (parts: { dimension: BuiltTxAggregateDimension; value: string }[]) => {
    onDrillDown(buildBuiltTxDrillDownFilters(items, parts));
  };

  const applyPreset = (presetId: string) => {
    const preset = presets.find((p) => p.id === presetId);
    if (!preset) return;
    setMode("cross");
    setActivePreset(presetId);
    setRowDim(preset.row);
    setColDim(preset.col);
  };

  const emptyStats: BuiltTxPriceStats = {
    count: 0,
    landMedian: null,
    landMean: null,
    grossMedian: null,
    grossMean: null,
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
                  ? "bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 shadow-sm border border-slate-100 dark:border-slate-700 font-medium"
                  : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200",
              )}
              onClick={() => setMode(id)}
            >
              {label}
            </button>
          ))}
        </div>
        {mode === "single" ? (
          <div
            className="inline-flex flex-wrap gap-1 rounded-md border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-800 p-0.5"
            role="tablist"
            aria-label="집계 기준"
          >
            {options.map((opt) => (
              <button
                key={opt.id}
                type="button"
                role="tab"
                aria-selected={dimension === opt.id}
                title={opt.hint}
                className={clsx(
                  "px-2 py-0.5 text-[11px] rounded transition-colors",
                  dimension === opt.id
                    ? "bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 shadow-sm border border-slate-100 dark:border-slate-700 font-medium"
                    : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200",
                )}
                onClick={() => setDimension(opt.id)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        ) : (
          <div className="flex flex-wrap gap-1">
            {presets.map((preset) => (
              <button
                key={preset.id}
                type="button"
                className={clsx(
                  "px-2 py-0.5 text-[10px] rounded border transition-colors",
                  activePreset === preset.id
                    ? "bg-blue-50 dark:bg-blue-950 text-blue-800 dark:text-blue-200 border-blue-200 dark:border-blue-800 font-medium"
                    : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-800",
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
          {(
            [
              ["행", rowDim, colDim, setRowDim],
              ["열", colDim, rowDim, setColDim],
            ] as const
          ).map(([label, value, other, setValue]) => (
            <div key={label} className="flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] text-slate-600 dark:text-slate-300 shrink-0 w-8">{label}</span>
              <div className="inline-flex flex-wrap gap-1">
                {options
                  .filter((opt) => opt.id !== other)
                  .map((opt) => (
                    <button
                      key={opt.id}
                      type="button"
                      className={clsx(
                        "px-2 py-0.5 text-[10px] rounded border transition-colors",
                        value === opt.id
                          ? "bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 border-slate-200 dark:border-slate-600 shadow-sm font-medium"
                          : "bg-transparent text-slate-500 dark:text-slate-400 border-transparent hover:text-slate-700 dark:hover:text-slate-200",
                      )}
                      onClick={() => {
                        setActivePreset(null);
                        setValue(opt.id);
                      }}
                    >
                      {opt.label}
                    </button>
                  ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {truncated && (
        <p className="text-[10px] text-amber-800 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 border border-amber-100 dark:border-amber-900 rounded px-2 py-1">
          전체 {total.toLocaleString("ko-KR")}건 중 {items.length.toLocaleString("ko-KR")}건만 집계합니다.
        </p>
      )}

      {mode === "single" ? (
        <div className="flex-1 min-h-[280px] overflow-auto rounded-lg border border-slate-100 dark:border-slate-700">
          <table className="w-full text-[11px] border-collapse min-w-[640px]">
            <thead className="sticky top-0 z-10">
              <tr className="bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                <th className="text-left px-2 py-1.5">{builtTxAggregateDimensionLabel(dimension, useLabel)}</th>
                <th className="text-right px-2 py-1.5 w-16">건수</th>
                <th className="text-right px-2 py-1.5" title="금액 ÷ 대지면적, 만원/㎡">대지 중앙</th>
                <th className="text-right px-2 py-1.5" title="금액 ÷ 대지면적, 만원/㎡">대지 평균</th>
                <th className="text-right px-2 py-1.5" title="금액 ÷ 연면적, 만원/㎡">연면적 중앙</th>
                <th className="text-right px-2 py-1.5" title="금액 ÷ 연면적, 만원/㎡">연면적 평균</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center text-slate-400 py-6">
                    집계할 거래가 없습니다.
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr
                    key={row.key}
                    className="border-t border-slate-100 dark:border-slate-700 hover:bg-blue-50/40 dark:hover:bg-slate-800 cursor-pointer"
                    title="클릭하면 거래 목록에서 해당 구간만 표시"
                    onClick={() => drill([{ dimension, value: row.label }])}
                  >
                    <td className="px-2 py-1 font-medium text-slate-800 dark:text-slate-100">{row.label}</td>
                    <td className="px-2 py-1 text-right tabular-nums">{row.count.toLocaleString("ko-KR")}</td>
                    <td className="px-2 py-1 text-right tabular-nums text-blue-700 dark:text-blue-300 font-semibold">
                      {formatPrice(row.landMedian)}
                    </td>
                    <td className="px-2 py-1 text-right tabular-nums text-slate-600 dark:text-slate-300">
                      {formatPrice(row.landMean)}
                    </td>
                    <td className="px-2 py-1 text-right tabular-nums text-blue-700 dark:text-blue-300 font-semibold">
                      {formatPrice(row.grossMedian)}
                    </td>
                    <td className="px-2 py-1 text-right tabular-nums text-slate-600 dark:text-slate-300">
                      {formatPrice(row.grossMean)}
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
            <p className="text-center text-slate-400 py-8 text-[11px]">교차 집계할 거래가 없거나 행·열 축이 같습니다.</p>
          ) : (
            <table className="w-full text-[11px] border-collapse min-w-[480px]">
              <thead className="sticky top-0 z-10">
                <tr className="bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                  <th className="text-left px-2 py-1.5 sticky left-0 z-20 bg-slate-50 dark:bg-slate-800 min-w-[88px]">
                    {builtTxAggregateDimensionLabel(rowDim, useLabel)} ↓ / {builtTxAggregateDimensionLabel(colDim, useLabel)} →
                  </th>
                  {crossTab.colLabels.map((col) => (
                    <th
                      key={col}
                      className="text-center px-1.5 py-1 min-w-[72px] cursor-pointer hover:bg-blue-50/60 dark:hover:bg-slate-700"
                      title="열 헤더 클릭 → 해당 열만 목록 필터"
                      onClick={() => drill([{ dimension: colDim, value: col }])}
                    >
                      <div className="font-medium truncate max-w-[88px]" title={col}>
                        {col}
                      </div>
                      <div className="text-[10px] font-normal tabular-nums text-slate-400">
                        {(crossTab.colTotals[col]?.count ?? 0).toLocaleString("ko-KR")}건
                      </div>
                    </th>
                  ))}
                  <th className="text-center px-1.5 py-1 min-w-[72px]">합계</th>
                </tr>
              </thead>
              <tbody>
                {crossTab.rowLabels.map((row) => (
                  <tr key={row} className="border-t border-slate-100 dark:border-slate-700">
                    <td
                      className="px-2 py-1 font-medium text-slate-800 dark:text-slate-100 sticky left-0 bg-white dark:bg-slate-900 z-[5] cursor-pointer hover:bg-blue-50/40 dark:hover:bg-slate-800"
                      title="행 헤더 클릭 → 해당 행만 목록 필터"
                      onClick={() => drill([{ dimension: rowDim, value: row }])}
                    >
                      <div className="truncate max-w-[120px]" title={row}>
                        {row}
                      </div>
                      <div className="text-[10px] font-normal tabular-nums text-slate-400">
                        {(crossTab.rowTotals[row]?.count ?? 0).toLocaleString("ko-KR")}건
                      </div>
                    </td>
                    {crossTab.colLabels.map((col) => {
                      const cell = crossTab.cells[crossCellKey(row, col)] ?? emptyStats;
                      return (
                        <td
                          key={col}
                          className={clsx("px-1.5 py-1 text-center align-middle", cell.count > 0 && "cursor-pointer hover:bg-blue-50/50 dark:hover:bg-slate-800")}
                          title={cell.count > 0 ? "셀 클릭 → 행·열 조건 모두 목록 필터" : undefined}
                          onClick={() => {
                            if (cell.count === 0) return;
                            drill([
                              { dimension: rowDim, value: row },
                              { dimension: colDim, value: col },
                            ]);
                          }}
                        >
                          <PricePair stats={cell} />
                        </td>
                      );
                    })}
                    <td className="px-1.5 py-1 text-center bg-slate-50/50 dark:bg-slate-800/40 align-middle">
                      <PricePair stats={crossTab.rowTotals[row] ?? emptyStats} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <p className="text-[10px] text-slate-400">
        단가 만원/㎡ · 대지는 금액÷대지면적, 연면적은 금액÷연면적
        {mode === "cross" ? " · 칸 아래 숫자는 중앙값(대지 · 연면적)" : ""}
        {" · "}
        {mode === "single" ? "행을 누르면 목록이 그 구간만 보여 줍니다." : "칸은 행과 열, 머리글은 한 축만 목록으로 좁힙니다."}
      </p>
    </div>
  );
}
