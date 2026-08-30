import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import MacroStatsHeader from "@ch2/macro-shell/MacroStatsHeader";
import { useUiColorScheme } from "@ch2/macro-shell/useUiColorScheme";
import { useUiFontScale } from "@ch2/macro-shell/useUiFontScale";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import {
  fetchAddr2,
  fetchAddr3,
  fetchRentBuildings,
  fetchRentLeaf,
  fetchRentMeta,
  fetchRentStructure,
} from "./api/client";
import { buildRentListContext } from "./api/aiContext";
import AiAssistantPanel from "./components/AiAssistantPanel";
import { ActiveAiViewProvider, emptyAiContext, PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import BuildingDetailModal from "./components/BuildingDetailModal";
import DualHorizontalScroll from "./components/DualHorizontalScroll";
import RegionChipPanel, {
  LEFT_REGION_MULTI_SELECT,
  toggleChipMulti,
  toggleChipSingle,
} from "./components/RegionChipPanel";
import RentRegionMapHub, { type MapPanelMode } from "./components/RentRegionMapHub";
import SangkwonAnalysisModal, {
  sangkwonScopeLabel,
} from "./components/SangkwonAnalysisModal";
import StatsWindowToggle, {
  type StatsWindowYears,
} from "./components/StatsWindowToggle";
import StatsTableExpandButton from "./components/StatsTableExpandButton";
import { useRentDeepLink } from "./hooks/useRentDeepLink";
import {
  RENT_ASSET_KINDS,
  RENT_KIND_LABELS,
  assetTypeLabel,
  type LeaseMetric,
  type RentAssetType,
  type RentBuildingRow,
  type RentConversionRate,
} from "./types";
import {
  formatAddr2OptionLabel,
  formatScopeAddr2,
  isFlatSidoAddr2,
} from "./utils/flatSidoRegion";

type AnalysisScope = {
  addr1: string;
  addr2: string;
  guList: string[];
  leafList: string[];
  hasIntermediate: boolean;
  assetKinds: RentAssetType[];
  windowYears: StatsWindowYears;
  sort: string;
  sangkwonGuList: string[];
};

function fmtUnit(v: number | null | undefined) {
  if (v == null) return "—";
  const digits = Math.abs(v) < 10 ? 1 : 0;
  return v.toLocaleString("ko-KR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits === 1 ? 1 : 0,
  });
}

function ConvertedCell({ m }: { m: LeaseMetric }) {
  const v = m.mean ?? m.median;
  if (v == null) return <span className="text-slate-400">—</span>;
  return <span className="font-semibold">{fmtUnit(v)}</span>;
}

function tradeCount(row: RentBuildingRow): number {
  return (row.jeonse?.n ?? 0) + (row.mixed?.n ?? 0) + (row.monthly?.n ?? 0);
}

function formatAppliedRate(
  rates: RentConversionRate[],
  assetKinds: RentAssetType[],
  windowYears: number,
): string | null {
  const kinds = assetKinds.length ? assetKinds : RENT_ASSET_KINDS;
  const anyApplied = kinds.some((kind) => {
    const r = rates.find((x) => x.asset_type === kind);
    return Boolean(r?.gate_passed && r.r_selected != null);
  });
  if (!anyApplied) return null;
  const parts = kinds.map((kind) => {
    const r = rates.find((x) => x.asset_type === kind);
    const label = RENT_KIND_LABELS[kind];
    if (r?.gate_passed && r.r_selected != null) {
      return `${label} ${r.r_selected.toFixed(1)}%`;
    }
    return `${label} 미적용`;
  });
  return `전환율 ${windowYears}년 ${parts.join(" · ")}`;
}

function unconvertedVisibleLabels(rows: RentBuildingRow[], rates: RentConversionRate[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const row of rows) {
    const kind = row.asset_type;
    if (!kind || seen.has(kind)) continue;
    seen.add(kind);
    const r = rates.find((x) => x.asset_type === kind);
    if (!(r?.gate_passed && r.r_selected != null)) {
      out.push(assetTypeLabel(kind));
    }
  }
  return out;
}

function toggleKind(prev: RentAssetType[], kind: RentAssetType): RentAssetType[] {
  if (prev.includes(kind)) {
    const next = prev.filter((k) => k !== kind);
    return next.length ? next : prev;
  }
  return [...prev, kind];
}

function buildingMatchesQuery(row: RentBuildingRow, q: string): boolean {
  if (!q) return false;
  const hay = [row.display_name, row.jibun_address, row.road_address, row.asset_type]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return hay.includes(q);
}

export default function App() {
  const { isDark, toggleUiColorScheme } = useUiColorScheme();
  const { contentZoom, fontPct, fontStepMin, fontStepMax, bumpUiFontScale } = useUiFontScale();
  const [assetKinds, setAssetKinds] = useState<RentAssetType[]>(["apartment"]);
  const [windowYears, setWindowYears] = useState<StatsWindowYears>(5);
  const [addr1, setAddr1] = useState("");
  const [addr2, setAddr2] = useState("");
  const [guList, setGuList] = useState<string[]>([]);
  const [leafList, setLeafList] = useState<string[]>([]);
  const [sort, setSort] = useState("jeonse_equiv_median");
  const [scope, setScope] = useState<AnalysisScope | null>(null);
  const [buildingSearch, setBuildingSearch] = useState("");
  const [selected, setSelected] = useState<RentBuildingRow | null>(null);
  const [mapPanelMode, setMapPanelMode] = useState<MapPanelMode>("normal");
  const [showSangkwon, setShowSangkwon] = useState(false);
  const [tableWide, setTableWide] = useState(false);

  const metaQ = useQuery({
    queryKey: ["rent-meta", windowYears],
    queryFn: () => fetchRentMeta(windowYears),
  });

  const addr1List = metaQ.data?.addr1 ?? [];

  const addr2Q = useQuery({
    queryKey: ["rent-addr2", addr1, windowYears],
    queryFn: () => fetchAddr2(addr1, windowYears),
    enabled: Boolean(addr1),
  });
  const addr2List = addr2Q.data ?? [];

  useEffect(() => {
    if (!addr1 || addr2) return;
    const opts = addr2List;
    if (opts.length === 1 && isFlatSidoAddr2(opts[0]?.name)) {
      setAddr2(opts[0]!.name);
    }
  }, [addr1, addr2, addr2List]);

  const structureQ = useQuery({
    queryKey: ["rent-structure", addr1, addr2, windowYears],
    queryFn: () => fetchRentStructure(addr1, addr2, windowYears),
    enabled: Boolean(addr1 && addr2),
  });
  const hasIntermediate = structureQ.data?.has_intermediate ?? false;
  const intermediateLabel = structureQ.data?.intermediate_label ?? "구";

  const guQ = useQuery({
    queryKey: ["rent-gu", addr1, addr2, windowYears, assetKinds],
    queryFn: () => fetchAddr3(addr1, addr2, windowYears, assetKinds),
    enabled: Boolean(addr1 && addr2 && hasIntermediate),
  });
  const flatLeafQ = useQuery({
    queryKey: ["rent-flat-leaf", addr1, addr2, windowYears, assetKinds],
    queryFn: () => fetchAddr3(addr1, addr2, windowYears, assetKinds),
    enabled: Boolean(addr1 && addr2 && !hasIntermediate && structureQ.isSuccess),
  });
  const leafQ = useQuery({
    queryKey: ["rent-leaf", addr1, addr2, windowYears, assetKinds, guList],
    queryFn: () => fetchRentLeaf(addr1, addr2, windowYears, guList, assetKinds),
    enabled: Boolean(addr1 && addr2 && hasIntermediate),
  });

  const leafOptions = useMemo(() => {
    if (!hasIntermediate) {
      return (flatLeafQ.data ?? []).map((o) => ({ ...o, id: o.name }));
    }
    const opts = leafQ.data ?? [];
    const filtered = !guList.length ? opts : opts.filter((o) => o.parent && guList.includes(o.parent));
    return filtered.map((o) => ({ ...o, id: `${o.parent ?? ""}|${o.name}` }));
  }, [hasIntermediate, flatLeafQ.data, leafQ.data, guList]);

  useRentDeepLink({
    addr1,
    addr2,
    addr1Options: addr1List,
    addr2Options: addr2List.map((o) => o.name),
    leafOptions,
    setAddr1,
    setAddr2,
    setLeafList,
    setGuList,
  });

  useEffect(() => {
    const allowed = new Set(leafOptions.map((o) => o.name));
    setLeafList((prev) => prev.filter((n) => allowed.has(n)));
  }, [leafOptions]);

  const buildingsQ = useQuery({
    queryKey: ["rent-buildings", scope],
    queryFn: () => {
      if (!scope) throw new Error("no scope");
      return fetchRentBuildings({
        addr1: scope.addr1,
        addr2: scope.addr2,
        addr3List: scope.hasIntermediate
          ? scope.guList.length
            ? scope.guList
            : undefined
          : scope.leafList.length
            ? scope.leafList
            : undefined,
        addr4List: scope.hasIntermediate && scope.leafList.length ? scope.leafList : undefined,
        assetTypes: scope.assetKinds,
        windowYears: scope.windowYears,
        sort: scope.sort,
      });
    },
    enabled: scope !== null && !!scope.addr2,
  });

  const items = buildingsQ.data?.items ?? [];
  const buildingSearchQ = buildingSearch.trim().toLowerCase();
  const buildingMatchCount = useMemo(() => {
    if (!buildingSearchQ || !items.length) return 0;
    return items.filter((row) => buildingMatchesQuery(row, buildingSearchQ)).length;
  }, [items, buildingSearchQ]);

  useEffect(() => {
    setBuildingSearch("");
  }, [scope]);

  useEffect(() => {
    if (!buildingSearchQ || buildingMatchCount === 0) return;
    const el = document.querySelector<HTMLElement>("[data-building-highlight='1']");
    el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [buildingSearchQ, buildingMatchCount, items]);

  const appliedRateLabel = useMemo(() => {
    if (!scope) return null;
    return formatAppliedRate(
      buildingsQ.data?.conversion_rates ?? [],
      scope.assetKinds,
      scope.windowYears,
    );
  }, [buildingsQ.data, scope]);

  const unconvertedLabels = useMemo(
    () => unconvertedVisibleLabels(items, buildingsQ.data?.conversion_rates ?? []),
    [items, buildingsQ.data?.conversion_rates],
  );

  const rentAiContext = useMemo(
    () =>
      buildRentListContext({
        addr1: scope?.addr1 ?? addr1,
        addr2: scope?.addr2 ?? addr2,
        addr3: scope?.leafList[0],
        windowYears: scope?.windowYears ?? windowYears,
        assetKinds: scope?.assetKinds ?? assetKinds,
        rates: buildingsQ.data?.conversion_rates ?? [],
        conversionApplied: Boolean(buildingsQ.data?.conversion_applied),
        conversionFallback: buildingsQ.data?.conversion_fallback,
        conversionScope: buildingsQ.data?.conversion_scope,
        conversionMethod: buildingsQ.data?.conversion_method,
      }),
    [scope, addr1, addr2, windowYears, assetKinds, buildingsQ.data],
  );

  const scopeStale =
    scope !== null &&
    (JSON.stringify(scope.assetKinds) !== JSON.stringify(assetKinds) ||
      scope.addr1 !== addr1 ||
      scope.addr2 !== addr2 ||
      JSON.stringify(scope.guList) !== JSON.stringify(guList) ||
      JSON.stringify(scope.leafList) !== JSON.stringify(leafList) ||
      scope.hasIntermediate !== hasIntermediate ||
      scope.windowYears !== windowYears ||
      scope.sort !== sort);

  const sangkwonGuList = useMemo(() => {
    if (!hasIntermediate) return [];
    if (guList.length) return [...guList];
    const parents = new Set<string>();
    for (const name of leafList) {
      const o = leafOptions.find((x) => x.name === name);
      if (o?.parent) parents.add(o.parent);
    }
    return [...parents];
  }, [hasIntermediate, guList, leafList, leafOptions]);

  const runAnalysis = () => {
    if (!addr1 || !addr2) return;
    setScope({
      addr1,
      addr2,
      guList: [...guList],
      leafList: [...leafList],
      hasIntermediate,
      assetKinds: [...assetKinds],
      windowYears,
      sort,
      sangkwonGuList,
    });
    setSelected(null);
    setShowSangkwon(false);
  };

  const resetRegion = () => {
    setGuList([]);
    setLeafList([]);
    setScope(null);
    setSelected(null);
    setShowSangkwon(false);
  };

  const addr2ScopeLabel = formatScopeAddr2(addr2, addr1) || addr1;

  return (
    <ActiveAiViewProvider fallback={emptyAiContext("rent", "RentListCard")}>
    <div className="h-screen flex flex-col overflow-hidden">
      <MacroStatsHeader
        currentApp="rent"
        title="임대시장"
        fontPct={fontPct}
        fontStepMin={fontStepMin}
        fontStepMax={fontStepMax}
        onBumpFont={bumpUiFontScale}
        isDark={isDark}
        onToggleTheme={toggleUiColorScheme}
        rightSlot={<AiAssistantPanel />}
      />
      <PublishAiContext context={rentAiContext} />

      <div className="flex flex-1 min-h-0 overflow-hidden" style={{ zoom: contentZoom }}>
        <aside className="layout-sidebar p-4 space-y-3">
          <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">조건</h2>
          <div className="space-y-1">
            <span className="text-xs text-slate-500">유형</span>
            <div className="flex flex-wrap gap-1.5">
              {RENT_ASSET_KINDS.map((kind) => {
                const on = assetKinds.includes(kind);
                return (
                  <button
                    key={kind}
                    type="button"
                    className={clsx(
                      "rounded-md border px-2 py-1 text-xs font-semibold",
                      on
                        ? "border-indigo-500 bg-indigo-600 text-white"
                        : "border-slate-300 bg-white dark:border-slate-500 dark:bg-slate-800",
                    )}
                    onClick={() => {
                      setAssetKinds((prev) => toggleKind(prev, kind));
                      resetRegion();
                    }}
                  >
                    {RENT_KIND_LABELS[kind]}
                  </button>
                );
              })}
            </div>
          </div>
          <label className="text-xs block space-y-1">
            <span className="text-slate-500">시도</span>
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
              {addr1List.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs block space-y-1">
            <span className="text-slate-500">시군구 (괄호=거래)</span>
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
              {addr2List.map((n) => (
                <option key={n.name} value={n.name}>
                  {formatAddr2OptionLabel(n.name)} ({n.count})
                </option>
              ))}
            </select>
          </label>
          {addr2 && hasIntermediate && (
            <RegionChipPanel
              title={`${intermediateLabel} 선택`}
              hint={`미선택 시 ${addr2ScopeLabel} 전체 · 괄호는 거래 건수`}
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
                  ? `${intermediateLabel} 선택 후 1개 선택 · 인접은 지도에서 추가 · 괄호는 거래 건수`
                  : `1개 선택(미선택 시 ${addr2ScopeLabel} 전체) · 인접은 지도에서 추가 · 괄호는 거래 건수`
              }
              selected={leafList}
              options={leafOptions}
              formatLabel={(o) => (o.parent ? `${o.parent} · ${o.name}` : o.name)}
              multiSelect={LEFT_REGION_MULTI_SELECT}
              onToggle={(name) =>
                setLeafList((prev) =>
                  LEFT_REGION_MULTI_SELECT ? toggleChipMulti(prev, name) : toggleChipSingle(prev, name),
                )
              }
              onSelectAll={() => setLeafList(leafOptions.map((o) => o.name))}
              onClear={() => setLeafList([])}
            />
          )}
          <label className="text-xs block space-y-1">
            <span className="text-slate-500">정렬</span>
            <select className="input" value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="jeonse_equiv_median">전세환산</option>
              <option value="total_n">거래건수</option>
              <option value="name">건물명</option>
            </select>
          </label>
          <StatsWindowToggle value={windowYears} onChange={setWindowYears} />
          <button type="button" className="btn btn-primary w-full" disabled={!addr2} onClick={runAnalysis}>
            통계분석
          </button>
          <button
            type="button"
            className="btn btn-ghost w-full"
            disabled={!addr2}
            onClick={() => setShowSangkwon(true)}
          >
            상권통계
          </button>
          <p className="text-[10px] text-slate-400 leading-snug">
            목록은 건물 1행 · r 적용 환산 평균(만원/㎡). 전세/반전세/월세 원값·거래·회귀는 상세.
          </p>
          {addr2 && (
            <p className="text-[10px] text-slate-400 leading-snug">
              상권통계: {sangkwonScopeLabel({ addr1, addr2, sangkwonGuList })} 공표 · 주거와 별개
            </p>
          )}
        </aside>

        <div className="layout-main">
          <section className="px-4 pt-4 shrink-0">
            <RentRegionMapHub
              scope={{
                assetType: assetKinds[0] ?? "apartment",
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
                        jibunAddress: selected.jibun_address || null,
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
                      jibunAddress: row.jibun_address || null,
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
            {metaQ.data && (metaQ.data.addr1?.length ?? 0) === 0 && (
              <p className="text-sm text-amber-700">
                임대 마트가 없습니다. <code>py pipeline/rent/build_building_stats.py</code> 를 실행하세요.
              </p>
            )}
            {addr1List.length === 1 && addr1List[0] === "서울특별시" && (
              <p className="text-xs text-amber-700 dark:text-amber-300 mb-2 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded px-2 py-1">
                이 창의 건물 목록은 아직 서울만 있습니다. 창을 바꾸거나 전국 적재가 끝날 때까지 기다리세요.
              </p>
            )}
            {!scope && (
              <p className="text-sm text-slate-500 dark:text-slate-400">
                시군구까지 선택한 뒤 「통계분석」을 누르면 건물 목록이 표시됩니다.
              </p>
            )}
            {scopeStale && (
              <p className="text-xs text-amber-700 dark:text-amber-300 mb-2 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded px-2 py-1">
                조건이 변경되었습니다. 「통계분석」을 다시 실행하세요.
              </p>
            )}
            {scope && buildingsQ.isLoading && <p className="text-sm text-slate-400">불러오는 중…</p>}
            {scope && buildingsQ.isError && (
              <p className="text-sm text-red-600">목록을 불러오지 못했습니다. 마트 적재와 API를 확인하세요.</p>
            )}
            {scope && buildingsQ.data && (
              <>
                <div className="flex flex-wrap items-center gap-2 mb-2 text-xs text-slate-500">
                  <p className="flex-1 min-w-[12rem]">
                    {scope.addr1}
                    {formatScopeAddr2(scope.addr2, scope.addr1)
                      ? ` ${formatScopeAddr2(scope.addr2, scope.addr1)}`
                      : ""}
                    {scope.guList.length ? ` ${scope.guList.join(", ")}` : ""}
                    {scope.leafList.length ? ` ${scope.leafList.join(", ")}` : ""} ·{" "}
                    {buildingsQ.data.total}동 · {buildingsQ.data.stats_as_of_label} {scope.windowYears}년 창
                    {appliedRateLabel && (
                      <span className="ml-2 inline-flex items-center gap-1 font-medium text-indigo-600 dark:text-indigo-300">
                        {appliedRateLabel}
                        <StatsGlossaryHelp termId="rent_conversion_rate" size="xs" />
                      </span>
                    )}
                    {buildingsQ.data.conversion_fallback && (
                      <span className="ml-1 text-amber-600">동 미달·시군구</span>
                    )}
                    {buildingsQ.data.conversion_applied && unconvertedLabels.length > 0 && (
                      <span className="ml-2 text-amber-600">
                        {unconvertedLabels.join("·")} 전환율 미충족 · 해당 행은 환산 없음
                      </span>
                    )}
                    {!buildingsQ.data.conversion_applied && buildingsQ.data.total > 0 && (
                      <span className="ml-2 text-amber-600">전환율 미충족(게이트) · 원값만 표시</span>
                    )}
                    {!buildingsQ.data.conversion_applied && buildingsQ.data.total === 0 && (
                      <span className="ml-2 text-amber-600">선택한 유형의 건물이 없음</span>
                    )}
                  </p>
                  <div className="flex items-center gap-2 shrink-0">
                    <StatsTableExpandButton
                      expanded={tableWide}
                      onToggle={() => setTableWide((v) => !v)}
                      title="매매 평균(만원/㎡)과 전세가율을 보여 줍니다"
                    />
                    <label className="flex items-center gap-1.5">
                      <span>검색</span>
                      <input
                        type="search"
                        className="input py-1 w-48"
                        placeholder="건물명·주소…"
                        value={buildingSearch}
                        onChange={(e) => setBuildingSearch(e.target.value)}
                      />
                    </label>
                  </div>
                </div>
                {buildingsQ.data.total === 0 && (
                  <p className="text-sm text-slate-500 dark:text-slate-400 mb-2">
                    칩 숫자는 선택한 유형의 건물 수입니다. 유형을 더하면 목록이 생깁니다. 전환율 게이트는 목록을 숨기지 않습니다.
                  </p>
                )}
                <div className="card p-0">
                  <DualHorizontalScroll key={tableWide ? "wide" : "compact"}>
                  <table className={clsx("data buildings-table", tableWide && "is-wide")}>
                    <colgroup>
                      <col className="col-type" />
                      <col className="col-name" />
                      <col className="col-num" />
                      <col className="col-num" />
                      {tableWide && <col className="col-num" />}
                      {tableWide && <col className="col-num" />}
                      <col className="col-num" />
                      <col className="col-year" />
                      <col className="col-jibun" />
                      <col className="col-road" />
                    </colgroup>
                    <thead>
                      <tr>
                        <th>유형</th>
                        <th>건물명</th>
                        <th>거래건수</th>
                        <th>
                          <span className="inline-flex items-center justify-center gap-0.5">
                            전세전환값
                            <StatsGlossaryHelp termId="jeonse_equiv" size="xs" />
                          </span>
                        </th>
                        {tableWide && (
                          <th>
                            <span className="inline-flex items-center justify-center gap-0.5">
                              매매가
                              <StatsGlossaryHelp termId="sale_unit_mean" size="xs" />
                            </span>
                          </th>
                        )}
                        {tableWide && (
                          <th>
                            <span className="inline-flex items-center justify-center gap-0.5">
                              전세가율
                              <StatsGlossaryHelp termId="jeonse_to_sale_pct" size="xs" />
                            </span>
                          </th>
                        )}
                        <th>
                          <span className="inline-flex items-center justify-center gap-0.5">
                            월세전환값
                            <StatsGlossaryHelp termId="monthly_equiv" size="xs" />
                          </span>
                        </th>
                        <th>준공</th>
                        <th>지번주소</th>
                        <th>도로명주소</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((row) => {
                        const n = tradeCount(row);
                        const saleN = row.sale?.n ?? 0;
                        const ratio = row.jeonse_to_sale_pct;
                        return (
                          <tr
                            key={`${row.building_key}|${row.asset_type}`}
                            className={clsx(
                              "hover:bg-indigo-50 dark:hover:bg-indigo-950/40 cursor-pointer",
                              buildingMatchesQuery(row, buildingSearchQ) &&
                                "!bg-yellow-200 dark:!bg-yellow-700/50",
                            )}
                            data-building-highlight={
                              buildingMatchesQuery(row, buildingSearchQ) ? "1" : undefined
                            }
                            onClick={() => setSelected(row)}
                          >
                            <td className="text-[10px] text-center">{assetTypeLabel(row.asset_type)}</td>
                            <td className="name" title={row.display_name}>
                              {row.display_name}
                            </td>
                            <td className="num">
                              {n ? n.toLocaleString("ko-KR") : "—"}
                              {n > 0 && n < 15 && (
                                <span className="ml-0.5 text-[9px] text-amber-600">n&lt;15</span>
                              )}
                            </td>
                            <td className="lease">
                              <ConvertedCell m={row.jeonse_equiv} />
                            </td>
                            {tableWide && (
                              <td className="lease">
                                {row.sale?.mean != null ? (
                                  <>
                                    <span className="font-semibold">{fmtUnit(row.sale.mean)}</span>
                                    {saleN > 0 && saleN < 15 && (
                                      <span className="ml-0.5 text-[9px] text-amber-600">n&lt;15</span>
                                    )}
                                  </>
                                ) : (
                                  <span className="text-slate-400">—</span>
                                )}
                              </td>
                            )}
                            {tableWide && (
                              <td className="num">
                                {ratio != null ? `${ratio.toFixed(1)}%` : "—"}
                              </td>
                            )}
                            <td className="lease">
                              <ConvertedCell m={row.monthly_equiv} />
                            </td>
                            <td className="num">{row.building_year ?? "—"}</td>
                            <td className="addr truncate" title={row.jibun_address}>
                              {row.jibun_address || "—"}
                            </td>
                            <td className="addr truncate text-slate-500" title={row.road_address}>
                              {row.road_address || "—"}
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
      </div>

      {selected && scope && (
        <BuildingDetailModal
          row={selected}
          windowYears={scope.windowYears}
          peers={items.filter((r) => r.asset_type === selected.asset_type)}
          appliedRate={
            (buildingsQ.data?.conversion_rates ?? []).find(
              (r) => r.asset_type === selected.asset_type,
            ) ?? null
          }
          onClose={() => setSelected(null)}
        />
      )}
      {showSangkwon && addr2 && (
        <SangkwonAnalysisModal
          scope={{ addr1, addr2, sangkwonGuList }}
          onClose={() => {
            setShowSangkwon(false);
          }}
        />
      )}
    </div>
    </ActiveAiViewProvider>
  );
}
