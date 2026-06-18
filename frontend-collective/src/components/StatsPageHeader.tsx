import DisplaySettingsControls from "./DisplaySettingsControls";

type Props = {
  title: string;
  subtitle: React.ReactNode;
  fontPct: number;
  fontStepMin: boolean;
  fontStepMax: boolean;
  onBumpFont: (direction: 1 | -1) => void;
  isDark: boolean;
  onToggleTheme: () => void;
};

export default function StatsPageHeader({
  title,
  subtitle,
  fontPct,
  fontStepMin,
  fontStepMax,
  onBumpFont,
  isDark,
  onToggleTheme,
}: Props) {
  return (
    <header className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-6 py-3 shadow-sm shrink-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] text-slate-500 dark:text-slate-400 mb-0.5">
            <a href="/" className="hover:text-slate-700 dark:hover:text-slate-200">
              CH2 Macro
            </a>
            {" · "}
            <a href="/land/" className="hover:text-slate-700 dark:hover:text-slate-200">
              토지
            </a>
            {" · "}
            <a href="/built/" className="hover:text-slate-700 dark:hover:text-slate-200">
              복합
            </a>
            {" · "}
            <a href="/collective/" className="hover:text-slate-700 dark:hover:text-slate-200">
              집합
            </a>
          </p>
          <h1 className="text-base font-bold text-slate-800 dark:text-slate-100">{title}</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">{subtitle}</p>
        </div>
        <DisplaySettingsControls
          fontPct={fontPct}
          fontStepMin={fontStepMin}
          fontStepMax={fontStepMax}
          onBump={onBumpFont}
          isDark={isDark}
          onToggleTheme={onToggleTheme}
        />
      </div>
    </header>
  );
}
