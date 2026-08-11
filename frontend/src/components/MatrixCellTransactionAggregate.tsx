import { useMemo, useState } from "react";
import clsx from "clsx";
import type { MatrixCellTransactionItem } from "../types";
import { simpleTableHeadClass } from "../constants/displayUi";
import {
  aggregateLandTransactions,
  aggregateLandTransactionsCross,
  buildLandTxDrillDownFilters,
  crossCellKey,
  LAND_TX_AGGREGATE_DIMENSIONS,
  LAND_TX_CROSS_PRESETS,
  landTxAggregateDimensionLabel,
  type LandTxAggregateDimension,
  type LandTxCrossCell,
  type LandTxDrillDownFilters,
} from "../utils/landTxAggregate";

type Props = {
  items: MatrixCellTransactionItem[];
  total: number;
  truncated: boolean;
  showLandCategory?: boolean;
  onDrillDown: (filters: LandTxDrillDownFilters) => void;
};

type AggregateMode = "single" | "cross";

function formatPrice(v: number | null): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return v.toLocaleString("ko-KR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function CrossCellDisplay({ cell }: { cell: LandTxCrossCell }) {
  if (cell.count === 0) {
    return <span className="text-slate-300">—</span>;
  }
  return (
    <div className="leading-tight">
      <div className="tabular-nums text-slate-700">{cell.count.toLocaleString("ko-KR")}</div>
      <div className="tabular-nums text-[10px] text-blue-700 font-medium">
        {formatPrice(cell.medianUnitPrice)}
      </div>
    </div>
  );
}

function DimensionPicker({
  label,
  value,
  exclude,
  options,
  onChange,
}: {
  label: string;
  value: LandTxAggregateDimension;
  exclude?: LandTxAggregateDimension;
  options: typeof LAND_TX_AGGREGATE_DIMENSIONS;
  onChange: (dim: LandTxAggregateDimension) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-[11px] text-slate-600 shrink-0 w-8">{label}</span>
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
                  ? "bg-white text-slate-800 border-slate-200 shadow-sm font-medium"
                  : "bg-transparent text-slate-500 border-transparent hover:text-slate-700 hover:border-slate-100",
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

export default function MatrixCellTransactionAggregate({
  items,
  total,
  truncated,
  showLandCategory = false,
  onDrillDown,
}: Props) {
  const dimensionOptions = useMemo(
    () =>
      LAND_TX_AGGREGATE_DIMENSIONS.filter(
        (d) => d.id !== "land_category" || showLandCategory,
      ),
    [showLandCategory],
  );

  const crossPresets = useMemo(
    () =>
      LAND_TX_CROSS_PRESETS.filter(
        (p) => p.col !== "land_category" || showLandCategory,
      ),
    [showLandCategory],
  );

  const [mode, setMode] = useState<AggregateMode>("single");
  const [dimension, setDimension] = useState<LandTxAggregateDimension>("eupmyeondong");
  const [rowDim, setRowDim] = useState<LandTxAggregateDimension>("eupmyeondong");
  const [colDim, setColDim] = useState<LandTxAggregateDimension>("deal_type");
  const [activePreset, setActivePreset] = useState<string | null>("emd_deal");

  const rows = useMemo(
    () => aggregateLandTransactions(items, dimension),
    [items, dimension],
  );

  const crossTab = useMemo(
    () => aggregateLandTransactionsCross(items, rowDim, colDim),
    [items, rowDim, colDim],
  );

  const dimLabel = landTxAggregateDimensionLabel(dimension);
  const dimHint = dimensionOptions.find((d) => d.id === dimension)?.hint;

  const applyPreset = (presetId: string) => {
    const preset = crossPresets.find((p) => p.id === presetId);
    if (!preset) return;
    setMode("cross");
    setActivePreset(presetId);
    setRowDim(preset.row);
    setColDim(preset.col);
  };

  const handleRowDimChange = (dim: LandTxAggregateDimension) => {
    setActivePreset(null);
    setRowDim(dim);
    if (dim === colDim) {
      const alt = dimensionOptions.find((d) => d.id !== dim);
      if (alt) setColDim(alt.id);
    }
  };

  const handleColDimChange = (dim: LandTxAggregateDimension) => {
    setActivePreset(null);
    setColDim(dim);
    if (dim === rowDim) {
      const alt = dimensionOptions.find((d) => d.id !== dim);
      if (alt) setRowDim(alt.id);
    }
  };

  const emptyCrossCell: LandTxCrossCell = {
    count: 0,
    medianUnitPrice: null,
    meanUnitPrice: null,
  };

  return (
    <div className="flex flex-col flex-1 min-h-0 gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <div
          className="inline-flex rounded-md border border-slate-200 bg-slate-50 p-0.5 shrink-0"
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
                  ? "bg-white text-slate-800 shadow-sm border border-slate-100 font-medium"
                  : "text-slate-500 hover:text-slate-700",
              )}
              onClick={() => setMode(id)}
            >
              {label}
            </button>
          ))}
        </div>

        {mode === "single" ? (
          <>
            <span className="text-[11px] text-slate-600 shrink-0">집계 기준</span>
            <div
              className="inline-flex flex-wrap gap-1 rounded-md border border-slate-200 bg-slate-50 p-0.5"
              role="tablist"
              aria-label="집계 기준"
            >
              {dimensionOptions.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  role="tab"
                  aria-selected={dimension === opt.id}
                  className={clsx(
                    "px-2 py-0.5 text-[11px] rounded transition-colors",
                    dimension === opt.id
                      ? "bg-white text-slate-800 shadow-sm border border-slate-100 font-medium"
                      : "text-slate-500 hover:text-slate-700",
                  )}
                  onClick={() => setDimension(opt.id)}
                  title={opt.hint}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            {dimHint && (
              <span className="text-[10px] text-slate-400">{dimHint}</span>
            )}
          </>
        ) : (
          <div className="flex flex-wrap gap-1">
            {crossPresets.map((preset) => (
              <button
                key={preset.id}
                type="button"
                className={clsx(
                  "px-2 py-0.5 text-[10px] rounded border transition-colors",
                  activePreset === preset.id
                    ? "bg-blue-50 text-blue-800 border-blue-200 font-medium"
                    : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50",
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
        <div className="space-y-1 rounded-md border border-slate-100 bg-slate-50/60 px-2 py-1.5">
          <DimensionPicker
            label="행"
            value={rowDim}
            exclude={colDim}
            options={dimensionOptions}
            onChange={handleRowDimChange}
          />
          <DimensionPicker
            label="열"
            value={colDim}
            exclude={rowDim}
            options={dimensionOptions}
            onChange={handleColDimChange}
          />
        </div>
      )}

      {truncated && (
        <p className="text-[10px] text-amber-800 bg-amber-50 border border-amber-100 rounded px-2 py-1">
          전체 {total.toLocaleString("ko-KR")}건 중 {items.length.toLocaleString("ko-KR")}건만
          집계합니다. CSV 내보내기 또는 필터 범위 축소를 권장합니다.
        </p>
      )}

      {mode === "single" ? (
        <div className="flex-1 min-h-[280px] overflow-auto rounded-lg border border-slate-100">
          <table className="w-full text-[11px] border-collapse min-w-[520px]">
            <thead className="sticky top-0 z-10">
              <tr className={simpleTableHeadClass("neutral")}>
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
                    className="border-t border-slate-100 hover:bg-blue-50/40 cursor-pointer"
                    title="클릭하면 거래 목록에서 해당 구간만 표시"
                    onClick={() =>
                      onDrillDown(
                        buildLandTxDrillDownFilters([{ dimension, value: row.label }]),
                      )
                    }
                  >
                    <td className="px-2 py-1 font-medium text-slate-800">{row.label}</td>
                    <td className="px-2 py-1 text-right tabular-nums">
                      {row.count.toLocaleString("ko-KR")}
                    </td>
                    <td className="px-2 py-1 text-right tabular-nums text-blue-700 font-semibold">
                      {formatPrice(row.medianUnitPrice)}
                    </td>
                    <td className="px-2 py-1 text-right tabular-nums text-slate-600">
                      {formatPrice(row.meanUnitPrice)}
                    </td>
                    <td className="px-2 py-1 text-right tabular-nums text-slate-600">
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
        <div className="flex-1 min-h-[280px] overflow-auto rounded-lg border border-slate-100">
          {crossTab.rowLabels.length === 0 || crossTab.colLabels.length === 0 ? (
            <p className="text-center text-slate-400 py-8 text-[11px]">
              교차 집계할 거래가 없거나 행·열 축이 같습니다.
            </p>
          ) : (
            <table className="w-full text-[11px] border-collapse min-w-[480px]">
              <thead className="sticky top-0 z-10">
                <tr className={simpleTableHeadClass("neutral")}>
                  <th className="text-left px-2 py-1.5 sticky left-0 z-20 bg-slate-50 min-w-[88px]">
                    {landTxAggregateDimensionLabel(rowDim)} ↓ /{" "}
                    {landTxAggregateDimensionLabel(colDim)} →
                  </th>
                  {crossTab.colLabels.map((col) => (
                    <th
                      key={col}
                      className="text-center px-1.5 py-1 min-w-[56px] cursor-pointer hover:bg-blue-50/60"
                      title="열 헤더 클릭 → 해당 열만 목록 필터"
                      onClick={() =>
                        onDrillDown(
                          buildLandTxDrillDownFilters([{ dimension: colDim, value: col }]),
                        )
                      }
                    >
                      <div className="font-medium text-slate-700 truncate max-w-[72px]" title={col}>
                        {col}
                      </div>
                      <div className="text-[9px] text-slate-400 font-normal tabular-nums">
                        {(crossTab.colTotals[col]?.count ?? 0).toLocaleString("ko-KR")}건
                      </div>
                    </th>
                  ))}
                  <th
                    className="text-center px-1.5 py-1 min-w-[56px] bg-slate-100/80 cursor-pointer hover:bg-blue-50/60"
                    title="행 합계 열 — 필터 없음"
                  >
                    합계
                  </th>
                </tr>
              </thead>
              <tbody>
                {crossTab.rowLabels.map((row) => (
                  <tr key={row} className="border-t border-slate-100">
                    <td
                      className="px-2 py-1 font-medium text-slate-800 sticky left-0 bg-white z-[5] cursor-pointer hover:bg-blue-50/40"
                      title="행 헤더 클릭 → 해당 행만 목록 필터"
                      onClick={() =>
                        onDrillDown(
                          buildLandTxDrillDownFilters([{ dimension: rowDim, value: row }]),
                        )
                      }
                    >
                      <div className="truncate max-w-[120px]" title={row}>
                        {row}
                      </div>
                      <div className="text-[9px] text-slate-400 font-normal tabular-nums">
                        {(crossTab.rowTotals[row]?.count ?? 0).toLocaleString("ko-KR")}건
                      </div>
                    </td>
                    {crossTab.colLabels.map((col) => {
                      const cell =
                        crossTab.cells[crossCellKey(row, col)] ?? emptyCrossCell;
                      return (
                        <td
                          key={col}
                          className={clsx(
                            "px-1.5 py-1 text-center align-middle",
                            cell.count > 0 &&
                              "cursor-pointer hover:bg-blue-50/50",
                          )}
                          title={
                            cell.count > 0
                              ? "셀 클릭 → 행·열 조건 모두 목록 필터"
                              : undefined
                          }
                          onClick={() => {
                            if (cell.count === 0) return;
                            onDrillDown(
                              buildLandTxDrillDownFilters([
                                { dimension: rowDim, value: row },
                                { dimension: colDim, value: col },
                              ]),
                            );
                          }}
                        >
                          <CrossCellDisplay cell={cell} />
                        </td>
                      );
                    })}
                    <td className="px-1.5 py-1 text-center bg-slate-50/50 align-middle">
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
        {mode === "single"
          ? "행 클릭 → 목록 필터"
          : "셀=행+열 필터 · 행/열 헤더=한 축만 필터"}
      </p>
    </div>
  );
}
