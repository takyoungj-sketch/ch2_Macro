import clsx from "clsx";
import type { AreaRollingSeries } from "../types";
import MultiBuildingTrendChart from "./MultiBuildingTrendChart";
import { longTermPriceLabel, type LongTermPriceMetric } from "./LongTermMetricToggle";

export type RollingScope = "all" | "area";

function fmtPrice(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString("ko-KR", { maximumFractionDigits: 1 });
}

export function RollingScopeToggle({
  value,
  onChange,
  areaLabel,
}: {
  value: RollingScope;
  onChange: (next: RollingScope) => void;
  areaLabel: string;
}) {
  return (
    <div
      className="inline-flex rounded-md border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-800 p-0.5 text-xs"
      role="group"
      aria-label="롤링 구간 범위"
    >
      {(
        [
          ["all", "전체"],
          ["area", areaLabel],
        ] as const
      ).map(([id, label]) => (
        <button
          key={id}
          type="button"
          aria-pressed={value === id}
          className={clsx(
            "px-2 py-0.5 rounded font-medium",
            value === id
              ? "bg-white dark:bg-slate-700 shadow-sm text-slate-800 dark:text-slate-100"
              : "text-slate-500 dark:text-slate-400",
          )}
          onClick={() => onChange(id)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

/** 면적형 버튼이 눌린 뒤의 롤링 차트와 표. 25·75는 그리지 않는다. */
export default function AreaRollingView({
  series,
  metric,
  areaRule,
  areaColumnLabel,
}: {
  series: AreaRollingSeries[];
  metric: LongTermPriceMetric;
  areaRule: string;
  areaColumnLabel: string;
}) {
  const chartSeries = series.map((item) => ({
    label: item.area_label,
    points: [...item.points]
      .sort((a, b) => a.bucket_index - b.bucket_index)
      .map((point) => ({
        xLabel: point.label,
        xOrder: point.bucket_index,
        count: point.count,
        mean: point.mean,
        median: point.median,
      })),
  }));
  const rows = series.flatMap((item) =>
    [...item.points]
      .sort((a, b) => a.bucket_index - b.bucket_index)
      .map((point) => ({
        key: `${item.area_sort}-${item.area_label}-${point.bucket_index}`,
        area: item.area_label,
        label: point.label,
        count: point.count,
        price: metric === "median" ? point.median : point.mean,
      })),
  );

  return (
    <>
      <p className="text-[11px] text-slate-500 dark:text-slate-400 px-1 mb-2">{areaRule}</p>
      <MultiBuildingTrendChart
        series={chartSeries}
        metric={metric}
        showQuartiles={false}
        showValueLabels={chartSeries.length <= 1}
        ariaLabel={`${areaColumnLabel}별 롤링 구간 추이`}
      />
      <div className="modal-table-wrap mt-3">
        <p className="text-xs font-semibold text-slate-600 dark:text-slate-300 px-3 pt-3 pb-1">
          {areaColumnLabel}별 수치
        </p>
        <table className="w-full text-xs border-collapse modal-inner-table">
          <thead>
            <tr>
              <th className="border px-2 py-1.5 text-left font-medium">{areaColumnLabel}</th>
              <th className="border px-2 py-1.5 text-left font-medium">구간</th>
              <th className="border px-2 py-1.5 text-right font-medium">건수</th>
              <th className="border px-2 py-1.5 text-right font-bold text-blue-700 dark:text-blue-400">
                {longTermPriceLabel(metric)}(만원/㎡)
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <td className="border px-2 py-1">{row.area}</td>
                <td className="border px-2 py-1 tabular-nums">{row.label}</td>
                <td className="border px-2 py-1 text-right tabular-nums">{row.count.toLocaleString("ko-KR")}</td>
                <td className="border px-2 py-1 text-right tabular-nums text-blue-600 dark:text-blue-400 font-bold">
                  {row.price != null ? fmtPrice(row.price) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
