import { StatsGlossaryHelp } from "@ch2/stats-glossary";

export type StatsWindowYears = 3 | 5 | 7;

export function normalizeStatsWindowYears(v: unknown): StatsWindowYears {
  if (v === 3 || v === "3") return 3;
  if (v === 7 || v === "7") return 7;
  return 5;
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
  const choice = (id: string, label: string, active: boolean, onClick: () => void) => (
    <button
      key={id}
      type="button"
      aria-pressed={active}
      disabled={disabled}
      onClick={onClick}
      className={`px-3 py-1 rounded-md text-[11px] font-semibold transition-colors disabled:opacity-50 ${
        active
          ? "bg-white dark:bg-slate-600 text-slate-800 dark:text-slate-100 shadow-sm"
          : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="space-y-1">
      <span className="text-xs text-slate-500 dark:text-slate-400 inline-flex items-center gap-1">
        롤링 구간
        <StatsGlossaryHelp termId="rolling_window" size="xs" />
      </span>
      <div className="flex gap-0.5 bg-slate-100 dark:bg-slate-700 rounded-lg p-0.5" role="group" aria-label="계약일 기준 롤링 구간">
        {choice("3", "3년", value === 3, () => onChange(3))}
        {choice("5", "5년", value === 5, () => onChange(5))}
        {choice("7", "7년", value === 7, () => onChange(7))}
      </div>
    </div>
  );
}
