import { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import MacroStatsHeader from "@ch2/macro-shell/MacroStatsHeader";
import { useUiColorScheme } from "@ch2/macro-shell/useUiColorScheme";
import { useUiFontScale } from "@ch2/macro-shell/useUiFontScale";
import { fetchRegionalProfile, fetchTwinNeighbors, resolveRegionName } from "./api/profile";
import type { RegionLevel, RegionNameInfo, YearlyMix } from "./types";
import IdentityHeader from "./components/IdentityHeader";
import YearlyMixTable from "./components/YearlyMixTable";
import MarketComposition from "./components/MarketComposition";
import DominantMarketCard from "./components/DominantMarketCard";
import LandProfileCard from "./components/LandProfileCard";
import ApartmentProfileCard from "./components/ApartmentProfileCard";
import TwinRegionCard from "./components/TwinRegionCard";
import { cityShortLabel, formatProfileSelectionQuery } from "@ch2/region-picker";
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
  if (sel.regionLevel === "sigungu") return name.sigungu_name;
  if (sel.regionLevel === "beopjungri") return name.beopjungri_name;
  return name.eupmyeondong_name;
}

export default function App() {
  const [selection, setSelection] = useState<RegionSelection | null>(() => readSelectionFromUrl());
  const { contentZoom, fontPct, fontStepMin, fontStepMax, bumpUiFontScale } = useUiFontScale();
  const { isDark, toggleUiColorScheme } = useUiColorScheme();

  const handleSelect = useCallback((region: RegionSearchResult) => {
    const sel: RegionSelection = { regionLevel: region.level, regionCode: region.code };
    writeSelectionToUrl(sel);
    setSelection(sel);
  }, []);

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

  return (
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
      />

      <div className="flex-1 min-h-0 overflow-y-auto" style={{ zoom: contentZoom }}>
        <div className="mx-auto max-w-5xl px-4 py-6">
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
            <div className="space-y-5">
              {headerNode}

              {yearlyMix ? (
                <>
                  <YearlyMixTable yearlyMix={yearlyMix} />
                  <MarketComposition yearlyMix={yearlyMix} />
                  <DominantMarketCard
                    regionLevel={selection.regionLevel}
                    regionCode={selection.regionCode}
                    regionShortName={shortName}
                    yearlyMix={yearlyMix}
                    features={profileQuery.data.features}
                  />
                </>
              ) : (
                <div className="card p-5 text-sm text-slate-400">
                  8대 시장유형 연도별 데이터(yearly_mix)가 아직 없습니다.
                </div>
              )}

              <LandProfileCard features={profileQuery.data.features} />
              <ApartmentProfileCard
                regionLevel={selection.regionLevel}
                features={profileQuery.data.features}
              />

              {twinEnabled && (
                <TwinRegionCard
                  neighbors={twinQuery.data?.neighbors ?? []}
                  isLoading={twinQuery.isLoading}
                  isSigungu={isSigungu}
                  isBeop={isBeop}
                />
              )}

              <div className="pb-4 text-center text-[11px] text-slate-400">
                profile_version {profileQuery.data.meta.profile_version} · window {profileQuery.data.meta.window_years}
                y · as_of {profileQuery.data.meta.as_of_month}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
