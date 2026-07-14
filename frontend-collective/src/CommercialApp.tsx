import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  fetchCommercialAddr2,
  fetchCommercialAddr3,
  fetchCommercialClusters,
  fetchCommercialFilterMeta,
  fetchCommercialLeafRegions,
  fetchCommercialRegionStructure,
} from "./api/commercialClient";
import CommercialClusterDetailModal from "./components/CommercialClusterDetailModal";
import CollectiveRegionMapHub, { type MapPanelMode } from "./components/CollectiveRegionMapHub";
import StatsPageHeader from "./components/StatsPageHeader";
import StatsWindowToggle, { normalizeStatsWindowYears, type StatsWindowYears } from "./components/StatsWindowToggle";
import RegionChipPanel, {
  LEFT_REGION_MULTI_SELECT,
  toggleChipMulti,
  toggleChipSingle,
} from "./components/RegionChipPanel";
import { useUiColorScheme } from "./hooks/useUiColorScheme";
import { useUiFontScale } from "./hooks/useUiFontScale";
import { commercialAssetTypeLabel, type CommercialAssetSelectorType, type CommercialClusterRow, type RegionOption } from "./types";
import {
  COMMERCIAL_ASSET_KINDS,
  COMMERCIAL_KIND_LABELS,
  encodeCommercialAssetKinds,
  toggleCommercialAssetKind,
  type CommercialAssetKind,
} from "./utils/commercialAssetTypes";

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
  const [yearFrom, setYearFrom] = useState<number | "">("");
  const [yearTo, setYearTo] = useState<number | "">("");
  const [sort, setSort] = useState("count");
  const [windowYears, setWindowYears] = useState<StatsWindowYears>(5);
  const [scope, setScope] = useState<AnalysisScope | null>(null);
  const [selected, setSelected] = useState<CommercialClusterRow | null>(null);
  const [clusterSearch, setClusterSearch] = useState("");
  const [mapPanelMode, setMapPanelMode] = useState<MapPanelMode>("normal");
  const { contentZoom, fontPct, fontStepMin, fontStepMax, bumpUiFontScale } = useUiFontScale();
  const { isDark, toggleUiColorScheme } = useUiColorScheme();

  const metaQ = useQuery({ queryKey: ["comm-meta"], queryFn: fetchCommercialFilterMeta });
  const addr2Q = useQuery({
    queryKey: ["comm-addr2", addr1],
    queryFn: () => fetchCommercialAddr2(addr1),
    enabled: !!addr1,
  });
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
        contract_year_from: scope.yearFrom === "" ? undefined : scope.yearFrom,
        contract_year_to: scope.yearTo === "" ? undefined : scope.yearTo,
        window_years: scope.windowYears,
        sort: scope.sort,
        page_size: 500,
      });
    },
    enabled: scope !== null && !!scope.addr2,
  });

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

  const years = metaQ.data?.contract_years ?? [];
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
      scope.windowYears !== windowYears);

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
    <div className="min-h-screen flex flex-col bg-slate-100 dark:bg-slate-900">
      <StatsPageHeader
        title="상업·업무 집합부동산"
        subtitle={
          <>
            집합상가 · 집합공장 — 도로(cluster)별 ㎡당 단가 · 95% CI ·{" "}
            <a href="/collective/residential/" className="underline hover:text-slate-700 dark:hover:text-slate-200">
              주거형 집합
            </a>
          </>
        }
        fontPct={fontPct}
        fontStepMin={fontStepMin}
        fontStepMax={fontStepMax}
        onBumpFont={bumpUiFontScale}
        isDark={isDark}
        onToggleTheme={toggleUiColorScheme}
      />

      <main className="flex flex-1 min-h-0" style={{ zoom: contentZoom }}>
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
                        "rounded-md border px-2.5 py-1.5 text-xs transition-colors",
                        on
                          ? "border-slate-800 bg-slate-800 text-white dark:border-slate-200 dark:bg-slate-200 dark:text-slate-900"
                          : "border-slate-300 bg-white text-slate-600 hover:border-slate-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-300",
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

            <div className="grid grid-cols-2 gap-2">
              <label className="text-xs block space-y-1">
                <span className="text-slate-500 dark:text-slate-400">연도(from)</span>
                <select className="input" value={yearFrom} onChange={(e) => setYearFrom(e.target.value ? Number(e.target.value) : "")}>
                  <option value="">—</option>
                  {years.map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-xs block space-y-1">
                <span className="text-slate-500 dark:text-slate-400">연도(to)</span>
                <select className="input" value={yearTo} onChange={(e) => setYearTo(e.target.value ? Number(e.target.value) : "")}>
                  <option value="">—</option>
                  {years.map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <label className="text-xs block space-y-1">
              <span className="text-slate-500 dark:text-slate-400">시도</span>
              <select
                className="input"
                value={addr1}
                onChange={(e) => {
                  setAddr1(e.target.value);
                  setAddr2("");
                  resetRegion();
                }}
              >
                <option value="">선택</option>
                {(metaQ.data?.addr1_list ?? []).map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
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
                    {a}
                  </option>
                ))}
              </select>
            </label>

            {addr2 && hasIntermediate && (
              <RegionChipPanel
                title={`${intermediateLabel} 선택`}
                hint={`미선택 시 ${addr2} 전체`}
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
                onSelectAll={() => setGuList((guQ.data ?? []).map((o) => o.name))}
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
                    : `1개 선택(미선택 시 시군구 전체) · 인접은 지도에서 추가`
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
                onSelectAll={() => setLeafList(visibleLeafOptions.map((o) => o.name))}
                onClear={() => setLeafList([])}
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

            <StatsWindowToggle
              value={windowYears}
              onChange={(y) => setWindowYears(normalizeStatsWindowYears(y))}
              disabled={hasYearFilter(yearFrom, yearTo)}
            />
            {hasYearFilter(yearFrom, yearTo) && (
              <p className="text-[10px] text-amber-700 dark:text-amber-400 leading-snug">
                연도가 선택되어 롤링 구간은 적용되지 않습니다.
              </p>
            )}

            <button type="button" className="btn btn-primary w-full" disabled={!addr2} onClick={runAnalysis}>
              통계분석
            </button>
          </div>
        </aside>

        <div className="layout-main min-w-0 flex-1">
          <section className="px-4 pt-4 shrink-0">
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
                    {scope.addr1} {scope.addr2} · 도로 {clustersQ.data.total}개
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
                <div className="card overflow-x-auto p-0 w-full">
                  <table className="data commercial-clusters-table">
                    <colgroup>
                      <col className="col-type" />
                      <col className="col-road" />
                      <col className="col-num" />
                      <col className="col-num" />
                      <col className="col-num" />
                      <col className="col-num" />
                      <col className="col-district" />
                    </colgroup>
                    <thead>
                      <tr>
                        <th>유형</th>
                        <th>도로명</th>
                        <th className="text-right">거래</th>
                        <th className="text-right">평균</th>
                        <th className="text-right">중앙</th>
                        <th className="text-right">95% CI</th>
                        <th className="col-district">구·동</th>
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
                            <td className="num">{fmtPrice(row.mean)}</td>
                            <td className="num">{fmtPrice(row.median)}</td>
                            <td className="num text-[10px]">{fmtCi(row.ci_lower, row.ci_upper)}</td>
                            <td className="col-district text-[10px] text-slate-600 dark:text-slate-300">
                              {[row.addr3, row.addr4].filter(Boolean).join(" · ") || "—"}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        </div>
      </main>

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
