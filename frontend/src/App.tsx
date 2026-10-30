import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import CollapsibleLeftSidebar from "@ch2/macro-shell/CollapsibleLeftSidebar";
import MacroStatsHeader from "@ch2/macro-shell/MacroStatsHeader";
import { useProductAccess } from "@ch2/macro-shell/productAccess";
import { useUiColorScheme } from "@ch2/macro-shell/useUiColorScheme";
import { useUiFontScale } from "@ch2/macro-shell/useUiFontScale";
import AiAssistantPanel from "@ch2/ai-assistant/AiAssistantPanel";
import { Ai2HeaderSlot } from "@ch2/ai2-entry/Ai2Entry";
import { ActiveAiViewProvider, emptyAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { CH2_AI_ACTION_EVENT, type AiScreenAction } from "@ch2/ai-assistant/aiActions";
import { fetchRegions } from "./api/client";
import { REGIONS_CATALOG_QUERY_KEY } from "./constants/regionsCatalog";
import { useLandDeepLink } from "./hooks/useLandDeepLink";
import { useAppStore } from "./store";
import { landScreenRegion } from "./utils/upperTierStats";
import RegionSelector from "./components/RegionSelector";
import RegionMapHub, { type MapPanelMode } from "./components/RegionMapHub";
import FreeStatsPanel from "./components/FreeStatsPanel";
import PaidAnalysisPanel from "./components/PaidAnalysisPanel";
import PaidFilterTable from "./components/PaidFilterTable";
import { setLandPickSingle } from "./regionPickMode";

const MOBILE_REGION_KEY = "ch2.land.mobileRegion";

function singleTier(tier: {
  sido_codes: string[];
  city_codes: string[];
  sigungu_codes: string[];
  eupmyeondong_codes: string[];
  beopjungri_codes: string[];
}): { level: string; code: string } | null {
  const rows: [string, string[]][] = [
    ["beopjungri", tier.beopjungri_codes],
    ["eupmyeondong", tier.eupmyeondong_codes],
    ["sigungu", tier.sigungu_codes],
    ["city", tier.city_codes],
    ["sido", tier.sido_codes],
  ];
  const total = rows.reduce((n, [, codes]) => n + codes.length, 0);
  if (total !== 1) return null;
  const hit = rows.find(([, codes]) => codes.length === 1);
  if (!hit) return null;
  return { level: hit[0], code: hit[1][0]! };
}

export default function App() {
  useLandDeepLink();
  const { entitled, narrow } = useProductAccess();
  const restoredMobileRegion = useRef(false);
  const { paidResultView, tierSelection, applyDeepLinkRegion } = useAppStore();
  const { data: regions = [] } = useQuery({
    queryKey: REGIONS_CATALOG_QUERY_KEY,
    queryFn: () => fetchRegions(),
    staleTime: 6 * 60 * 60 * 1000,
  });
  const screenRegion = useMemo(() => landScreenRegion(tierSelection, regions), [tierSelection, regions]);
  const [mapPanelMode, setMapPanelMode] = useState<MapPanelMode>("normal");
  const { contentZoom, fontPct, fontStepMin, fontStepMax, bumpUiFontScale } = useUiFontScale();
  const { isDark, toggleUiColorScheme } = useUiColorScheme();

  useEffect(() => {
    setLandPickSingle(narrow);
  }, [narrow]);

  useEffect(() => {
    if (!narrow) return;
    const saved = singleTier(tierSelection);
    if (!saved) return;
    try {
      window.localStorage.setItem(MOBILE_REGION_KEY, JSON.stringify(saved));
    } catch {
      /* ignore */
    }
  }, [narrow, tierSelection]);

  useEffect(() => {
    if (!narrow || restoredMobileRegion.current) return;
    restoredMobileRegion.current = true;
    if (singleTier(useAppStore.getState().tierSelection)) return;
    try {
      const raw = window.localStorage.getItem(MOBILE_REGION_KEY);
      if (!raw) return;
      const saved = JSON.parse(raw) as { level?: string; code?: string };
      if (saved.level && saved.code) applyDeepLinkRegion(saved.level, saved.code);
    } catch {
      /* ignore */
    }
  }, [narrow, applyDeepLinkRegion]);

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
    !narrow && entitled && paidResultView === "filtered" ? (
      <PaidAnalysisPanel />
    ) : paidResultView === "idle" ? null : (
      <FreeStatsPanel />
    );

  const aiSlot = entitled && !narrow ? (
    <Ai2HeaderSlot domain="land" screenRegion={screenRegion}>
      <AiAssistantPanel />
    </Ai2HeaderSlot>
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
        rightSlot={aiSlot}
      />

      <div className="flex flex-1 min-h-0 flex flex-col overflow-hidden" style={{ zoom: contentZoom }}>
        <main className={narrow ? "flex flex-1 min-h-0 flex-col overflow-hidden" : "flex flex-1 overflow-hidden min-h-0"}>
          {narrow ? (
            <div className="shrink-0 border-b border-slate-200 bg-white px-2 py-1 dark:border-slate-700 dark:bg-slate-800">
              <RegionSelector />
            </div>
          ) : (
            <CollapsibleLeftSidebar
              storageKey="land"
              className="layout-sidebar p-4 space-y-4"
            >
              <RegionSelector />
              <PaidFilterTable />
            </CollapsibleLeftSidebar>
          )}

          <div className={narrow ? "flex min-h-0 flex-1 flex-col overflow-hidden bg-slate-50 dark:bg-slate-900" : "layout-main"}>
            {narrow ? null : (
              <section className="px-4 pt-4 shrink-0">
                <RegionMapHub
                  fillHeight={mapPanelMode === "expanded"}
                  mapPanelMode={mapPanelMode}
                  onExpand={() => setMapPanelMode("expanded")}
                  onCollapse={() => setMapPanelMode("collapsed")}
                  onNormal={() => setMapPanelMode("normal")}
                />
              </section>
            )}
            {statsPanel ? (
              <div id="land-step-analysis" className={narrow ? "flex min-h-0 flex-1 flex-col px-1 py-1" : "p-4 pt-2 pb-8"}>
                {statsPanel}
              </div>
            ) : null}
          </div>
        </main>
      </div>
    </div>
    </ActiveAiViewProvider>
  );
}
