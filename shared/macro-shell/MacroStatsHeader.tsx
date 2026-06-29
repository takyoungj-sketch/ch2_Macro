// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
import type { ReactNode } from "react";
import DisplaySettingsControls from "./DisplaySettingsControls";
import MacroTypeNav, { type MacroAppKind } from "./MacroTypeNav";

type Props = {
  currentApp: MacroAppKind;
  title: string;
  subtitle?: ReactNode;
  badge?: ReactNode;
  fontPct: number;
  fontStepMin: boolean;
  fontStepMax: boolean;
  onBumpFont: (direction: 1 | -1) => void;
  isDark: boolean;
  onToggleTheme: () => void;
  rightSlot?: ReactNode;
};

export default function MacroStatsHeader({
  currentApp,
  title,
  subtitle,
  badge,
  fontPct,
  fontStepMin,
  fontStepMax,
  onBumpFont,
  isDark,
  onToggleTheme,
  rightSlot,
}: Props) {
  return (
    <header className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-6 py-3 shadow-sm shrink-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] text-slate-500 dark:text-slate-400 mb-0.5 flex flex-wrap items-center gap-1">
            <a href="/" className="hover:text-slate-700 dark:hover:text-slate-200">
              CH2 Macro
            </a>
            {badge}
          </p>
          <h1 className="text-base font-bold text-slate-800 dark:text-slate-100">{title}</h1>
          {subtitle ? (
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">{subtitle}</p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-3 shrink-0">
          <MacroTypeNav current={currentApp} />
          <DisplaySettingsControls
            fontPct={fontPct}
            fontStepMin={fontStepMin}
            fontStepMax={fontStepMax}
            onBump={onBumpFont}
            isDark={isDark}
            onToggleTheme={onToggleTheme}
          />
          {rightSlot}
        </div>
      </div>
    </header>
  );
}
