import clsx from "clsx";

export type LongTermPriceMetric = "mean" | "median";

export function longTermPriceLabel(metric: LongTermPriceMetric): string {
  return metric === "median" ? "중앙값" : "평균";
}

export default function LongTermMetricToggle({
  metric,
  onChange,
  showQuartiles = false,
  onQuartilesChange,
}: {
  metric: LongTermPriceMetric;
  onChange: (m: LongTermPriceMetric) => void;
  showQuartiles?: boolean;
  onQuartilesChange?: (on: boolean) => void;
}) {
  return (
    <div
      className="inline-flex rounded-md border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-800 p-0.5 text-xs"
      role="group"
      aria-label="장기 추세선 기준"
    >
      {(
        [
          ["mean", "평균"],
          ["median", "중앙값"],
        ] as const
      ).map(([id, label]) => (
        <button
          key={id}
          type="button"
          aria-pressed={metric === id}
          className={clsx(
            "px-2 py-0.5 rounded font-medium",
            metric === id
              ? "bg-white dark:bg-slate-700 shadow-sm text-slate-800 dark:text-slate-100"
              : "text-slate-500 dark:text-slate-400",
          )}
          onClick={() => {
            onChange(id);
            if (id !== "median") onQuartilesChange?.(false);
          }}
        >
          {label}
        </button>
      ))}
      {onQuartilesChange && (
        <button
          type="button"
          aria-pressed={metric === "median" && showQuartiles}
          disabled={metric !== "median"}
          className={clsx(
            "px-2 py-0.5 rounded font-medium",
            metric !== "median" && "text-slate-300 dark:text-slate-600 cursor-not-allowed",
            metric === "median" && showQuartiles && "bg-white dark:bg-slate-700 shadow-sm text-slate-800 dark:text-slate-100",
            metric === "median" && !showQuartiles && "text-slate-500 dark:text-slate-400",
          )}
          onClick={() => onQuartilesChange(!showQuartiles)}
        >
          25·75
        </button>
      )}
    </div>
  );
}
