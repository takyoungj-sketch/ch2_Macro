// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
import type { ReactNode } from "react";
import "./headerToolbar.css";
import DisplaySettingsControls from "./DisplaySettingsControls";
import MacroProfileNavLink from "./MacroProfileNavLink";
import MacroTypeNav, { type MacroAppKind } from "./MacroTypeNav";

type Props = {
  /** stats 앱(토지·복합·집합) 중 현재 페이지. 지역프로필 단독 화면이면 null */
  currentApp?: MacroAppKind | null;
  profileActive?: boolean;
  title: string;
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
  currentApp = null,
  profileActive = false,
  title,
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
    <header className="ch2-macro-stats-header">
      <div className="macro-header-row">
        <div className="macro-header-title">
          <p className="macro-header-breadcrumb">
            <a href="/" className="macro-header-home">
              CH2 Macro
            </a>
            {badge ? <span className="macro-header-badge-slot">{badge}</span> : null}
          </p>
          <h1>{title}</h1>
        </div>
        <div className="macro-header-toolbar">
          <div className="macro-header-nav-cluster">
            <MacroProfileNavLink active={profileActive} />
            <MacroTypeNav current={currentApp} />
          </div>
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
