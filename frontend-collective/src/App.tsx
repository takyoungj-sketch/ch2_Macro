import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  fetchAddr1List,
  fetchAddr2,
  fetchAddr3WithCounts,
  fetchAllBuildings,
  fetchFilterMeta,
  fetchLeafRegions,
  fetchRegionStructure,
  COLLECTIVE_EXPERIMENT_MODE,
  type BuildingStatsRow,
} from "./api/client";
import { fetchCollectiveMapResolveCodes } from "./api/mapClient";
import BuildingDetailModal from "./components/BuildingDetailModal";
import NewApartmentExperimentModal from "./components/NewApartmentExperimentModal";
import CollectiveRegionMapHub, { type MapPanelMode } from "./components/CollectiveRegionMapHub";
import MacroStatsHeader from "@ch2/macro-shell/MacroStatsHeader";
import { useUiColorScheme } from "@ch2/macro-shell/useUiColorScheme";
import { useUiFontScale } from "@ch2/macro-shell/useUiFontScale";
import RegionChipPanel, {
  LEFT_REGION_MULTI_SELECT,
  toggleChipMulti,
  toggleChipSingle,
} from "./components/RegionChipPanel";
import StatsWindowToggle, {
  normalizeStatsWindowYears,
  type StatsWindowYears,
} from "./components/StatsWindowToggle";
import type { AssetSelectorType, RegionOption } from "./types";
import { assetTypeLabel } from "./types";
import {
  hasYearFilter,
} from "./utils/contractYearRange";
import {
  formatAddr2OptionLabel,
  formatScopeAddr2,
  isFlatSidoAddr2,
} from "./utils/flatSidoRegion";
import {
  encodeResidentialAssetKinds,
  RESIDENTIAL_ASSET_KINDS,
  RESIDENTIAL_KIND_LABELS,
  toggleResidentialAssetKind,
  type ResidentialAssetKind,
} from "./utils/residentialAssetTypes";
import { useCollectiveDeepLink } from "./hooks/useCollectiveDeepLink";
import { profileHref, resolveCollectiveProfileTarget } from "./utils/profileLink";

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
};

function fmtPrice(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function fmtCiCompact(lo: number | null | undefined, hi: number | null | undefined) {
  if (lo == null || hi == null) return "—";
  return `${fmtPrice(lo)}~${fmtPrice(hi)}`;
}

function BuildingTableRow({
  row,
  highlighted,
  onSelect,
}: {
  row: BuildingStatsRow;
  highlighted?: boolean;
  onSelect: (row: BuildingStatsRow) => void;
}) {
  return (
    <tr
      className={clsx(
        "hover:bg-indigo-50 dark:hover:bg-indigo-950/40 cursor-pointer",
        highlighted && "!bg-yellow-200 dark:!bg-yellow-700/50",
      )}
      onClick={() => onSelect(row)}
      title={row.display_name}
      data-building-highlight={highlighted ? "1" : undefined}
    >
      <td className="text-[10px] whitespace-nowrap text-center">{assetTypeLabel(row.asset_type)}</td>
      <td className="name">
        {row.display_name}
        {!row.is_reliable && <span className="ml-0.5 text-[9px] text-amber-600">n&lt;15</span>}
      </td>
      <td className="num">{row.count}</td>
      <td className="num">{fmtPrice(row.mean)}</td>
      <td className="num">{fmtPrice(row.median)}</td>
      <td className="num text-[10px]">{fmtCiCompact(row.ci_lower, row.ci_upper)}</td>
      <td className="num">{row.building_year ?? "—"}</td>
      <td className="addr truncate" title={row.jibun_address || row.address || undefined}>
        {row.jibun_address ?? row.address ?? "—"}
      </td>
      <td className="addr truncate" title={row.road_address || undefined}>
        {row.road_address ?? "—"}
      </td>
    </tr>
  );
}

function buildingMatchesQuery(row: BuildingStatsRow, q: string): boolean {
  if (!q) return false;
  const hay = [
    row.display_name,
    row.jibun_address,
    row.road_address,
    row.address,
    row.asset_type,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return hay.includes(q);
}

export default function App() {
  const [assetKinds, setAssetKinds] = useState<ResidentialAssetKind[]>(["apartment"]);
  const assetType = useMemo(() => encodeResidentialAssetKinds(assetKinds), [assetKinds]);
  const [addr1, setAddr1] = useState("");
  const [addr2, setAddr2] = useState("");
  const [guList, setGuList] = useState<string[]>([]);
  const [leafList, setLeafList] = useState<string[]>([]);
  const [yearFrom, setYearFrom] = useState<number | "">("");
  const [yearTo, setYearTo] = useState<number | "">("");
  const [windowYears, setWindowYears] = useState<StatsWindowYears>(5);
  const [sort, setSort] = useState("count");
  const [scope, setScope] = useState<AnalysisScope | null>(null);
  const [selected, setSelected] = useState<BuildingStatsRow | null>(null);
  const [newAptOpen, setNewAptOpen] = useState(false);
  const [buildingSearch, setBuildingSearch] = useState("");
  const [mapPanelMode, setMapPanelMode] = useState<MapPanelMode>("normal");
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
  });

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
  });
  const hasIntermediate = structureQ.data?.has_intermediate ?? false;
  const intermediateLabel = structureQ.data?.intermediate_label ?? "구";
  const isDaejeonApartment =
    COLLECTIVE_EXPERIMENT_MODE && assetKinds.includes("apartment") && addr1.includes("대전");

  const regionPeriod = hasYearFilter(yearFrom, yearTo)
    ? {
        contract_year_from: yearFrom === "" ? undefined : yearFrom,
        contract_year_to: yearTo === "" ? undefined : yearTo,
      }
    : undefined;

  const guQ = useQuery({
    queryKey: ["coll-gu", addr1, addr2, assetType, regionPeriod],
    queryFn: () => fetchAddr3WithCounts(addr1, addr2, assetType, regionPeriod),
    enabled: !!addr1 && !!addr2 && hasIntermediate,
  });
  const flatLeafQ = useQuery({
    queryKey: ["coll-flat-leaf", addr1, addr2, assetType, regionPeriod],
    queryFn: () => fetchAddr3WithCounts(addr1, addr2, assetType, regionPeriod),
    enabled: !!addr1 && !!addr2 && !hasIntermediate && structureQ.isSuccess,
  });
  const leafQ = useQuery({
    queryKey: ["coll-leaf", addr1, addr2, assetType, guList, regionPeriod],
    queryFn: () => fetchLeafRegions(addr1, addr2, guList, assetType, regionPeriod),
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
        contract_year_from: scope.yearFrom === "" ? undefined : scope.yearFrom,
        contract_year_to: scope.yearTo === "" ? undefined : scope.yearTo,
        window_years: scope.windowYears,
        presale_stats_mode: "rolling",
        sort: scope.sort,
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
    () => resolveCollectiveProfileTarget(profileResolveQ.data),
    [profileResolveQ.data],
  );

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
      scope.windowYears !== windowYears ||
      scope.sort !== sort);

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
      windowYears,
      sort,
    });
    setSelected(null);
  };

  const resetRegion = () => {
    setGuList([]);
    setLeafList([]);
    setScope(null);
    setSelected(null);
  };

  return (
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
      />

      <div className="flex flex-1 min-h-0 flex flex-col overflow-hidden" style={{ zoom: contentZoom }}>
      <main className="flex flex-1 min-h-0">
        <aside className="layout-sidebar p-4">
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
                }}
                onSelectAll={() => setGuList((guQ.data ?? []).filter((o) => !o.disabled).map((o) => o.name))}
                onClear={() => {
                  setGuList([]);
                  setLeafList([]);
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
                formatLabel={(o) => (o.parent ? `${o.parent} · ${o.name}` : o.name)}
                multiSelect={LEFT_REGION_MULTI_SELECT}
                onToggle={(name) =>
                  setLeafList((prev) =>
                    LEFT_REGION_MULTI_SELECT ? toggleChipMulti(prev, name) : toggleChipSingle(prev, name),
                  )
                }
                onSelectAll={() => setLeafList(visibleLeafOptions.filter((o) => !o.disabled).map((o) => o.name))}
                onClear={() => setLeafList([])}
              />
            )}

            <label className="text-xs block space-y-1">
              <span className="text-slate-500 dark:text-slate-400">정렬</span>
              <select className="input" value={sort} onChange={(e) => setSort(e.target.value)}>
                <option value="count">거래수</option>
                <option value="mean">평균 단가</option>
                <option value="display_name">건물명</option>
                <option value="address">지번 주소</option>
              </select>
            </label>

            <StatsWindowToggle
              value={windowYears}
              onChange={(y) => setWindowYears(normalizeStatsWindowYears(y))}
            />

            <button type="button" className="btn btn-primary w-full" disabled={!addr2} onClick={runAnalysis}>
              통계분석
            </button>
            {COLLECTIVE_EXPERIMENT_MODE && assetKinds.includes("apartment") && (
              <button
                type="button"
                className="btn w-full border border-indigo-300 text-indigo-800 bg-indigo-50 hover:bg-indigo-100 dark:border-indigo-500/60 dark:text-indigo-200 dark:bg-indigo-950/40 dark:hover:bg-indigo-900/50"
                disabled={!isDaejeonApartment}
                title={isDaejeonApartment ? "대전 아파트 신규 가격 실험" : "1차는 대전 아파트만"}
                onClick={() => setNewAptOpen(true)}
              >
                신규아파트 실험
              </button>
            )}
          </div>
        </aside>

        <div className="layout-main">
          <section className="px-4 pt-4 shrink-0">
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
              onAddLeaf={(name) => {
                setLeafList((prev) => (prev.includes(name) ? prev : [...prev, name]));
              }}
            />
          </section>
          <div className="p-4 pt-2">
          {!scope && (
            <p className="text-sm text-slate-500 dark:text-slate-400">시군구까지 선택한 뒤 「통계분석」을 누르면 건물 목록이 표시됩니다.</p>
          )}
          {scopeStale && (
            <p className="text-xs text-amber-700 dark:text-amber-300 mb-2 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded px-2 py-1">
              조건이 변경되었습니다. 「통계분석」을 다시 실행하세요.
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
                {isDaejeonApartment && (
                  <button
                    type="button"
                    className="shrink-0 text-xs font-medium text-indigo-700 hover:text-indigo-900 dark:text-indigo-300 dark:hover:text-white underline"
                    onClick={() => setNewAptOpen(true)}
                  >
                    신규아파트 실험
                  </button>
                )}
                {profileTarget && (
                  <a
                    href={profileHref(profileTarget)}
                    className="shrink-0 text-xs font-medium text-slate-700 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white underline"
                  >
                    지역 프로필 →
                  </a>
                )}
                <label className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-300 shrink-0">
                  <span className="whitespace-nowrap">검색</span>
                  <input
                    type="search"
                    className="input py-1 text-xs w-44 sm:w-56"
                    value={buildingSearch}
                    onChange={(e) => setBuildingSearch(e.target.value)}
                    placeholder="건물명·주소…"
                    aria-label="검색"
                  />
                </label>
              </div>
              <div className="card overflow-x-auto p-0 w-full">
                <table className="data buildings-table">
                  <colgroup>
                    <col className="col-type" />
                    <col className="col-name" />
                    <col className="col-num" />
                    <col className="col-num" />
                    <col className="col-num" />
                    <col className="col-num" />
                    <col className="col-year" />
                    <col className="col-jibun" />
                    <col className="col-road" />
                  </colgroup>
                  <thead>
                    <tr>
                      <th>유형</th>
                      <th>건물명</th>
                      <th className="text-right">거래</th>
                      <th className="text-right">평균</th>
                      <th className="text-right">중앙</th>
                      <th className="text-right">95% CI</th>
                      <th className="text-right">신축연도</th>
                      <th className="col-addr-head">지번 주소</th>
                      <th className="col-addr-head">도로명 주소</th>
                    </tr>
                  </thead>
                  <tbody>
                    {buildingsQ.data.items.map((row) => (
                      <BuildingTableRow
                        key={`${row.building_key}|${row.asset_type}`}
                        row={row}
                        highlighted={buildingMatchesQuery(row, buildingSearchQ)}
                        onSelect={setSelected}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          </div>
        </div>
      </main>

      {newAptOpen && <NewApartmentExperimentModal onClose={() => setNewAptOpen(false)} />}
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
        />
      )}
      </div>
    </div>
  );
}
