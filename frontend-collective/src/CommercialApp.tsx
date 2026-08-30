import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import clsx from "clsx";
import {
  fetchCommercialAddr1List,
  fetchCommercialAddr2,
  fetchCommercialAddr3,
  fetchCommercialClusters,
  fetchCommercialFilterMeta,
  fetchCommercialLeafRegions,
  fetchCommercialRegionStructure,
} from "./api/commercialClient";
import { fetchCollectiveMapResolveCodes } from "./api/mapClient";
import DualHorizontalScroll from "./components/DualHorizontalScroll";
import StatsTableExpandButton from "./components/StatsTableExpandButton";
import CommercialClusterDetailModal from "./components/CommercialClusterDetailModal";
import CollectiveRegionMapHub, { type MapPanelMode } from "./components/CollectiveRegionMapHub";
import MacroStatsHeader from "@ch2/macro-shell/MacroStatsHeader";
import { useUiColorScheme } from "@ch2/macro-shell/useUiColorScheme";
import { useUiFontScale } from "@ch2/macro-shell/useUiFontScale";
import StatsWindowToggle, { normalizeStatsWindowYears, type StatsWindowYears } from "./components/StatsWindowToggle";
import RegionChipPanel, {
  LEFT_REGION_MULTI_SELECT,
  formatLeafChipLabel,
  toggleChipMulti,
  toggleChipSingle,
} from "./components/RegionChipPanel";
import { commercialAssetTypeLabel, type CommercialAssetSelectorType, type CommercialClusterRow, type RegionOption } from "./types";
import {
  COMMERCIAL_ASSET_KINDS,
  COMMERCIAL_KIND_LABELS,
  encodeCommercialAssetKinds,
  toggleCommercialAssetKind,
  type CommercialAssetKind,
} from "./utils/commercialAssetTypes";
import { useCollectiveDeepLink } from "./hooks/useCollectiveDeepLink";
import { profileHref, resolveCollectiveProfileTarget } from "./utils/profileLink";
import { useCollectiveAnalysisUnits } from "./hooks/useCollectiveAnalysisUnits";
import {
  analysisUnitLabel,
  MAX_COLLECTIVE_ANALYSIS_UNITS,
} from "./utils/collectiveAnalysisUnits";
import {
  formatAddr2OptionLabel,
  formatScopeAddr2,
  isFlatSidoAddr2,
} from "./utils/flatSidoRegion";

function fmtPrice(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function fmtCi(lo: number | null | undefined, hi: number | null | undefined) {
  if (lo == null || hi == null) return "—";
  return `${fmtPrice(lo)}~${fmtPrice(hi)}`;
}

type AnalysisScope = {
  assetType: CommercialAssetSelectorType;
  addr1: string;
  addr2: string;
  guList: string[];
  leafList: string[];
  hasIntermediate: boolean;
  yearFrom: number | "";
  yearTo: number | "";
  sort: string;
  windowYears: StatsWindowYears;
  region_codes?: string[];
  region_code_level?: "eupmyeondong" | "beopjungri";
  region_addrs?: string[];
};

function hasYearFilter(from: number | "", to: number | "") {
  return from !== "" || to !== "";
}

function buildRegionPeriodParams(
  yearFrom: number | "",
  yearTo: number | "",
  windowYears: StatsWindowYears,
) {
  if (hasYearFilter(yearFrom, yearTo)) {
    return {
      contract_year_from: yearFrom === "" ? undefined : yearFrom,
      contract_year_to: yearTo === "" ? undefined : yearTo,
    };
  }
  return { window_years: windowYears };
}

function clusterMatchesQuery(row: CommercialClusterRow, q: string): boolean {
  if (!q) return false;
  const hay = [
    row.road_name,
    row.display_label,
    row.addr3,
    row.addr4,
    row.asset_type,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return hay.includes(q);
}

export default function CommercialApp() {
  const [assetKinds, setAssetKinds] = useState<CommercialAssetKind[]>(["collective_shop"]);
  const assetType = useMemo(() => encodeCommercialAssetKinds(assetKinds), [assetKinds]);
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
    commercial: true,
  });
  const [yearFrom, setYearFrom] = useState<number | "">("");
  const [yearTo, setYearTo] = useState<number | "">("");
  const [sort, setSort] = useState("count");
  const [windowYears, setWindowYears] = useState<StatsWindowYears>(5);
  const [scope, setScope] = useState<AnalysisScope | null>(null);
  const [selected, setSelected] = useState<CommercialClusterRow | null>(null);
  const [clusterSearch, setClusterSearch] = useState("");
  const [mapPanelMode, setMapPanelMode] = useState<MapPanelMode>("normal");
  const [tableWide, setTableWide] = useState(false);
  const { contentZoom, fontPct, fontStepMin, fontStepMax, bumpUiFontScale } = useUiFontScale();
  const { isDark, toggleUiColorScheme } = useUiColorScheme();

  const addr1Q = useQuery({
    queryKey: ["comm-addr1"],
    queryFn: fetchCommercialAddr1List,
    staleTime: 24 * 60 * 60_000,
    placeholderData: (prev) => prev,
  });
  const metaQ = useQuery({
    queryKey: ["comm-meta"],
    queryFn: fetchCommercialFilterMeta,
    staleTime: 60_000,
    placeholderData: (prev) => prev,
  });
  const addr2Q = useQuery({
    queryKey: ["comm-addr2", addr1, assetType],
    queryFn: () => fetchCommercialAddr2(addr1, assetType),
    enabled: !!addr1,
  });

  useEffect(() => {
    if (!addr1 || addr2) return;
    const opts = addr2Q.data ?? [];
    if (opts.length === 1 && isFlatSidoAddr2(opts[0])) {
      setAddr2(opts[0]!);
    }
  }, [addr1, addr2, addr2Q.data]);
  const structureQ = useQuery({
    queryKey: ["comm-structure", addr1, addr2, assetType],
    queryFn: () => fetchCommercialRegionStructure(addr1, addr2, assetType),
    enabled: !!addr1 && !!addr2,
  });
  const hasIntermediate = structureQ.data?.has_intermediate ?? false;
  const intermediateLabel = structureQ.data?.intermediate_label ?? "구";

  const regionPeriod = buildRegionPeriodParams(yearFrom, yearTo, windowYears);

  const guQ = useQuery({
    queryKey: ["comm-gu", addr1, addr2, assetType, regionPeriod],
    queryFn: () => fetchCommercialAddr3(addr1, addr2, assetType, regionPeriod),
    enabled: !!addr1 && !!addr2 && hasIntermediate,
  });
  const flatLeafQ = useQuery({
    queryKey: ["comm-flat-leaf", addr1, addr2, assetType, regionPeriod],
    queryFn: () => fetchCommercialAddr3(addr1, addr2, assetType, regionPeriod),
    enabled: !!addr1 && !!addr2 && !hasIntermediate && structureQ.isSuccess,
  });
  const leafQ = useQuery({
    queryKey: ["comm-leaf", addr1, addr2, assetType, guList, regionPeriod],
    queryFn: () => fetchCommercialLeafRegions(addr1, addr2, guList, assetType, regionPeriod),
    enabled: !!addr1 && !!addr2 && hasIntermediate,
  });

  const visibleLeafOptions = useMemo(() => {
    if (!hasIntermediate) {
      return (flatLeafQ.data ?? []).map((o: RegionOption) => ({ ...o, id: o.name }));
    }
    const opts = leafQ.data ?? [];
    const filtered = !guList.length ? opts : opts.filter((o) => o.parent && guList.includes(o.parent));
    return filtered.map((o) => ({ ...o, id: `${o.parent ?? ""}|${o.name}` }));
  }, [hasIntermediate, flatLeafQ.data, leafQ.data, guList]);

  useEffect(() => {
    if (!hasIntermediate) return;
    const allowed = new Set(visibleLeafOptions.map((o) => o.name));
    setLeafList((prev) => prev.filter((n) => allowed.has(n)));
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

  const clustersQ = useQuery({
    queryKey: ["comm-clusters", scope],
    queryFn: () => {
      if (!scope) throw new Error("no scope");
      const regionParams = scope.hasIntermediate
        ? {
            addr3_list: scope.guList.length ? scope.guList : undefined,
            addr4_list: scope.leafList.length ? scope.leafList : undefined,
          }
        : { addr3_list: scope.leafList.length ? scope.leafList : undefined };
      return fetchCommercialClusters({
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
        sort: scope.sort,
        page_size: 500,
      });
    },
    enabled: scope !== null && !!scope.addr2,
  });

  const profileResolveQ = useQuery({
    queryKey: ["comm-profile-resolve", scope],
    queryFn: () =>
      fetchCollectiveMapResolveCodes({
        assetType: scope!.assetType,
        addr1: scope!.addr1,
        addr2: scope!.addr2,
        gu: scope!.hasIntermediate ? scope!.guList : [],
        leaf: scope!.leafList,
        commercial: true,
      }),
    enabled: scope !== null && !!scope.addr2,
    staleTime: 30_000,
  });
  const profileTarget = useMemo(
    () => unitsProfile ?? resolveCollectiveProfileTarget(profileResolveQ.data),
    [unitsProfile, profileResolveQ.data],
  );

  const clusterSearchQ = clusterSearch.trim().toLowerCase();
  const clusterMatchCount = useMemo(() => {
    if (!clusterSearchQ || !clustersQ.data?.items.length) return 0;
    return clustersQ.data.items.filter((row) => clusterMatchesQuery(row, clusterSearchQ)).length;
  }, [clustersQ.data?.items, clusterSearchQ]);

  useEffect(() => {
    setClusterSearch("");
  }, [scope]);

  useEffect(() => {
    if (!clusterSearchQ || clusterMatchCount === 0) return;
    const el = document.querySelector<HTMLElement>("[data-cluster-highlight='1']");
    el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [clusterSearchQ, clusterMatchCount, clustersQ.data?.items]);

  const scopeStale =
    scope !== null &&
    (scope.assetType !== assetType ||
      scope.addr1 !== addr1 ||
      scope.addr2 !== addr2 ||
      scope.hasIntermediate !== hasIntermediate ||
      JSON.stringify(scope.guList) !== JSON.stringify(guList) ||
      JSON.stringify(scope.leafList) !== JSON.stringify(leafList) ||
      scope.yearFrom !== yearFrom ||
      scope.yearTo !== yearTo ||
      scope.sort !== sort ||
      scope.windowYears !== windowYears ||
      JSON.stringify(scope.region_codes ?? []) !== JSON.stringify(regionCodeScope.region_codes ?? []) ||
      JSON.stringify(scope.region_addrs ?? []) !== JSON.stringify(regionCodeScope.region_addrs ?? []));

  const addr2ScopeLabel = formatScopeAddr2(addr2, addr1) || addr1;

  const runAnalysis = () => {
    if (!addr2) return;
    setScope({
      assetType,
      addr1,
      addr2,
      guList: [...guList],
      leafList: [...leafList],
      hasIntermediate,
      yearFrom,
      yearTo,
      sort,
      windowYears,
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
    <div className="h-screen flex flex-col overflow-hidden bg-slate-100 dark:bg-slate-900">
      <MacroStatsHeader
        currentApp="collective"
        title="상업·업무 집합부동산"
        fontPct={fontPct}
        fontStepMin={fontStepMin}
        fontStepMax={fontStepMax}
        onBumpFont={bumpUiFontScale}
        isDark={isDark}
        onToggleTheme={toggleUiColorScheme}
      />

      <div className="flex flex-1 min-h-0 flex flex-col overflow-hidden" style={{ zoom: contentZoom }}>
      <main className="flex flex-1 min-h-0">
        <aside className="layout-sidebar p-4">
          <h2 className="text-sm font-semibold mb-3 text-slate-800 dark:text-slate-100">조건</h2>
          <div className="space-y-3">
            <div className="space-y-1">
              <span className="text-xs text-slate-500 dark:text-slate-400">유형</span>
              <p className="text-[10px] text-slate-400 leading-snug">
                기본은 집합상가. 필요 시 공장을 추가해 함께 조회합니다.
              </p>
              <div className="flex flex-wrap gap-1.5">
                {COMMERCIAL_ASSET_KINDS.map((kind) => {
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
                        setAssetKinds((prev) => toggleCommercialAssetKind(prev, kind));
                        resetRegion();
                      }}
                      aria-pressed={on}
                    >
                      {COMMERCIAL_KIND_LABELS[kind]}
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
                options={guQ.data ?? []}
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
                onSelectAll={() => setGuList((guQ.data ?? []).filter((o) => !o.disabled).map((o) => o.name))}
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
                    : `1개 선택(미선택 시 시군구 전체) · 인접은 지도에서 추가`
                }
                selected={leafList}
                options={visibleLeafOptions}
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

            <label className="text-xs block space-y-1">
              <span className="text-slate-500 dark:text-slate-400">정렬</span>
              <select className="input" value={sort} onChange={(e) => setSort(e.target.value)}>
                <option value="count">거래수</option>
                <option value="mean">평균 단가</option>
                <option value="display_label">도로명</option>
              </select>
            </label>

            <button type="button" className="btn btn-primary w-full" disabled={!addr2} onClick={runAnalysis}>
              통계분석
            </button>
          </div>
        </aside>

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
              commercial
              scope={{
                assetType,
                addr1,
                addr2,
                guList,
                leafList,
                riPick: [],
              }}
              analysisUnits={analysisUnits}
              onAddUnit={addUnit}
              selectedRoads={
                selected && scope
                  ? [
                      {
                        clusterKey: selected.cluster_key,
                        roadName: selected.road_name || selected.display_label,
                        label: selected.road_name || selected.display_label,
                        addr1: scope.addr1,
                        addr2: scope.addr2,
                        addr3: selected.addr3,
                        addr4: selected.addr4,
                      },
                    ]
                  : []
              }
              roadCandidates={
                scope && clustersQ.data
                  ? clustersQ.data.items.slice(0, 100).map((cluster) => ({
                      clusterKey: cluster.cluster_key,
                      roadName: cluster.road_name || cluster.display_label,
                      label: cluster.road_name || cluster.display_label,
                      addr1: scope.addr1,
                      addr2: scope.addr2,
                      addr3: cluster.addr3,
                      addr4: cluster.addr4,
                    }))
                  : []
              }
              fillHeight={mapPanelMode === "expanded"}
              mapPanelMode={mapPanelMode}
              onExpand={() => setMapPanelMode("expanded")}
              onCollapse={() => setMapPanelMode("collapsed")}
              onNormal={() => setMapPanelMode("normal")}
            />
          </section>
          <div className="p-4 pt-2 flex-1 min-h-0 overflow-y-auto">
            {!scope && (
              <p className="text-sm text-slate-500 dark:text-slate-400">시군구까지 선택한 뒤 「통계분석」을 누르면 도로(cluster) 목록이 표시됩니다.</p>
            )}
            {scopeStale && (
              <p className="text-xs text-amber-700 dark:text-amber-300 mb-2 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded px-2 py-1">
                조건이 변경되었습니다. 「통계분석」을 다시 실행하세요.
              </p>
            )}
            {scope && clustersQ.isLoading && <p className="text-sm text-slate-500 dark:text-slate-400">불러오는 중…</p>}
            {scope && clustersQ.isError && <p className="text-sm text-red-600">도로 목록을 불러오지 못했습니다.</p>}
            {scope && clustersQ.data && (
              <>
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <p className="text-xs text-slate-500 dark:text-slate-400 flex-1 min-w-[12rem]">
                    {scope.addr1}
                    {addr2ScopeLabel && addr2ScopeLabel !== scope.addr1 ? ` ${addr2ScopeLabel}` : ""} · 도로{" "}
                    {clustersQ.data.total}개
                    {clustersQ.data.stats_as_of_label && !hasYearFilter(scope.yearFrom, scope.yearTo) && (
                      <span className="ml-2 text-indigo-600 dark:text-indigo-400">
                        · {clustersQ.data.stats_as_of_label}
                        {clustersQ.data.window_years ? ` (${clustersQ.data.window_years}년 창)` : ""}
                      </span>
                    )}
                    {hasYearFilter(scope.yearFrom, scope.yearTo) && (
                      <span className="ml-2 text-indigo-600 dark:text-indigo-400">
                        · 연도 {scope.yearFrom || "…"}–{scope.yearTo || "…"}
                      </span>
                    )}
                    {clustersQ.data.data_source === "live" && (
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
                    title="신뢰구간을 보여 줍니다"
                  />
                  <label className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-300 shrink-0">
                    <span className="whitespace-nowrap">검색</span>
                    <input
                      type="search"
                      className="input py-1 text-xs w-44 sm:w-56"
                      value={clusterSearch}
                      onChange={(e) => setClusterSearch(e.target.value)}
                      placeholder="도로명·구·동…"
                      aria-label="검색"
                    />
                  </label>
                </div>
                <div className="card p-0 w-full">
                  <DualHorizontalScroll key={tableWide ? "wide" : "compact"}>
                  <table className={clsx("data commercial-clusters-table", tableWide && "is-wide")}>
                    <colgroup>
                      <col className="col-type" />
                      <col className="col-road" />
                      <col className="col-num" />
                      <col className="col-num" />
                      <col className="col-num" />
                      {tableWide && <col className="col-num" />}
                      <col className="col-district" />
                    </colgroup>
                    <thead>
                      <tr>
                        <th>유형</th>
                        <th>
                          <span className="inline-flex items-center gap-1">
                            도로명
                            <StatsGlossaryHelp termId="commercial_cluster" size="xs" />
                          </span>
                        </th>
                        <th>거래수</th>
                        <th>중앙(만원/㎡)</th>
                        <th>평균(만원/㎡)</th>
                        {tableWide && <th title="95% 신뢰구간">신뢰구간(만원/㎡)</th>}
                        <th>구·동</th>
                      </tr>
                    </thead>
                    <tbody>
                      {clustersQ.data.items.map((row) => {
                        const highlighted = clusterMatchesQuery(row, clusterSearchQ);
                        return (
                          <tr
                            key={`${row.cluster_key}|${row.asset_type}`}
                            className={clsx(
                              "hover:bg-indigo-50 dark:hover:bg-indigo-950/40 cursor-pointer",
                              highlighted
                                ? "!bg-yellow-200 dark:!bg-yellow-700/50"
                                : selected?.cluster_key === row.cluster_key &&
                                    selected?.asset_type === row.asset_type &&
                                    "bg-indigo-50 dark:bg-indigo-950/50",
                            )}
                            onClick={() => setSelected(row)}
                            data-cluster-highlight={highlighted ? "1" : undefined}
                          >
                            <td className="text-[10px] whitespace-nowrap text-center">
                              {commercialAssetTypeLabel(row.asset_type)}
                            </td>
                            <td className="name">
                              {row.road_name || row.display_label}
                              {!row.is_reliable && <span className="ml-0.5 text-[9px] text-amber-600">n&lt;15</span>}
                            </td>
                            <td className="num">{row.count}</td>
                            <td className="num">{fmtPrice(row.median)}</td>
                            <td className="num">{fmtPrice(row.mean)}</td>
                            {tableWide && (
                              <td className="num text-[10px]">{fmtCi(row.ci_lower, row.ci_upper)}</td>
                            )}
                            <td className="col-district text-[10px] text-slate-600 dark:text-slate-300">
                              {[row.addr3, row.addr4].filter(Boolean).join(" · ") || "—"}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  </DualHorizontalScroll>
                </div>
              </>
            )}
          </div>
        </div>
      </main>
      </div>

      {selected && scope && (
        <CommercialClusterDetailModal
          row={selected}
          scope={scope}
          windowYears={scope.windowYears}
          periodStart={clustersQ.data?.period_start}
          periodEnd={clustersQ.data?.period_end}
          statsAsOfLabel={clustersQ.data?.stats_as_of_label}
          peerClusters={clustersQ.data?.items ?? []}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
