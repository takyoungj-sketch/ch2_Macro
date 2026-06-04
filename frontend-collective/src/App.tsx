import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  fetchAddr2,
  fetchAddr3WithCounts,
  fetchBuildings,
  fetchFilterMeta,
  fetchLeafRegions,
  fetchRegionStructure,
  type BuildingStatsRow,
} from "./api/client";
import BuildingDetailModal from "./components/BuildingDetailModal";
import type { AssetType, RegionOption } from "./types";
import { ASSET_LABELS } from "./types";

type AnalysisScope = {
  assetType: AssetType;
  addr1: string;
  addr2: string;
  guList: string[];
  leafList: string[];
  hasIntermediate: boolean;
  yearFrom: number | "";
  yearTo: number | "";
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

function fmtNum(n: number) {
  return n.toLocaleString();
}

function RegionChipPanel({
  title,
  hint,
  selected,
  options,
  formatLabel,
  onToggle,
  onSelectAll,
  onClear,
}: {
  title: string;
  hint: string;
  selected: string[];
  options: { id?: string; name: string; count: number; parent?: string | null }[];
  formatLabel?: (o: { name: string; count: number; parent?: string | null }) => string;
  onToggle: (name: string) => void;
  onSelectAll: () => void;
  onClear: () => void;
}) {
  const label = formatLabel ?? ((o) => o.name);
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-slate-700">{title}</span>
        <span className="text-[10px] text-slate-400">
          {selected.length ? `${selected.length}개` : "전체"}
        </span>
      </div>
      <p className="text-[10px] text-slate-500 leading-snug">{hint}</p>
      <div className="flex gap-1">
        <button type="button" className="btn btn-ghost text-[10px] py-0.5 px-1.5" onClick={onSelectAll} disabled={!options.length}>
          전체
        </button>
        <button type="button" className="btn btn-ghost text-[10px] py-0.5 px-1.5" onClick={onClear} disabled={!selected.length}>
          해제
        </button>
      </div>
      <div className="flex flex-wrap gap-1 max-h-32 overflow-y-auto border border-slate-100 rounded p-1.5">
        {options.map((o) => (
          <label
            key={o.id ?? o.name}
            className={clsx(
              "flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded border cursor-pointer",
              selected.includes(o.name)
                ? "bg-slate-800 text-white border-slate-800"
                : "bg-white text-slate-700 border-slate-200 hover:border-slate-400",
            )}
          >
            <input type="checkbox" className="sr-only" checked={selected.includes(o.name)} onChange={() => onToggle(o.name)} />
            {label(o)}
            <span className={clsx("opacity-70", selected.includes(o.name) && "text-slate-300")}>({fmtNum(o.count)})</span>
          </label>
        ))}
        {!options.length && <span className="text-[10px] text-slate-400">항목 없음</span>}
      </div>
    </div>
  );
}

export default function App() {
  const [assetType, setAssetType] = useState<AssetType>("apartment");
  const [addr1, setAddr1] = useState("");
  const [addr2, setAddr2] = useState("");
  const [guList, setGuList] = useState<string[]>([]);
  const [leafList, setLeafList] = useState<string[]>([]);
  const [yearFrom, setYearFrom] = useState<number | "">("");
  const [yearTo, setYearTo] = useState<number | "">("");
  const [sort, setSort] = useState("count");
  const [scope, setScope] = useState<AnalysisScope | null>(null);
  const [selected, setSelected] = useState<BuildingStatsRow | null>(null);

  const metaQ = useQuery({ queryKey: ["coll-meta"], queryFn: fetchFilterMeta });
  const addr2Q = useQuery({
    queryKey: ["coll-addr2", addr1],
    queryFn: () => fetchAddr2(addr1),
    enabled: !!addr1,
  });
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
      return fetchBuildings({
        asset_type: scope.assetType,
        addr1: scope.addr1,
        addr2: scope.addr2,
        ...regionParams,
        contract_year_from: scope.yearFrom === "" ? undefined : scope.yearFrom,
        contract_year_to: scope.yearTo === "" ? undefined : scope.yearTo,
        sort: scope.sort,
        page_size: 500,
      });
    },
    enabled: scope !== null && !!scope.addr2,
  });

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
    <div className="min-h-screen flex flex-col">
      <header className="bg-slate-900 text-white px-6 py-4">
        <p className="text-xs text-slate-400 mb-1">
          <a href="/" className="hover:text-white">
            CH2 Macro
          </a>
          {" · "}
          <a href="/land/" className="hover:text-white">
            토지
          </a>
          {" · "}
          <a href="/built/" className="hover:text-white">
            복합
          </a>
        </p>
        <h1 className="text-xl font-semibold">집합부동산 통계</h1>
        <p className="text-sm text-slate-400 mt-1">아파트 · 연립 · 오피스텔 — 건물별 단가·신뢰구간</p>
      </header>

      <main className="flex flex-1 min-h-0">
        <aside className="layout-sidebar p-4">
          <h2 className="text-sm font-semibold mb-3">조건</h2>
          <div className="space-y-3">
            <label className="text-xs block space-y-1">
              <span className="text-slate-500">유형</span>
              <select
                className="input"
                value={assetType}
                onChange={(e) => {
                  setAssetType(e.target.value as AssetType);
                  resetRegion();
                }}
              >
                {(Object.keys(ASSET_LABELS) as AssetType[]).map((t) => (
                  <option key={t} value={t}>
                    {ASSET_LABELS[t]}
                  </option>
                ))}
              </select>
            </label>

            <div className="grid grid-cols-2 gap-2">
              <label className="text-xs block space-y-1">
                <span className="text-slate-500">연도(from)</span>
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
                <span className="text-slate-500">연도(to)</span>
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
                {(metaQ.data?.addr1_list ?? []).map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-xs block space-y-1">
              <span className="text-slate-500">시군구</span>
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
                onToggle={(name) => setGuList((prev) => (prev.includes(name) ? prev.filter((x) => x !== name) : [...prev, name]))}
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
                hint={hasIntermediate ? `${intermediateLabel} 선택 후 좁힐 수 있습니다` : "미선택 시 시군구 전체"}
                selected={leafList}
                options={visibleLeafOptions}
                formatLabel={(o) => (o.parent ? `${o.parent} · ${o.name}` : o.name)}
                onToggle={(name) => setLeafList((prev) => (prev.includes(name) ? prev.filter((x) => x !== name) : [...prev, name]))}
                onSelectAll={() => setLeafList(visibleLeafOptions.map((o) => o.name))}
                onClear={() => setLeafList([])}
              />
            )}

            <label className="text-xs block space-y-1">
              <span className="text-slate-500">정렬</span>
              <select className="input" value={sort} onChange={(e) => setSort(e.target.value)}>
                <option value="count">거래수</option>
                <option value="mean">평균 단가</option>
                <option value="display_name">건물명</option>
              </select>
            </label>

            <button type="button" className="btn btn-primary w-full" disabled={!addr2} onClick={runAnalysis}>
              통계분석
            </button>
          </div>
        </aside>

        <div className="layout-main p-4">
          {!scope && (
            <p className="text-sm text-slate-500">시군구까지 선택한 뒤 「통계분석」을 누르면 건물 목록이 표시됩니다.</p>
          )}
          {scopeStale && (
            <p className="text-xs text-amber-700 mb-2 bg-amber-50 border border-amber-200 rounded px-2 py-1">
              조건이 변경되었습니다. 「통계분석」을 다시 실행하세요.
            </p>
          )}
          {scope && buildingsQ.isLoading && <p className="text-sm text-slate-500">불러오는 중…</p>}
          {scope && buildingsQ.isError && <p className="text-sm text-red-600">건물 목록을 불러오지 못했습니다.</p>}
          {scope && buildingsQ.data && (
            <>
              <p className="text-xs text-slate-500 mb-2">
                {scope.addr1} {scope.addr2} · 건물 {buildingsQ.data.total}개
              </p>
              <div className="card overflow-x-auto p-0 inline-block max-w-full">
                <table className="data buildings-table">
                  <colgroup>
                    <col className="col-name" />
                    <col className="col-num" />
                    <col className="col-num" />
                    <col className="col-num" />
                    <col className="col-num" />
                    <col className="col-year" />
                    <col className="col-addr" />
                  </colgroup>
                  <thead>
                    <tr>
                      <th>건물명</th>
                      <th className="text-right">거래</th>
                      <th className="text-right">평균</th>
                      <th className="text-right">중앙</th>
                      <th className="text-right">95% CI</th>
                      <th className="text-right">신축연도</th>
                      <th>주소</th>
                    </tr>
                  </thead>
                  <tbody>
                    {buildingsQ.data.items.map((row) => (
                      <tr
                        key={row.building_key}
                        className="hover:bg-indigo-50 cursor-pointer"
                        onClick={() => setSelected(row)}
                        title={row.display_name}
                      >
                        <td className="name">
                          {row.display_name}
                          {!row.is_reliable && <span className="ml-0.5 text-[9px] text-amber-600">n&lt;15</span>}
                        </td>
                        <td className="num">{row.count}</td>
                        <td className="num">{fmtPrice(row.mean)}</td>
                        <td className="num">{fmtPrice(row.median)}</td>
                        <td className="num text-[10px]">{fmtCiCompact(row.ci_lower, row.ci_upper)}</td>
                        <td className="num">{row.building_year ?? "—"}</td>
                        <td className="addr truncate" title={row.address || undefined}>
                          {row.address || "—"}
                        </td>
                      </tr>
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
          yearFrom={scope.yearFrom === "" ? undefined : scope.yearFrom}
          yearTo={scope.yearTo === "" ? undefined : scope.yearTo}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
