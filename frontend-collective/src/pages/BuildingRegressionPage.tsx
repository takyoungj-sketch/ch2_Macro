import { useEffect, useMemo, useState } from "react";
import BuildingRegressionPanel from "../components/BuildingRegressionPanel";
import { COLLECTIVE_EXPERIMENT_MODE, fetchBuildingKeyStatus, type BuildingKeyStatus } from "../api/client";
import type { AssetType } from "../types";
import { ASSET_LABELS } from "../types";
import MacroStatsHeader from "@ch2/macro-shell/MacroStatsHeader";
import { useUiColorScheme } from "@ch2/macro-shell/useUiColorScheme";
import { useUiFontScale } from "@ch2/macro-shell/useUiFontScale";
import AiAssistantPanel from "@ch2/ai-assistant/AiAssistantPanel";
import { Ai2HeaderSlot } from "@ch2/ai2-entry/Ai2Entry";
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
  // 집합 2단계 — 옛 키 링크: 1:1 이면 새 키로, 분할이면 후보를 고르게 한다.
  const [keyStatus, setKeyStatus] = useState<BuildingKeyStatus | null>(null);
  useEffect(() => {
    if (!params.buildingKey) return;
    let alive = true;
    void fetchBuildingKeyStatus(params.buildingKey).then((s) => {
      if (alive) setKeyStatus(s);
    });
    return () => {
      alive = false;
    };
  }, [params.buildingKey]);

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
          rightSlot={<Ai2HeaderSlot domain="collective"><AiAssistantPanel /></Ai2HeaderSlot>}
        />
        <div className="max-w-3xl mx-auto w-full p-4 md:p-6">
          <div className="card space-y-4">
            <p className="text-xs text-slate-500">{ASSET_LABELS[params.assetType]} · 별도 창 (레거시)</p>
            {keyStatus?.key_status === "split" ? (
              <div className="space-y-2 text-sm">
                <p className="text-slate-700 dark:text-slate-200">{keyStatus.message}</p>
                <ul className="space-y-1">
                  {keyStatus.candidates.map((c) => {
                    const u = new URL(window.location.href);
                    u.searchParams.set("building_key", c.building_key);
                    const where = [c.addr3, c.addr4, c.addr5].filter(Boolean).join(" ");
                    return (
                      <li key={c.building_key}>
                        <a className="text-blue-600 hover:underline dark:text-blue-400" href={u.toString()}>
                          {c.display_name || params.displayName || "단지"}
                          {where ? ` · ${where}` : ""}
                        </a>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ) : keyStatus === null ? (
              <p className="text-xs text-slate-500">단지 확인 중…</p>
            ) : (
            <BuildingRegressionPanel
              buildingKey={keyStatus.building_key}
              assetType={params.assetType}
              yearFrom={params.yearFrom}
              yearTo={params.yearTo}
              experiment={COLLECTIVE_EXPERIMENT_MODE}
            />
            )}
          </div>
        </div>
      </div>
    </ActiveAiViewProvider>
  );
}
