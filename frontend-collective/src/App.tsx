import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import {
  fetchAddr1List,
  fetchAddr2,
  fetchAddr3WithCounts,
  fetchAllBuildings,
  fetchFilterMeta,
  fetchLeafRegions,
  fetchRegionStructure,
  type BuildingStatsRow,
} from "./api/client";
import { CH2_AI_ACTION_EVENT, type AiScreenAction } from "@ch2/ai-assistant/aiActions";
import { fetchCollectiveMapResolveCodes } from "./api/mapClient";
import BuildingStatsTable, { buildingMatchesQuery } from "./components/BuildingStatsTable";
import StatsTableExpandButton from "./components/StatsTableExpandButton";
import BuildingDetailModal from "./components/BuildingDetailModal";
import RegionalRegressionModal from "./components/RegionalRegressionModal";
import CollectiveRegionMapHub, { type MapPanelMode } from "./components/CollectiveRegionMapHub";
import CollapsibleLeftSidebar from "@ch2/macro-shell/CollapsibleLeftSidebar";
import MacroStatsHeader from "@ch2/macro-shell/MacroStatsHeader";
import { useUiColorScheme } from "@ch2/macro-shell/useUiColorScheme";
import { useUiFontScale } from "@ch2/macro-shell/useUiFontScale";
import AiAssistantPanel from "@ch2/ai-assistant/AiAssistantPanel";
import { ActiveAiViewProvider, emptyAiContext, PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import RegionChipPanel, {
  LEFT_REGION_MULTI_SELECT,
  formatLeafChipLabel,
  toggleChipMulti,
  toggleChipSingle,
} from "./components/RegionChipPanel";
import StatsWindowToggle, {
  normalizeStatsWindowYears,
  type StatsWindowYears,
} from "./components/StatsWindowToggle";
import type { AssetSelectorType, RegionOption } from "./types";
import {
  hasYearFilter,
} from "./utils/contractYearRange";
import {
  formatAddr2OptionLabel,
  formatScopeAddr2,
  isFlatSidoAddr2,
} from "./utils/flatSidoRegion";
import {
  mergeRegionChipOptions,
  orderedSidoPrefetchList,
  REGION_LIST_STALE_MS,
} from "./utils/regionListCache";
import {
  encodeResidentialAssetKinds,
  RESIDENTIAL_ASSET_KINDS,
  RESIDENTIAL_KIND_LABELS,
  toggleResidentialAssetKind,
  type ResidentialAssetKind,
} from "./utils/residentialAssetTypes";
import { useCollectiveDeepLink } from "./hooks/useCollectiveDeepLink";
import { profileHref, resolveCollectiveProfileTarget } from "./utils/profileLink";
import { buildCollectiveListContext } from "./api/aiContext";
import { useCollectiveAnalysisUnits } from "./hooks/useCollectiveAnalysisUnits";
import { useCollectiveScopeStale } from "./hooks/useCollectiveScopeStale";
import {
  analysisUnitLabel,
  MAX_COLLECTIVE_ANALYSIS_UNITS,
} from "./utils/collectiveAnalysisUnits";
type AnalysisScope = {
  assetType: AssetSelectorType;
  addr1: string;
  addr2: string;
  guList: string[];
  leafList: string[];
  hasIntermediate: boolean;
  yearFrom: number | "";
  yearTo: number | "";
  windowYears: StatsWindowYears;
  sort: string;
  region_codes?: string[];
  region_code_level?: "eupmyeondong" | "beopjungri";
  region_addrs?: string[];
};

export default function App() {
  const qc = useQueryClient();
  const [assetKinds, setAssetKinds] = useState<ResidentialAssetKind[]>(["apartment"]);
  const assetType = useMemo(() => encodeResidentialAssetKinds(assetKinds), [assetKinds]);
  const [addr1, setAddr1] = useState("");
  const [addr2, setAddr2] = useState("");
  const [guList, setGuList] = useState<string[]>([]);
  const [leafList, setLeafList] = useState<string[]>([]);
  const {
    analysisUnits,
    setAnalysisUnits,
    regionCodeScope,
    profileTarget: unitsProfile,
    removeAnalysisUnit,
    addUnit,
    clearUnits,
  } = useCollectiveAnalysisUnits({
    assetType,
    addr1,
    addr2,
    guList,
    leafList,
    setLeafList,
  });
  const [yearFrom, setYearFrom] = useState<number | "">("");
  const [yearTo, setYearTo] = useState<number | "">("");
  const [windowYears, setWindowYears] = useState<StatsWindowYears>(5);
  const [scope, setScope] = useState<AnalysisScope | null>(null);
  const [selected, setSelected] = useState<BuildingStatsRow | null>(null);
  const [regionalOpen, setRegionalOpen] = useState(false);
  const [aiHint, setAiHint] = useState<string | null>(null);
  const [buildingSearch, setBuildingSearch] = useState("");
  const [mapPanelMode, setMapPanelMode] = useState<MapPanelMode>("normal");
  const [tableWide, setTableWide] = useState(false);
  const { contentZoom, fontPct, fontStepMin, fontStepMax, bumpUiFontScale } = useUiFontScale();
  const { isDark, toggleUiColorScheme } = useUiColorScheme();

  const addr1Q = useQuery({
    queryKey: ["coll-addr1"],
    queryFn: fetchAddr1List,
    staleTime: 24 * 60 * 60_000,
    placeholderData: (prev) => prev,
  });
  const metaQ = useQuery({
    queryKey: ["coll-meta"],
    queryFn: () => fetchFilterMeta(),
    staleTime: 60_000,
    placeholderData: (prev) => prev,
  });
  const addr2Q = useQuery({
    queryKey: ["coll-addr2", addr1, assetType],
    queryFn: () => fetchAddr2(addr1, assetType),
    enabled: !!addr1,
    staleTime: REGION_LIST_STALE_MS,
  });

  useEffect(() => {
    const sidos = addr1Q.data ?? [];
    if (!sidos.length) return;
    let cancelled = false;
    (async () => {
      for (const sido of orderedSidoPrefetchList(sidos)) {
        if (cancelled) return;
        await qc.prefetchQuery({
          queryKey: ["coll-addr2", sido, assetType],
          queryFn: () => fetchAddr2(sido, assetType),
          staleTime: REGION_LIST_STALE_MS,
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [qc, assetType, addr1Q.data]);

  useEffect(() => {
    if (!addr1 || addr2) return;
    const opts = addr2Q.data ?? [];
    if (opts.length === 1 && isFlatSidoAddr2(opts[0])) {
      setAddr2(opts[0]!);
    }
  }, [addr1, addr2, addr2Q.data]);
  const structureQ = useQuery({
    queryKey: ["coll-structure", addr1, addr2, assetType],
    queryFn: () => fetchRegionStructure(addr1, addr2, assetType),
    enabled: !!addr1 && !!addr2,
    staleTime: REGION_LIST_STALE_MS,
  });
  const hasIntermediate = structureQ.data?.has_intermediate ?? false;
  const intermediateLabel = structureQ.data?.intermediate_label ?? "구";
  const chipsReady = !!addr1 && !!addr2 && structureQ.isSuccess;

  const regionPeriod = hasYearFilter(yearFrom, yearTo)
    ? {
        contract_year_from: yearFrom === "" ? undefined : yearFrom,
        contract_year_to: yearTo === "" ? undefined : yearTo,
      }
    : undefined;

  const guNamesQ = useQuery({
    queryKey: ["coll-gu-names", addr1, addr2, assetType],
    queryFn: () => fetchAddr3WithCounts(addr1, addr2, assetType, undefined, true),
    enabled: chipsReady && hasIntermediate,
    staleTime: REGION_LIST_STALE_MS,
  });
  const guCountsQ = useQuery({
    queryKey: ["coll-gu", addr1, addr2, assetType, regionPeriod],
    queryFn: () => fetchAddr3WithCounts(addr1, addr2, assetType, regionPeriod),
    enabled: chipsReady && hasIntermediate,
    staleTime: REGION_LIST_STALE_MS,
  });
  const guOptions = useMemo(
    () => mergeRegionChipOptions(guNamesQ.data, guCountsQ.data),
    [guNamesQ.data, guCountsQ.data],
  );

  const flatLeafNamesQ = useQuery({
    queryKey: ["coll-flat-leaf-names", addr1, addr2, assetType],
    queryFn: () => fetchAddr3WithCounts(addr1, addr2, assetType, undefined, true),
    enabled: chipsReady && !hasIntermediate,
    staleTime: REGION_LIST_STALE_MS,
  });
  const flatLeafCountsQ = useQuery({
    queryKey: ["coll-flat-leaf", addr1, addr2, assetType, regionPeriod],
    queryFn: () => fetchAddr3WithCounts(addr1, addr2, assetType, regionPeriod),
    enabled: chipsReady && !hasIntermediate,
    staleTime: REGION_LIST_STALE_MS,
  });
  const leafNamesQ = useQuery({
    queryKey: ["coll-leaf-names", addr1, addr2, assetType, guList],
    queryFn: () => fetchLeafRegions(addr1, addr2, guList, assetType, undefined, true),
    enabled: chipsReady && hasIntermediate,
    staleTime: REGION_LIST_STALE_MS,
  });
  const leafCountsQ = useQuery({
    queryKey: ["coll-leaf", addr1, addr2, assetType, guList, regionPeriod],
    queryFn: () => fetchLeafRegions(addr1, addr2, guList, assetType, regionPeriod),
    enabled: chipsReady && hasIntermediate,
    staleTime: REGION_LIST_STALE_MS,
  });

  const visibleLeafOptions = useMemo(() => {
    if (!hasIntermediate) {
      return mergeRegionChipOptions(flatLeafNamesQ.data, flatLeafCountsQ.data).map((o: RegionOption) => ({
        ...o,
        id: o.name,
      }));
    }
    const opts = mergeRegionChipOptions(leafNamesQ.data, leafCountsQ.data);
    const filtered = !guList.length ? opts : opts.filter((o) => o.parent && guList.includes(o.parent));
    return filtered.map((o) => ({ ...o, id: `${o.parent ?? ""}|${o.name}` }));
  }, [
    hasIntermediate,
    flatLeafNamesQ.data,
    flatLeafCountsQ.data,
    leafNamesQ.data,
    leafCountsQ.data,
    guList,
  ]);
  const leafCountsReady = hasIntermediate ? leafCountsQ.isSuccess : flatLeafCountsQ.isSuccess;

  useEffect(() => {
    if (!hasIntermediate) return;
    const allowed = new Set(visibleLeafOptions.map((o) => o.name));
    setLeafList((prev) => {
      const next = prev.filter((n) => allowed.has(n));
      if (next.length === prev.length && next.every((n, i) => n === prev[i])) return prev;
      return next;
    });
  }, [hasIntermediate, visibleLeafOptions]);

  useCollectiveDeepLink({
    addr1,
    addr2,
    addr1Options: addr1Q.data ?? [],
    addr2Options: addr2Q.data ?? [],
    leafOptions: visibleLeafOptions,
    setAddr1,
    setAddr2,
    setLeafList,
    setGuList,
  });

  const buildingsQ = useQuery({
    queryKey: ["coll-buildings", scope],
    queryFn: () => {
      if (!scope) throw new Error("no scope");
      const regionParams = scope.hasIntermediate
        ? {
            addr3_list: scope.guList.length ? scope.guList : undefined,
            addr4_list: scope.leafList.length ? scope.leafList : undefined,
          }
        : { addr3_list: scope.leafList.length ? scope.leafList : undefined };
      return fetchAllBuildings({
        asset_type: scope.assetType,
        addr1: scope.addr1,
        addr2: scope.addr2,
        ...regionParams,
        region_codes: scope.region_codes,
        region_code_level: scope.region_code_level,
        region_addrs: scope.region_addrs,
        contract_year_from: scope.yearFrom === "" ? undefined : scope.yearFrom,
        contract_year_to: scope.yearTo === "" ? undefined : scope.yearTo,
        window_years: scope.windowYears,
        presale_stats_mode: "rolling",
        sort: "count",
      });
    },
    enabled: scope !== null && !!scope.addr2,
  });

  const profileResolveQ = useQuery({
    queryKey: ["coll-profile-resolve", scope],
    queryFn: () =>
      fetchCollectiveMapResolveCodes({
        assetType: scope!.assetType,
        addr1: scope!.addr1,
        addr2: scope!.addr2,
        gu: scope!.hasIntermediate ? scope!.guList : [],
        leaf: scope!.leafList,
      }),
    enabled: scope !== null && !!scope.addr2,
    staleTime: 30_000,
  });
  const profileTarget = useMemo(
    () => unitsProfile ?? resolveCollectiveProfileTarget(profileResolveQ.data),
    [unitsProfile, profileResolveQ.data],
  );

  const listAiContext = useMemo(() => {
    if (!scope || !buildingsQ.data) return null;
    const regionLabel = [scope.addr1, formatScopeAddr2(scope.addr2, scope.addr1)]
      .filter(Boolean)
      .join(" ");
    return buildCollectiveListContext({
      regionLabel,
      assetType: scope.assetType,
      windowYears: buildingsQ.data.window_years ?? scope.windowYears,
      total: buildingsQ.data.total,
      first: buildingsQ.data.items[0] ?? null,
      items: buildingsQ.data.items,
      sort: scope.sort,
    });
  }, [scope, buildingsQ.data]);

  const buildingSearchQ = buildingSearch.trim().toLowerCase();
  const buildingMatchCount = useMemo(() => {
    if (!buildingSearchQ || !buildingsQ.data?.items.length) return 0;
    return buildingsQ.data.items.filter((row) => buildingMatchesQuery(row, buildingSearchQ)).length;
  }, [buildingsQ.data?.items, buildingSearchQ]);

  useEffect(() => {
    setBuildingSearch("");
  }, [scope]);

  useEffect(() => {
    if (!buildingSearchQ || buildingMatchCount === 0) return;
    const el = document.querySelector<HTMLElement>("[data-building-highlight='1']");
    el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [buildingSearchQ, buildingMatchCount, buildingsQ.data?.items]);

  const addr2ScopeLabel = formatScopeAddr2(addr2, addr1) || addr1;

  const liveFilters = {
    assetType,
    addr1,
    addr2,
    hasIntermediate,
    guList,
    leafList,
    yearFrom,
    yearTo,
    windowYears,
    sort: "count",
  };
  const { scopeStale, markRegionScopeCaptured } = useCollectiveScopeStale(
    scope,
    liveFilters,
    regionCodeScope,
  );

  const isApartment = assetKinds.includes("apartment");
  const regionalReady = Boolean(scope) && !scopeStale && isApartment;
  const regionalTitle = !isApartment
    ? "아파트일 때만 사용할 수 있습니다"
    : !scope
      ? "「통계분석」을 먼저 실행하세요"
      : scopeStale
        ? "조건이 변경되었습니다. 「통계분석」을 다시 실행하세요"
        : "선택한 지역의 아파트 단지로 식을 만들고 평균단가를 봅니다";

  useEffect(() => {
    if (!regionalReady) setRegionalOpen(false);
  }, [regionalReady]);

  useEffect(() => {
    const on = (e: Event) => {
      const a = (e as CustomEvent<AiScreenAction>).detail;
      if (!a) return;
      if (a.ui === "collective_regional") {
        setRegionalOpen(true);
        setAiHint(null);
        return;
      }
      if (a.ui === "collective_cohort" || a.ui === "collective_integrated") {
        setAiHint(
          "목록에서 단지를 연 다음 코호트에 비교할 단지를 추가하세요. AI가 코호트 구성을 바꾸지 않습니다.",
        );
      }
    };
    window.addEventListener(CH2_AI_ACTION_EVENT, on);
    return () => window.removeEventListener(CH2_AI_ACTION_EVENT, on);
  }, []);

  const runAnalysis = () => {
    if (!addr2 || !structureQ.isSuccess) return;
    markRegionScopeCaptured(regionCodeScope);
    setScope({
      assetType,
      addr1,
      addr2,
      guList: [...guList],
      leafList: [...leafList],
      hasIntermediate,
      yearFrom,
      yearTo,
      windowYears,
      sort: "count",
      ...regionCodeScope,
    });
    setSelected(null);
  };

  const resetRegion = () => {
    setGuList([]);
    setLeafList([]);
    setAnalysisUnits([]);
    setScope(null);
    setSelected(null);
  };

  return (
    <ActiveAiViewProvider fallback={emptyAiContext("collective", "BuildingList")}>
    <div className="h-screen flex flex-col overflow-hidden bg-slate-100 dark:bg-slate-900">
      <MacroStatsHeader
        currentApp="collective"
        title="주거형 집합부동산"
        fontPct={fontPct}
        fontStepMin={fontStepMin}
        fontStepMax={fontStepMax}
        onBumpFont={bumpUiFontScale}
        isDark={isDark}
        onToggleTheme={toggleUiColorScheme}
        rightSlot={<AiAssistantPanel />}
      />
      {listAiContext ? <PublishAiContext context={listAiContext} role="base" /> : null}

      <div className="relative z-0 isolate flex flex-1 min-h-0 flex flex-col overflow-hidden" style={{ zoom: contentZoom }}>
      <main className="flex flex-1 min-h-0 overflow-hidden">
        <CollapsibleLeftSidebar storageKey="collective" className="layout-sidebar p-4">
          <h2 className="text-sm font-semibold mb-3 text-slate-800 dark:text-slate-100">조건</h2>
          <div className="space-y-3">
            <div className="space-y-1">
              <span className="text-xs text-slate-500 dark:text-slate-400">유형</span>
              <p className="text-[10px] text-slate-400 leading-snug">
                기본은 아파트. 필요 시 유형을 추가해 함께 조회합니다.
              </p>
              <div className="flex flex-wrap gap-1.5">
                {RESIDENTIAL_ASSET_KINDS.map((kind) => {
                  const on = assetKinds.includes(kind);
                  return (
                    <button
                      key={kind}
                      type="button"
                      className={clsx(
                        "rounded-md border px-2.5 py-1.5 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:ring-offset-1 dark:focus-visible:ring-offset-slate-900",
                        on
                          ? "border-indigo-500 bg-indigo-600 text-white shadow-sm dark:border-indigo-300 dark:bg-indigo-500 dark:text-white"
                          : "border-slate-300 bg-white text-slate-700 hover:border-indigo-400 hover:bg-indigo-50 dark:border-slate-500 dark:bg-slate-800 dark:text-slate-100 dark:hover:border-indigo-400 dark:hover:bg-slate-700",
                      )}
                      onClick={() => {
                        setAssetKinds((prev) => toggleResidentialAssetKind(prev, kind));
                        resetRegion();
                      }}
                      aria-pressed={on}
                    >
                      {RESIDENTIAL_KIND_LABELS[kind]}
                    </button>
                  );
                })}
              </div>
            </div>

            <StatsWindowToggle
              value={windowYears}
              onChange={(y) => setWindowYears(normalizeStatsWindowYears(y))}
            />
            <p className="text-[10px] text-slate-400 leading-snug">
              직전 월말 기준 롤링 {windowYears}년 창으로 집계합니다.
            </p>

            <label className="text-xs block space-y-1">
              <span className="text-slate-500 dark:text-slate-400">시도</span>
              <select
                className="input"
                value={addr1}
                disabled={addr1Q.isLoading && !addr1Q.data}
                onChange={(e) => {
                  setAddr1(e.target.value);
                  setAddr2("");
                  resetRegion();
                }}
              >
                <option value="">선택</option>
                {(addr1Q.data ?? metaQ.data?.addr1_list ?? []).map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
              {addr1Q.isLoading && !addr1Q.data && (
                <span className="text-slate-400 text-[11px]">시도 목록 불러오는 중…</span>
              )}
            </label>

            <label className="text-xs block space-y-1">
              <span className="text-slate-500 dark:text-slate-400">시군구</span>
              <select
                className="input"
                value={addr2}
                disabled={!addr1}
                onChange={(e) => {
                  setAddr2(e.target.value);
                  resetRegion();
                }}
              >
                <option value="">선택</option>
                {(addr2Q.data ?? []).map((a) => (
                  <option key={a} value={a}>
                    {formatAddr2OptionLabel(a)}
                  </option>
                ))}
              </select>
            </label>

            {addr2 && hasIntermediate && (
              <RegionChipPanel
                title={`${intermediateLabel} 선택`}
                hint={`미선택 시 ${addr2ScopeLabel} 전체`}
                selected={guList}
                options={guOptions}
                countsReady={guCountsQ.isSuccess}
                multiSelect={LEFT_REGION_MULTI_SELECT}
                onToggle={(name) => {
                  if (LEFT_REGION_MULTI_SELECT) {
                    setGuList((prev) => toggleChipMulti(prev, name));
                    return;
                  }
                  setGuList((prev) => toggleChipSingle(prev, name));
                  setLeafList([]);
                  setAnalysisUnits([]);
                }}
                onSelectAll={() => setGuList(guOptions.filter((o) => !o.disabled).map((o) => o.name))}
                onClear={() => {
                  setGuList([]);
                  setLeafList([]);
                  setAnalysisUnits([]);
                }}
              />
            )}

            {addr2 && structureQ.isSuccess && (
              <RegionChipPanel
                title="읍·면·동"
                hint={
                  hasIntermediate
                    ? `${intermediateLabel} 선택 후 1개 선택 · 인접은 지도에서 추가`
                    : `1개 선택(미선택 시 ${addr2ScopeLabel} 전체) · 인접은 지도에서 추가`
                }
                selected={leafList}
                options={visibleLeafOptions}
                countsReady={leafCountsReady}
                formatLabel={(o) => formatLeafChipLabel(o, visibleLeafOptions)}
                multiSelect={LEFT_REGION_MULTI_SELECT}
                onToggle={(name) => {
                  setAnalysisUnits([]);
                  setLeafList((prev) =>
                    LEFT_REGION_MULTI_SELECT ? toggleChipMulti(prev, name) : toggleChipSingle(prev, name),
                  );
                }}
                onSelectAll={() => {
                  setAnalysisUnits([]);
                  setLeafList(visibleLeafOptions.filter((o) => !o.disabled).map((o) => o.name));
                }}
                onClear={() => {
                  setAnalysisUnits([]);
                  setLeafList([]);
                }}
              />
            )}

            <button
              type="button"
              className="btn btn-primary w-full"
              disabled={!addr2 || !structureQ.isSuccess}
              onClick={runAnalysis}
            >
              통계분석
            </button>
            <button
              type="button"
              className="btn w-full border border-slate-300 bg-white hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-800 dark:hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={!regionalReady}
              title={regionalTitle}
              onClick={() => setRegionalOpen(true)}
            >
              지역회귀
            </button>
          </div>
        </CollapsibleLeftSidebar>

        <div className="layout-main">
          <section className="px-4 pt-4 shrink-0">
            {analysisUnits.length > 0 && (
              <div className="mb-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/60 px-3 py-2">
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <p className="text-[11px] font-semibold text-slate-600 dark:text-slate-300">
                    선택 지역 ({analysisUnits.length}/{MAX_COLLECTIVE_ANALYSIS_UNITS})
                  </p>
                  <button
                    type="button"
                    className="text-[11px] text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                    onClick={clearUnits}
                  >
                    모두 지우기
                  </button>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {analysisUnits.map((u) => (
                    <span
                      key={u.code}
                      className="inline-flex items-center gap-1 rounded-full border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-2 py-0.5 text-[11px] text-slate-700 dark:text-slate-200"
                    >
                      {analysisUnitLabel(u)}
                      <button
                        type="button"
                        className="text-slate-400 hover:text-red-600"
                        aria-label="제거"
                        onClick={() => removeAnalysisUnit(u.code)}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            )}
            <CollectiveRegionMapHub
              scope={{
                assetType,
                addr1,
                addr2,
                guList,
                leafList,
                riPick: [],
              }}
              selectedBuildings={
                selected && scope
                  ? [
                      {
                        buildingKey: selected.building_key,
                        label: selected.display_name,
                        jibunAddress: selected.jibun_address || selected.address || null,
                        roadAddress: selected.road_address || null,
                        addr1: scope.addr1,
                        addr2: scope.addr2,
                      },
                    ]
                  : []
              }
              buildingCandidates={
                scope && buildingsQ.data
                  ? buildingsQ.data.items.slice(0, 100).map((row) => ({
                      buildingKey: row.building_key,
                      label: row.display_name,
                      jibunAddress: row.jibun_address || row.address || null,
                      roadAddress: row.road_address || null,
                      addr1: scope.addr1,
                      addr2: scope.addr2,
                    }))
                  : []
              }
              fillHeight={mapPanelMode === "expanded"}
              mapPanelMode={mapPanelMode}
              onExpand={() => setMapPanelMode("expanded")}
              onCollapse={() => setMapPanelMode("collapsed")}
              onNormal={() => setMapPanelMode("normal")}
              analysisUnits={analysisUnits}
              onAddUnit={addUnit}
            />
          </section>
          <div className="p-4 pt-2 pb-8">
          {!scope && (
            <p className="text-sm text-slate-500 dark:text-slate-400">시군구까지 선택한 뒤 「통계분석」을 누르면 건물 목록이 표시됩니다.</p>
          )}
          {scopeStale && (
            <p className="text-xs text-amber-700 dark:text-amber-300 mb-2 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded px-2 py-1">
              조건이 변경되었습니다. 「통계분석」을 다시 실행하세요.
            </p>
          )}
          {aiHint && (
            <p className="text-xs text-indigo-800 dark:text-indigo-200 mb-2 bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800 rounded px-2 py-1.5">
              {aiHint}
            </p>
          )}
          {scope && buildingsQ.isLoading && <p className="text-sm text-slate-500 dark:text-slate-400">불러오는 중…</p>}
          {scope && buildingsQ.isError && <p className="text-sm text-red-600">건물 목록을 불러오지 못했습니다.</p>}
          {scope && buildingsQ.data && (
            <>
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <p className="text-xs text-slate-500 dark:text-slate-400 flex-1 min-w-[12rem]">
                  {scope.addr1}
                  {!isFlatSidoAddr2(scope.addr2) && scope.addr2 ? ` ${scope.addr2}` : ""} · 건물 {buildingsQ.data.total}개
                  {buildingsQ.data.stats_as_of_label && !hasYearFilter(scope.yearFrom, scope.yearTo) && (
                    <span className="ml-2 text-indigo-600 dark:text-indigo-400">
                      · {buildingsQ.data.stats_as_of_label}
                      {buildingsQ.data.window_years ? ` (${buildingsQ.data.window_years}년 창)` : ""}
                    </span>
                  )}
                  {hasYearFilter(scope.yearFrom, scope.yearTo) && (
                    <span className="ml-2 text-indigo-600 dark:text-indigo-400">
                      · 연도 {scope.yearFrom || "…"}–{scope.yearTo || "…"}
                    </span>
                  )}
                  {buildingsQ.data.data_source === "live" && (
                    <span className="ml-1 text-amber-700 dark:text-amber-400">· 실시간 집계</span>
                  )}
                </p>
                {profileTarget && (
                  <a
                    href={profileHref(profileTarget)}
                    className="shrink-0 text-xs font-medium text-slate-700 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white underline"
                  >
                    지역 프로필 →
                  </a>
                )}
                <StatsTableExpandButton
                  expanded={tableWide}
                  onToggle={() => setTableWide((v) => !v)}
                  title="신뢰구간·도로명 주소·개별공시지가를 보여 줍니다"
                />
                <label className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-300 shrink-0">
                  <span className="whitespace-nowrap">검색</span>
                  <input
                    type="search"
                    className="input py-1 text-xs w-44 sm:w-56"
                    value={buildingSearch}
                    onChange={(e) => setBuildingSearch(e.target.value)}
                    placeholder="건물명·주소·시공사…"
                    aria-label="검색"
                  />
                </label>
              </div>
              <BuildingStatsTable
                items={buildingsQ.data.items}
                wide={tableWide}
                highlightQuery={buildingSearchQ}
                onSelect={setSelected}
              />
            </>
          )}
          </div>
        </div>
      </main>
      </div>

      {regionalOpen && scope && (
        <RegionalRegressionModal
          addr1={scope.addr1}
          addr2={scope.addr2}
          hasIntermediate={scope.hasIntermediate}
          guList={scope.guList}
          leafList={scope.leafList}
          regionCodes={scope.region_codes}
          regionCodeLevel={scope.region_code_level}
          regionAddrs={scope.region_addrs}
          windowYears={scope.windowYears}
          assetType={scope.assetType}
          onClose={() => setRegionalOpen(false)}
        />
      )}
      {selected && scope && (
        <BuildingDetailModal
          row={selected}
          assetType={scope.assetType}
          windowYears={scope.windowYears}
          yearFrom={scope.yearFrom === "" ? undefined : scope.yearFrom}
          yearTo={scope.yearTo === "" ? undefined : scope.yearTo}
          periodStart={buildingsQ.data?.period_start}
          periodEnd={buildingsQ.data?.period_end}
          statsAsOfLabel={buildingsQ.data?.stats_as_of_label}
          peerBuildings={buildingsQ.data?.items ?? []}
          onClose={() => setSelected(null)}
          onOpenSibling={setSelected}
        />
      )}
    </div>
    </ActiveAiViewProvider>
  );
}
