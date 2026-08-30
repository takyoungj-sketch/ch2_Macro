import { useMemo } from "react";
import BuildingRegressionPanel from "../components/BuildingRegressionPanel";
import { COLLECTIVE_EXPERIMENT_MODE } from "../api/client";
import type { AssetType } from "../types";
import { ASSET_LABELS } from "../types";
import MacroStatsHeader from "@ch2/macro-shell/MacroStatsHeader";
import { useUiColorScheme } from "@ch2/macro-shell/useUiColorScheme";
import { useUiFontScale } from "@ch2/macro-shell/useUiFontScale";
import AiAssistantPanel from "@ch2/ai-assistant/AiAssistantPanel";
import { ActiveAiViewProvider, emptyAiContext } from "@ch2/ai-assistant/ActiveAiView";

function parseSearchParams() {
  const p = new URLSearchParams(window.location.search);
  return {
    buildingKey: p.get("building_key") ?? "",
    displayName: p.get("display_name") ?? "",
    assetType: (p.get("asset_type") ?? "apartment") as AssetType,
    yearFrom: p.get("year_from") ? Number(p.get("year_from")) : undefined,
    yearTo: p.get("year_to") ? Number(p.get("year_to")) : undefined,
  };
}

export default function BuildingRegressionPage() {
  const params = useMemo(() => parseSearchParams(), []);
  const { fontPct, fontStepMin, fontStepMax, bumpUiFontScale } = useUiFontScale();
  const { isDark, toggleUiColorScheme } = useUiColorScheme();

  if (!params.buildingKey) {
    return (
      <div className="min-h-screen flex items-center justify-center text-sm text-slate-500">
        building_key가 필요합니다.
      </div>
    );
  }

  return (
    <ActiveAiViewProvider fallback={emptyAiContext("collective", "BuildingRegressionPanel")}>
      <div className="min-h-screen bg-slate-100 dark:bg-slate-900 flex flex-col">
        <MacroStatsHeader
          currentApp="collective"
          title={params.displayName || "건물 회귀"}
          fontPct={fontPct}
          fontStepMin={fontStepMin}
          fontStepMax={fontStepMax}
          onBumpFont={bumpUiFontScale}
          isDark={isDark}
          onToggleTheme={toggleUiColorScheme}
          rightSlot={<AiAssistantPanel />}
        />
        <div className="max-w-3xl mx-auto w-full p-4 md:p-6">
          <div className="card space-y-4">
            <p className="text-xs text-slate-500">{ASSET_LABELS[params.assetType]} · 별도 창 (레거시)</p>
            <BuildingRegressionPanel
              buildingKey={params.buildingKey}
              assetType={params.assetType}
              yearFrom={params.yearFrom}
              yearTo={params.yearTo}
              experiment={COLLECTIVE_EXPERIMENT_MODE}
            />
          </div>
        </div>
      </div>
    </ActiveAiViewProvider>
  );
}
