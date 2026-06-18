export type StatsWindowYears = 3 | 5;

export function normalizeStatsWindowYears(v: unknown): StatsWindowYears {
  return v === 3 ? 3 : 5;
}

export default function StatsWindowToggle({
  value,
  onChange,
  disabled = false,
}: {
  value: StatsWindowYears;
  onChange: (y: StatsWindowYears) => void;
  disabled?: boolean;
}) {
  const choice = (y: StatsWindowYears, label: string) => {
    const active = value === y;
    return (
      <button
        key={y}
        type="button"
        aria-pressed={active}
        disabled={disabled}
        onClick={() => onChange(y)}
        className={`px-3 py-1 rounded-md text-[11px] font-semibold transition-colors disabled:opacity-50 ${
          active
            ? "bg-white dark:bg-slate-600 text-slate-800 dark:text-slate-100 shadow-sm"
            : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
        }`}
      >
        {label}
      </button>
    );
  };

  return (
    <div className="space-y-1">
      <span className="text-xs text-slate-500 dark:text-slate-400">롤링 구간</span>
      <div className="flex gap-0.5 bg-slate-100 dark:bg-slate-700 rounded-lg p-0.5" role="group" aria-label="계약일 기준 롤링 구간">
        {choice(3, "3년")}
        {choice(5, "5년")}
      </div>
    </div>
  );
}
