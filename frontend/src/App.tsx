import { useEffect, useState } from "react";
import MacroStatsHeader from "@ch2/macro-shell/MacroStatsHeader";
import { useUiColorScheme } from "@ch2/macro-shell/useUiColorScheme";
import { useUiFontScale } from "@ch2/macro-shell/useUiFontScale";
import AiAssistantPanel from "@ch2/ai-assistant/AiAssistantPanel";
import { ActiveAiViewProvider, emptyAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { CH2_AI_ACTION_EVENT, type AiScreenAction } from "@ch2/ai-assistant/aiActions";
import { useLandDeepLink } from "./hooks/useLandDeepLink";
import { useAppStore } from "./store";
import RegionSelector from "./components/RegionSelector";
import RegionMapHub, { type MapPanelMode } from "./components/RegionMapHub";
import FreeStatsPanel from "./components/FreeStatsPanel";
import PaidAnalysisPanel from "./components/PaidAnalysisPanel";
import PaidFilterTable from "./components/PaidFilterTable";

export default function App() {
  useLandDeepLink();
  const { paidResultView } = useAppStore();
  const [mapPanelMode, setMapPanelMode] = useState<MapPanelMode>("normal");
  const { contentZoom, fontPct, fontStepMin, fontStepMax, bumpUiFontScale } = useUiFontScale();
  const { isDark, toggleUiColorScheme } = useUiColorScheme();

  useEffect(() => {
    const on = (e: Event) => {
      const a = (e as CustomEvent<AiScreenAction>).detail;
      if (a?.ui !== "land_matrix") return;
      document.getElementById("land-step-analysis")?.scrollIntoView({ behavior: "smooth", block: "start" });
    };
    window.addEventListener(CH2_AI_ACTION_EVENT, on);
    return () => window.removeEventListener(CH2_AI_ACTION_EVENT, on);
  }, []);

  const statsPanel =
    paidResultView === "basic" ? (
      <FreeStatsPanel />
    ) : paidResultView === "filtered" ? (
      <PaidAnalysisPanel />
    ) : null;

  return (
    <ActiveAiViewProvider fallback={emptyAiContext("land", "PaidMatrixCell")}>
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
        rightSlot={<AiAssistantPanel />}
      />

      <div className="flex flex-1 min-h-0 flex flex-col overflow-hidden" style={{ zoom: contentZoom }}>
        <main className="flex flex-1 overflow-hidden min-h-0">
          <aside className="layout-sidebar p-4 space-y-4">
            <RegionSelector />
            <PaidFilterTable />
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
            {statsPanel ? <div id="land-step-analysis" className="p-4 pt-2 pb-8">{statsPanel}</div> : null}
          </div>
        </main>
      </div>
    </div>
    </ActiveAiViewProvider>
  );
}
