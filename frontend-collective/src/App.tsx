import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchAddr2,
  fetchAddr3WithCounts,
  fetchAllBuildings,
  fetchFilterMeta,
  fetchLeafRegions,
  fetchRegionStructure,
  type BuildingStatsRow,
} from "./api/client";
import BuildingDetailModal from "./components/BuildingDetailModal";
import StatsPageHeader from "./components/StatsPageHeader";
import RegionChipPanel from "./components/RegionChipPanel";
import StatsWindowToggle, { normalizeStatsWindowYears, type StatsWindowYears } from "./components/StatsWindowToggle";
import type { AssetSelectorType, RegionOption } from "./types";
import { ASSET_SELECTOR_LABELS, assetTypeLabel } from "./types";
import {
  applyYearFrom,
  applyYearTo,
  clampYearsToAvailable,
  filterFromYearOptions,
  filterToYearOptions,
  hasYearFilter,
} from "./utils/contractYearRange";
import {
  formatAddr2OptionLabel,
  formatScopeAddr2,
  isFlatSidoAddr2,
} from "./utils/flatSidoRegion";
import { useUiFontScale } from "./hooks/useUiFontScale";
import { useUiColorScheme } from "./hooks/useUiColorScheme";

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

function BuildingTableRow({ row, onSelect }: { row: BuildingStatsRow; onSelect: (row: BuildingStatsRow) => void }) {
  return (
    <tr
      className="hover:bg-indigo-50 dark:hover:bg-indigo-950/40 cursor-pointer"
      onClick={() => onSelect(row)}
      title={row.display_name}
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

export default function App() {
  const [assetType, setAssetType] = useState<AssetSelectorType>("apartment");
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
  const { contentZoom, fontPct, fontStepMin, fontStepMax, bumpUiFontScale } = useUiFontScale();
  const { isDark, toggleUiColorScheme } = useUiColorScheme();

  const metaQ = useQuery({
    queryKey: ["coll-meta", assetType],
    queryFn: () => fetchFilterMeta(assetType),
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

  const guQ = useQuery({
    queryKey: ["coll-gu", addr1, addr2, assetType],
    queryFn: () => fetchAddr3WithCounts(addr1, addr2, assetType),
    enabled: !!addr1 && !!addr2 && hasIntermediate,
  });
  const flatLeafQ = useQuery({
    queryKey: ["coll-flat-leaf", addr1, addr2, assetType],
    queryFn: () => fetchAddr3WithCounts(addr1, addr2, assetType),
    enabled: !!addr1 && !!addr2 && !hasIntermediate && structureQ.isSuccess,
  });
  const leafQ = useQuery({
    queryKey: ["coll-leaf", addr1, addr2, assetType, guList],
    queryFn: () => fetchLeafRegions(addr1, addr2, guList, assetType),
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
        sort: scope.sort,
      });
    },
    enabled: scope !== null && !!scope.addr2,
  });

  const addr2ScopeLabel = formatScopeAddr2(addr2, addr1) || addr1;

  const years = metaQ.data?.contract_years ?? [];
  const fromYearOptions = useMemo(() => filterFromYearOptions(years, yearTo), [years, yearTo]);
  const toYearOptions = useMemo(() => filterToYearOptions(years, yearFrom), [years, yearFrom]);
  const yearFilterActive = hasYearFilter(yearFrom, yearTo);

  useEffect(() => {
    const next = clampYearsToAvailable(yearFrom, yearTo, years);
    if (next.from !== yearFrom) setYearFrom(next.from);
    if (next.to !== yearTo) setYearTo(next.to);
  }, [years, yearFrom, yearTo]);

  const handleYearFromChange = (value: number | "") => {
    setYearFrom(value);
    setYearTo((prev) => applyYearFrom(value, prev));
  };

  const handleYearToChange = (value: number | "") => {
    setYearTo(value);
    setYearFrom((prev) => applyYearTo(prev, value));
  };
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
    <div className="min-h-screen flex flex-col bg-slate-100 dark:bg-slate-900">
      <StatsPageHeader
        title="주거형 집합부동산"
        subtitle={
          <>
            아파트 · 연립 · 오피스텔 · 분양권 — 건물별 ㎡당 단가·신뢰구간 ·{" "}
            <a href="/collective/commercial/" className="underline hover:text-slate-700 dark:hover:text-slate-200">
              상업·업무 집합
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
            <label className="text-xs block space-y-1">
              <span className="text-slate-500 dark:text-slate-400">유형</span>
              <select
                className="input"
                value={assetType}
                onChange={(e) => {
                  setAssetType(e.target.value as AssetSelectorType);
                  resetRegion();
                }}
              >
                {(Object.keys(ASSET_SELECTOR_LABELS) as AssetSelectorType[]).map((t) => (
                  <option key={t} value={t}>
                    {ASSET_SELECTOR_LABELS[t]}
                  </option>
                ))}
              </select>
            </label>

            <div className="grid grid-cols-2 gap-2">
              <label className="text-xs block space-y-1">
                <span className="text-slate-500 dark:text-slate-400">연도(from)</span>
                <select
                  className="input"
                  value={yearFrom}
                  onChange={(e) => handleYearFromChange(e.target.value ? Number(e.target.value) : "")}
                >
                  <option value="">—</option>
                  {fromYearOptions.map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-xs block space-y-1">
                <span className="text-slate-500 dark:text-slate-400">연도(to)</span>
                <select
                  className="input"
                  value={yearTo}
                  onChange={(e) => handleYearToChange(e.target.value ? Number(e.target.value) : "")}
                >
                  <option value="">—</option>
                  {toYearOptions.map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p className="text-[10px] text-slate-400 leading-snug">
              연도 미선택: 직전 월말 기준 롤링 {windowYears}년 창. 연도 지정: 해당 연도 거래만 집계(실시간).
            </p>

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
                onToggle={(name) => setGuList((prev) => (prev.includes(name) ? prev.filter((x) => x !== name) : [...prev, name]))}
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
                hint={hasIntermediate ? `${intermediateLabel} 선택 후 좁힐 수 있습니다` : `미선택 시 ${addr2ScopeLabel} 전체`}
                selected={leafList}
                options={visibleLeafOptions}
                formatLabel={(o) => (o.parent ? `${o.parent} · ${o.name}` : o.name)}
                onToggle={(name) => setLeafList((prev) => (prev.includes(name) ? prev.filter((x) => x !== name) : [...prev, name]))}
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
              disabled={yearFilterActive}
            />
            {yearFilterActive && (
              <p className="text-[10px] text-amber-700 dark:text-amber-400 leading-snug">연도가 선택되어 롤링 구간은 적용되지 않습니다.</p>
            )}

            <button type="button" className="btn btn-primary w-full" disabled={!addr2} onClick={runAnalysis}>
              통계분석
            </button>
          </div>
        </aside>

        <div className="layout-main p-4">
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
              <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">
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
                        onSelect={setSelected}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </main>

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
  );
}
