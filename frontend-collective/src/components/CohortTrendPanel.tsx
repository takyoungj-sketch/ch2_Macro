import clsx from "clsx";
import { useMemo } from "react";
import MultiBuildingTrendChart, { type CohortTrendMetric, type TrendSeries } from "./MultiBuildingTrendChart";
import type { LongTermPriceMetric } from "./LongTermMetricToggle";
import { buildWeightedMeanCombinedSeries } from "../utils/weightedMeanCombinedSeries";

export default function CohortTrendPanel({
  series,
  metric,
  onMetricChange,
  buildingCount,
  chartTitle,
  note,
  variant = "rolling",
  priceMetric,
  onPriceMetricChange,
}: {
  series: TrendSeries[];
  metric: CohortTrendMetric;
  onMetricChange: (m: CohortTrendMetric) => void;
  buildingCount: number;
  chartTitle: string;
  note?: string;
  /** rolling: 평균·건수 / longTerm: 평균·중앙값 */
  variant?: "rolling" | "longTerm";
  priceMetric?: LongTermPriceMetric;
  onPriceMetricChange?: (m: LongTermPriceMetric) => void;
}) {
  const chartMetric: CohortTrendMetric =
    variant === "longTerm" ? (priceMetric === "median" ? "median" : "mean") : metric;

  const combinedSeries = useMemo(() => {
    if (variant !== "longTerm" || priceMetric !== "mean" || series.length < 2) return null;
    return buildWeightedMeanCombinedSeries(series);
  }, [variant, priceMetric, series]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[10px] text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-100 dark:border-indigo-900 rounded px-2 py-1">
          {buildingCount}개 단지 비교 · 실시간
          {note ? <span className="text-slate-500 dark:text-slate-400"> · {note}</span> : null}
          {combinedSeries ? (
            <span className="text-slate-500 dark:text-slate-400"> · 통합(가중평균)은 아래 별도 칸</span>
          ) : null}
        </p>
        <div className="inline-flex rounded-md border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-800 p-0.5 text-[10px]">
          {variant === "longTerm" ? (
            <>
              <button
                type="button"
                className={clsx(
                  "px-2 py-0.5 rounded font-medium",
                  priceMetric === "mean"
                    ? "bg-white dark:bg-slate-700 shadow-sm text-slate-800 dark:text-slate-100"
                    : "text-slate-500 dark:text-slate-400",
                )}
                onClick={() => onPriceMetricChange?.("mean")}
              >
                평균(만원/㎡)
              </button>
              <button
                type="button"
                className={clsx(
                  "px-2 py-0.5 rounded font-medium",
                  priceMetric === "median"
                    ? "bg-white dark:bg-slate-700 shadow-sm text-slate-800 dark:text-slate-100"
                    : "text-slate-500 dark:text-slate-400",
                )}
                onClick={() => onPriceMetricChange?.("median")}
              >
                중앙값(만원/㎡)
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className={clsx(
                  "px-2 py-0.5 rounded font-medium",
                  metric === "mean"
                    ? "bg-white dark:bg-slate-700 shadow-sm text-slate-800 dark:text-slate-100"
                    : "text-slate-500 dark:text-slate-400",
                )}
                onClick={() => onMetricChange("mean")}
              >
                평균(만원/㎡)
              </button>
              <button
                type="button"
                className={clsx(
                  "px-2 py-0.5 rounded font-medium",
                  metric === "count"
                    ? "bg-white dark:bg-slate-700 shadow-sm text-slate-800 dark:text-slate-100"
                    : "text-slate-500 dark:text-slate-400",
                )}
                onClick={() => onMetricChange("count")}
              >
                거래 건수
              </button>
            </>
          )}
        </div>
      </div>
      <div className="modal-card px-2 py-3">
        <p className="text-[10px] font-semibold text-slate-600 dark:text-slate-300 px-1 mb-2">
          {variant === "longTerm" && series.length >= 2 ? "단지별 연도 추이 (꺾은선)" : chartTitle}
        </p>
        <MultiBuildingTrendChart series={series} metric={chartMetric} />
      </div>
      {combinedSeries && (
        <div className="modal-card px-2 py-3 border border-slate-200 dark:border-slate-600">
          <p className="text-[10px] font-semibold text-slate-700 dark:text-slate-200 px-1 mb-0.5">
            통합(거래수 가중평균)
          </p>
          <p className="text-[10px] text-slate-500 dark:text-slate-400 px-1 mb-2">
            Σ(n·단지평균) / Σn · 단지별 선과 축·스케일은 독립
          </p>
          <MultiBuildingTrendChart series={[combinedSeries]} metric="mean" />
        </div>
      )}
    </div>
  );
}
