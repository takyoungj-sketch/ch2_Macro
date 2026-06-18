type Props = {
  fontPct: number;
  fontStepMin: boolean;
  fontStepMax: boolean;
  onBump: (direction: 1 | -1) => void;
  isDark: boolean;
  onToggleTheme: () => void;
};

export default function DisplaySettingsControls({
  fontPct,
  fontStepMin,
  fontStepMax,
  onBump,
  isDark,
  onToggleTheme,
}: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs shrink-0" aria-label="화면 표시 설정">
      <button
        type="button"
        role="switch"
        aria-checked={isDark}
        aria-label={isDark ? "밝은 테마로 전환" : "어두운 테마로 전환"}
        title={isDark ? "밝은 테마" : "어두운 테마"}
        className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-medium transition-colors ${
          isDark
            ? "border-slate-600 bg-slate-700 text-slate-100 hover:bg-slate-600"
            : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-white"
        }`}
        onClick={onToggleTheme}
      >
        <span aria-hidden>{isDark ? "☀" : "☾"}</span>
        <span className="hidden sm:inline">{isDark ? "밝게" : "어둡게"}</span>
      </button>
      <span className="text-[11px] text-slate-500 dark:text-slate-400 hidden sm:inline">글자</span>
      <div className="flex items-center gap-0.5 border border-slate-200 dark:border-slate-600 rounded-md bg-slate-50/90 dark:bg-slate-700/90 p-0.5">
        <button
          type="button"
          className="w-8 h-7 rounded text-sm font-semibold leading-none text-slate-700 dark:text-slate-200 hover:bg-white dark:hover:bg-slate-600 disabled:opacity-40 disabled:hover:bg-transparent"
          aria-label="글자 크기 줄이기"
          disabled={fontStepMin}
          onClick={() => onBump(-1)}
        >
          −
        </button>
        <span
          className="min-w-[2.85rem] text-center tabular-nums font-medium text-[11px] text-slate-600 dark:text-slate-300"
          aria-live="polite"
        >
          {fontPct}%
        </span>
        <button
          type="button"
          className="w-8 h-7 rounded text-sm font-semibold leading-none text-slate-700 dark:text-slate-200 hover:bg-white dark:hover:bg-slate-600 disabled:opacity-40 disabled:hover:bg-transparent"
          aria-label="글자 크기 키우기"
          disabled={fontStepMax}
          onClick={() => onBump(1)}
        >
          +
        </button>
      </div>
    </div>
  );
}
