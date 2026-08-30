import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import MacroStatsHeader from "@ch2/macro-shell/MacroStatsHeader";
import { useUiColorScheme } from "@ch2/macro-shell/useUiColorScheme";
import { useUiFontScale } from "@ch2/macro-shell/useUiFontScale";
import AiAssistantPanel from "@ch2/ai-assistant/AiAssistantPanel";
import { ActiveAiViewProvider, emptyAiContext, PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { CH2_AI_ACTION_EVENT, type AiScreenAction } from "@ch2/ai-assistant/aiActions";
import { fetchNationalRanks, fetchRegionalProfile, fetchRentProfileYearly, fetchTwinNeighbors, resolveRegionName } from "./api/profile";
import RentYearlyTable from "./components/RentYearlyTable";
import type { RegionLevel, RegionNameInfo, YearlyMix } from "./types";
import IdentityHeader from "./components/IdentityHeader";
import YearlyMixTable from "./components/YearlyMixTable";
import NationalRankCard from "./components/NationalRankCard";
import MarketComposition from "./components/MarketComposition";
import TypeCorrCard from "./components/TypeCorrCard";
import DominantMarketCard from "./components/DominantMarketCard";
import LandProfileCard from "./components/LandProfileCard";
import ApartmentProfileCard from "./components/ApartmentProfileCard";
import TwinRegionCard from "./components/TwinRegionCard";
import AnalysisLinks from "./components/AnalysisLinks";
import { cityShortLabel, formatProfileSelectionQuery, isSejongPseudoSigunguCode, isSejongRegionRow } from "@ch2/region-picker";
import RegionSearch, { type RegionSearchResult } from "./components/RegionSearch";
import { sidoName } from "./utils/sido";

interface RegionSelection {
  regionLevel: RegionLevel;
  regionCode: string;
}

function readSelectionFromUrl(): RegionSelection | null {
  const qs = new URLSearchParams(window.location.search);
  const level = qs.get("region_level") as RegionLevel | null;
  const code = qs.get("region_code");
  if (!level || !code) return null;
  if (!["sido", "sigungu", "eupmyeondong", "beopjungri", "city"].includes(level)) return null;
  return { regionLevel: level, regionCode: code };
}

function writeSelectionToUrl(sel: RegionSelection) {
  const qs = new URLSearchParams(window.location.search);
  qs.set("region_level", sel.regionLevel);
  qs.set("region_code", sel.regionCode);
  const url = `${window.location.pathname}?${qs.toString()}`;
  window.history.replaceState(null, "", url);
}

function regionShortName(sel: RegionSelection, name: RegionNameInfo | null): string {
  if (sel.regionLevel === "sido") return sidoName(sel.regionCode);
  if (sel.regionLevel === "city") return cityShortLabel(name, sel.regionCode);
  if (!name) return sel.regionCode;
  if (sel.regionLevel === "sigungu") {
    if (isSejongPseudoSigunguCode(sel.regionCode)) return `${name.sido_name || "세종특별자치시"} 전체`;
    return name.sigungu_name;
  }
  if (sel.regionLevel === "beopjungri") return name.beopjungri_name;
  if (isSejongRegionRow(name)) return name.sigungu_name;
  return name.eupmyeondong_name;
}

export default function App() {
  const [selection, setSelection] = useState<RegionSelection | null>(() => readSelectionFromUrl());
  const scrollRef = useRef<HTMLDivElement>(null);
  const { contentZoom, fontPct, fontStepMin, fontStepMax, bumpUiFontScale } = useUiFontScale();
  const { isDark, toggleUiColorScheme } = useUiColorScheme();

  const openRegion = useCallback((regionLevel: RegionLevel, regionCode: string) => {
    const sel: RegionSelection = { regionLevel, regionCode };
    writeSelectionToUrl(sel);
    setSelection(sel);
    scrollRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const handleSelect = useCallback((region: RegionSearchResult) => {
    openRegion(region.level, region.code);
  }, [openRegion]);

  const profileQuery = useQuery({
    queryKey: ["regional-profile", selection?.regionLevel, selection?.regionCode],
    queryFn: () => fetchRegionalProfile({ regionLevel: selection!.regionLevel, regionCode: selection!.regionCode }),
    enabled: !!selection,
    retry: false,
  });

  const regionNameQuery = useQuery({
    queryKey: ["region-name", "v2", selection?.regionLevel, selection?.regionCode],
    queryFn: () => resolveRegionName({ regionLevel: selection!.regionLevel, regionCode: selection!.regionCode }),
    enabled: !!selection,
    staleTime: Infinity,
    retry: 1,
  });

  const isSigungu = selection?.regionLevel === "sigungu";
  const isBeop = selection?.regionLevel === "beopjungri";
  const twinEnabled =
    !!selection &&
    (selection.regionLevel === "eupmyeondong" ||
      selection.regionLevel === "sigungu" ||
      selection.regionLevel === "beopjungri");
  const twinQuery = useQuery({
    queryKey: ["profile-twins", selection?.regionLevel, selection?.regionCode],
    queryFn: () => fetchTwinNeighbors({ regionLevel: selection!.regionLevel, regionCode: selection!.regionCode, topK: 5 }),
    enabled: twinEnabled,
    retry: false,
  });

  const yearlyMix = profileQuery.data?.features.yearly_mix as YearlyMix | undefined;
  const rankQuery = useQuery({
    queryKey: [
      "national-ranks",
      selection?.regionLevel,
      profileQuery.data?.meta.profile_version,
      profileQuery.data?.meta.window_years,
      profileQuery.data?.meta.as_of_month,
    ],
    queryFn: () =>
      fetchNationalRanks({
        regionLevel: selection!.regionLevel,
        profileVersion: profileQuery.data!.meta.profile_version,
        windowYears: profileQuery.data!.meta.window_years,
        asOfMonth: profileQuery.data!.meta.as_of_month,
      }),
    enabled: !!selection && !!profileQuery.data,
    staleTime: 60 * 60 * 1000,
    retry: false,
  });
  const rentYears = yearlyMix?.years?.filter((y) => Number.isFinite(y)) ?? [];
  const rentYearlyQuery = useQuery({
    queryKey: ["rent-profile-yearly", selection?.regionLevel, selection?.regionCode, rentYears],
    queryFn: () =>
      fetchRentProfileYearly({
        regionLevel: selection!.regionLevel,
        regionCode: selection!.regionCode,
        years: rentYears.length ? rentYears : undefined,
      }),
    enabled: !!selection && !!profileQuery.data,
    retry: false,
  });
  const shortName = selection ? regionShortName(selection, regionNameQuery.data ?? null) : "";

  const searchDisplayQuery = useMemo(() => {
    if (!selection) return "";
    return formatProfileSelectionQuery(
      selection.regionLevel,
      selection.regionCode,
      regionNameQuery.data ?? null,
      sidoName,
    );
  }, [selection, regionNameQuery.data]);

  const headerNode = useMemo(() => {
    if (!selection) return null;
    return (
      <IdentityHeader
        regionLevel={selection.regionLevel}
        regionCode={selection.regionCode}
        regionName={regionNameQuery.data ?? null}
        population={profileQuery.data?.features.population}
        yearlyMix={yearlyMix}
      />
    );
  }, [selection, regionNameQuery.data, profileQuery.data, yearlyMix]);

  const profileAiContext = useMemo(() => {
    if (!selection) return null;
    return {
      app: "profile" as const,
      panel: "RegionalProfile",
      purpose: "market_analysis" as const,
      scope: { region_label: shortName || selection.regionCode },
      facts: profileQuery.data
        ? {
            profile_version: profileQuery.data.meta.profile_version,
            as_of_month: profileQuery.data.meta.as_of_month,
            window_years: profileQuery.data.meta.window_years,
            region_level: selection.regionLevel,
            dominant_type: profileQuery.data.features.dominant_type ?? yearlyMix?.dominant_type,
            total_count_3y: yearlyMix?.total_count_3y,
          }
        : {},
    };
  }, [selection, shortName, profileQuery.data, yearlyMix]);

  useEffect(() => {
    const on = (e: Event) => {
      const a = (e as CustomEvent<AiScreenAction>).detail;
      if (a?.ui !== "profile_twin") return;
      document.getElementById("profile-step-twin")?.scrollIntoView({ behavior: "smooth", block: "start" });
    };
    window.addEventListener(CH2_AI_ACTION_EVENT, on);
    return () => window.removeEventListener(CH2_AI_ACTION_EVENT, on);
  }, []);

  return (
    <ActiveAiViewProvider fallback={emptyAiContext("profile", "RegionalProfile")}>
    <div className="h-screen flex flex-col overflow-hidden bg-slate-50 dark:bg-slate-900">
      <MacroStatsHeader
        profileActive
        title="지역 프로필"
        fontPct={fontPct}
        fontStepMin={fontStepMin}
        fontStepMax={fontStepMax}
        onBumpFont={bumpUiFontScale}
        isDark={isDark}
        onToggleTheme={toggleUiColorScheme}
        rightSlot={<AiAssistantPanel />}
      />
      <PublishAiContext context={profileAiContext} />

      <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto" style={{ zoom: contentZoom }}>
        <div className="mx-auto max-w-7xl px-4 py-6">
          <div className="mb-4 flex justify-end">
            <RegionSearch onSelect={handleSelect} displayQuery={searchDisplayQuery} />
          </div>

          {!selection && (
            <div className="card p-8 text-center text-slate-500 dark:text-slate-400">
              지역을 검색하거나, 토지·복합·집합 분석 화면 상단의 「지역프로필」으로 이동하세요.
            </div>
          )}

          {selection && profileQuery.isLoading && (
            <div className="card p-8 text-center text-slate-400">프로필을 불러오는 중...</div>
          )}

          {selection && profileQuery.isError && (
            <div className="card p-8 text-center text-rose-500">
              프로필을 찾을 수 없습니다 ({shortName || selection.regionCode}). 아직 Profile v2 재빌드가 반영되지 않은
              지역일 수 있습니다.
            </div>
          )}

          {selection && profileQuery.data && (
            <div className="flex flex-col gap-5 xl:flex-row xl:items-start">
              <aside className="w-full shrink-0 xl:w-[21.5rem]">
                <NationalRankCard
                  data={rankQuery.data}
                  isLoading={rankQuery.isLoading}
                  isError={rankQuery.isError}
                  focusCode={selection.regionCode}
                  focusName={shortName}
                />
              </aside>
              <div className="min-w-0 flex-1 space-y-5">
              {headerNode}
              <AnalysisLinks regionLevel={selection.regionLevel} regionCode={selection.regionCode} />

              {yearlyMix ? (
                <YearlyMixTable yearlyMix={yearlyMix} />
              ) : (
                <div className="card p-5 text-sm text-slate-400">
                  8대 시장유형 연도별 데이터(yearly_mix)가 아직 없습니다.
                </div>
              )}

              {rentYearlyQuery.data ? (
                <RentYearlyTable
                  data={rentYearlyQuery.data}
                  regionLevel={selection.regionLevel}
                  regionCode={selection.regionCode}
                />
              ) : rentYearlyQuery.isError ? (
                <div className="card p-5 text-sm text-slate-400">
                  주거 전월세 연간 집계를 불러오지 못했습니다.
                </div>
              ) : rentYearlyQuery.isLoading ? (
                <div className="card p-5 text-sm text-slate-400">주거 전월세를 집계하는 중…</div>
              ) : null}

              {yearlyMix ? (
                <>
                  <MarketComposition
                    yearlyMix={yearlyMix}
                    nationalShare={rankQuery.data?.national_share_by_type}
                  />
                  <TypeCorrCard data={rankQuery.data?.type_corr} />
                  <DominantMarketCard
                    regionLevel={selection.regionLevel}
                    regionCode={selection.regionCode}
                    regionShortName={shortName}
                    yearlyMix={yearlyMix}
                    features={profileQuery.data.features}
                  />
                </>
              ) : null}

              <LandProfileCard
                regionLevel={selection.regionLevel}
                regionCode={selection.regionCode}
                features={profileQuery.data.features}
              />
              <ApartmentProfileCard
                regionLevel={selection.regionLevel}
                regionCode={selection.regionCode}
                features={profileQuery.data.features}
              />

              {twinEnabled && (
                <div id="profile-step-twin">
                <TwinRegionCard
                  neighbors={twinQuery.data?.neighbors ?? []}
                  isLoading={twinQuery.isLoading}
                  isSigungu={isSigungu}
                  isBeop={isBeop}
                  onOpenTwin={openRegion}
                />
                </div>
              )}

              <div className="pb-4 text-center text-[11px] text-slate-400">
                profile_version {profileQuery.data.meta.profile_version} · window {profileQuery.data.meta.window_years}
                y · as_of {profileQuery.data.meta.as_of_month}
              </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
    </ActiveAiViewProvider>
  );
}
