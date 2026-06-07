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
import RegionChipPanel from "./components/RegionChipPanel";
import { COMMERCIAL_ASSET_LABELS, type CommercialAssetType, type CommercialClusterRow, type RegionOption } from "./types";

function fmtPrice(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function fmtCi(lo: number | null | undefined, hi: number | null | undefined) {
  if (lo == null || hi == null) return "—";
  return `${fmtPrice(lo)}~${fmtPrice(hi)}`;
}

type AnalysisScope = {
  assetType: CommercialAssetType;
  addr1: string;
  addr2: string;
  guList: string[];
  leafList: string[];
  hasIntermediate: boolean;
  yearFrom: number | "";
  yearTo: number | "";
  sort: string;
};

export default function CommercialApp() {
  const [assetType, setAssetType] = useState<CommercialAssetType>("collective_shop");
  const [addr1, setAddr1] = useState("");
  const [addr2, setAddr2] = useState("");
  const [guList, setGuList] = useState<string[]>([]);
  const [leafList, setLeafList] = useState<string[]>([]);
  const [yearFrom, setYearFrom] = useState<number | "">("");
  const [yearTo, setYearTo] = useState<number | "">("");
  const [sort, setSort] = useState("count");
  const [scope, setScope] = useState<AnalysisScope | null>(null);
  const [selected, setSelected] = useState<CommercialClusterRow | null>(null);

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

  const guQ = useQuery({
    queryKey: ["comm-gu", addr1, addr2, assetType],
    queryFn: () => fetchCommercialAddr3(addr1, addr2, assetType),
    enabled: !!addr1 && !!addr2 && hasIntermediate,
  });
  const flatLeafQ = useQuery({
    queryKey: ["comm-flat-leaf", addr1, addr2, assetType],
    queryFn: () => fetchCommercialAddr3(addr1, addr2, assetType),
    enabled: !!addr1 && !!addr2 && !hasIntermediate && structureQ.isSuccess,
  });
  const leafQ = useQuery({
    queryKey: ["comm-leaf", addr1, addr2, assetType, guList],
    queryFn: () => fetchCommercialLeafRegions(addr1, addr2, guList, assetType),
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
          {" · "}
          <a href="/collective/" className="hover:text-white">
            집합
          </a>
        </p>
        <h1 className="text-xl font-semibold">상업·업무 집합부동산</h1>
        <p className="text-sm text-slate-400 mt-1">
          집합상가 · 집합공장 — 도로(cluster)별 ㎡당 단가 · 95% CI ·{" "}
          <a href="/collective/residential/" className="underline hover:text-white">
            주거형 집합
          </a>
        </p>
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
                  setAssetType(e.target.value as CommercialAssetType);
                  resetRegion();
                }}
              >
                {(Object.keys(COMMERCIAL_ASSET_LABELS) as CommercialAssetType[]).map((t) => (
                  <option key={t} value={t}>
                    {COMMERCIAL_ASSET_LABELS[t]}
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
                <option value="display_label">도로명</option>
              </select>
            </label>

            <button type="button" className="btn btn-primary w-full" disabled={!addr2} onClick={runAnalysis}>
              통계분석
            </button>
          </div>
        </aside>

        <div className="layout-main p-4 min-w-0 flex-1">
            {!scope && (
              <p className="text-sm text-slate-500">시군구까지 선택한 뒤 「통계분석」을 누르면 도로(cluster) 목록이 표시됩니다.</p>
            )}
            {scopeStale && (
              <p className="text-xs text-amber-700 mb-2 bg-amber-50 border border-amber-200 rounded px-2 py-1">
                조건이 변경되었습니다. 「통계분석」을 다시 실행하세요.
              </p>
            )}
            {scope && clustersQ.isLoading && <p className="text-sm text-slate-500">불러오는 중…</p>}
            {scope && clustersQ.isError && <p className="text-sm text-red-600">도로 목록을 불러오지 못했습니다.</p>}
            {scope && clustersQ.data && (
              <>
                <p className="text-xs text-slate-500 mb-2">
                  {scope.addr1} {scope.addr2} · 도로 {clustersQ.data.total}개
                </p>
                <div className="card overflow-x-auto p-0">
                  <table className="data buildings-table">
                    <thead>
                      <tr>
                        <th>도로명</th>
                        <th className="text-right">거래</th>
                        <th className="text-right">평균</th>
                        <th className="text-right">중앙</th>
                        <th className="text-right">95% CI</th>
                        <th>구·동</th>
                      </tr>
                    </thead>
                    <tbody>
                      {clustersQ.data.items.map((row) => (
                        <tr
                          key={row.cluster_key}
                          className={clsx(
                            "hover:bg-indigo-50 cursor-pointer",
                            selected?.cluster_key === row.cluster_key && "bg-indigo-50",
                          )}
                          onClick={() => setSelected(row)}
                        >
                          <td className="name">
                            {row.road_name || row.display_label}
                            {!row.is_reliable && <span className="ml-0.5 text-[9px] text-amber-600">n&lt;15</span>}
                          </td>
                          <td className="num">{row.count}</td>
                          <td className="num">{fmtPrice(row.mean)}</td>
                          <td className="num">{fmtPrice(row.median)}</td>
                          <td className="num text-[10px]">{fmtCi(row.ci_lower, row.ci_upper)}</td>
                          <td className="text-[10px] text-slate-600">
                            {[row.addr3, row.addr4].filter(Boolean).join(" · ") || "—"}
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
        <CommercialClusterDetailModal row={selected} scope={scope} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
