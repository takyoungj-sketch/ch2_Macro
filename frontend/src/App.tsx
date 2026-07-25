import { useState } from "react";
import MacroStatsHeader from "@ch2/macro-shell/MacroStatsHeader";
import { useUiColorScheme } from "@ch2/macro-shell/useUiColorScheme";
import { useUiFontScale } from "@ch2/macro-shell/useUiFontScale";
import { useAppStore } from "./store";
import RegionSelector from "./components/RegionSelector";
import RegionMapHub, { type MapPanelMode } from "./components/RegionMapHub";
import FreeStatsPanel from "./components/FreeStatsPanel";
import PaidAnalysisPanel from "./components/PaidAnalysisPanel";
import PaidFilterTable from "./components/PaidFilterTable";

export default function App() {
  const { viewMode, setViewMode, paidResultView } = useAppStore();
  const [mapPanelMode, setMapPanelMode] = useState<MapPanelMode>("normal");
  const { contentZoom, fontPct, fontStepMin, fontStepMax, bumpUiFontScale } = useUiFontScale();
  const { isDark, toggleUiColorScheme } = useUiColorScheme();

  const statsPanel =
    viewMode === "free" ? (
      <FreeStatsPanel />
    ) : paidResultView === "basic" ? (
      <FreeStatsPanel />
    ) : paidResultView === "filtered" ? (
      <PaidAnalysisPanel />
    ) : null;

  const viewModeTabs = (
    <div className="flex flex-col gap-1 bg-slate-100 dark:bg-slate-700 rounded-lg p-1">
      <button
        type="button"
        onClick={() => setViewMode("free")}
        className={`w-full px-3 py-1.5 rounded-md text-xs font-semibold transition-colors text-left ${
          viewMode === "free"
            ? "bg-white dark:bg-slate-600 text-blue-700 dark:text-blue-300 shadow-sm"
            : "text-slate-500 dark:text-slate-300 hover:text-slate-700 dark:hover:text-slate-100"
        }`}
      >
        무료 통계
      </button>
      <button
        type="button"
        onClick={() => setViewMode("paid")}
        className={`w-full px-3 py-1.5 rounded-md text-xs font-semibold transition-colors text-left ${
          viewMode === "paid"
            ? "bg-white dark:bg-slate-600 text-blue-700 dark:text-blue-300 shadow-sm"
            : "text-slate-500 dark:text-slate-300 hover:text-slate-700 dark:hover:text-slate-100"
        }`}
      >
        유료 분석
      </button>
    </div>
  );

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-slate-50 dark:bg-slate-900">
      <MacroStatsHeader
        currentApp="land"
        title="토지 실거래 통계"
        fontPct={fontPct}
        fontStepMin={fontStepMin}
        fontStepMax={fontStepMax}
        onBumpFont={bumpUiFontScale}
        isDark={isDark}
        onToggleTheme={toggleUiColorScheme}
      />

      <div className="flex flex-1 min-h-0 flex flex-col overflow-hidden" style={{ zoom: contentZoom }}>
        <main className="flex flex-1 overflow-hidden min-h-0">
          <aside className="layout-sidebar p-4 space-y-4">
            <div className="space-y-2">
              <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">화면</p>
              {viewModeTabs}
            </div>
            <RegionSelector />
            {viewMode === "paid" && <PaidFilterTable />}
          </aside>

          <div className="layout-main">
            <section className="px-4 pt-4 shrink-0">
              <RegionMapHub
                fillHeight={mapPanelMode === "expanded"}
                mapPanelMode={mapPanelMode}
                onExpand={() => setMapPanelMode("expanded")}
                onCollapse={() => setMapPanelMode("collapsed")}
                onNormal={() => setMapPanelMode("normal")}
              />
            </section>
            {statsPanel ? <div className="p-4 pt-2 pb-8">{statsPanel}</div> : null}
          </div>
        </main>
      </div>
    </div>
  );
}
