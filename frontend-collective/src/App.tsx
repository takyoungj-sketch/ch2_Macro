import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  fetchAddr2,
  fetchAddr3,
  fetchBuildingHistogram,
  fetchBuildingTransactions,
  fetchBuildingYearlyStats,
  fetchBuildings,
  fetchFilterMeta,
  runBuildingRegression,
  type BuildingStatsRow,
} from "./api/client";
import type { AssetType, CollectiveRegressionResponse } from "./types";
import { ASSET_LABELS } from "./types";

function fmtPrice(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function fmtCi(lo: number | null | undefined, hi: number | null | undefined) {
  if (lo == null || hi == null) return "—";
  return `${fmtPrice(lo)} ~ ${fmtPrice(hi)}`;
}

function BuildingModal({
  row,
  assetType,
  yearFrom,
  yearTo,
  onClose,
}: {
  row: BuildingStatsRow;
  assetType: AssetType;
  yearFrom: number | "";
  yearTo: number | "";
  onClose: () => void;
}) {
  const yearParams = useMemo(
    () => ({
      contract_year_from: yearFrom === "" ? undefined : yearFrom,
      contract_year_to: yearTo === "" ? undefined : yearTo,
    }),
    [yearFrom, yearTo],
  );

  const txQ = useQuery({
    queryKey: ["b-tx", row.building_key, yearParams],
    queryFn: () => fetchBuildingTransactions(row.building_key, { ...yearParams, page: 1 }),
  });
  const yearQ = useQuery({
    queryKey: ["b-year", row.building_key],
    queryFn: () => fetchBuildingYearlyStats(row.building_key),
  });
  const histQ = useQuery({
    queryKey: ["b-hist", row.building_key],
    queryFn: () => fetchBuildingHistogram(row.building_key),
  });
  const regM = useMutation({
    mutationFn: () =>
      runBuildingRegression(row.building_key, {
        asset_type: assetType,
        ...yearParams,
        exclude_outliers_iqr: false,
      }),
  });

  const maxHist = Math.max(...(histQ.data?.bins.map((b) => b.count) ?? [1]), 1);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="card max-h-[90vh] w-full max-w-4xl overflow-y-auto p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <h2 className="text-lg font-semibold">{row.display_name}</h2>
            <p className="text-xs text-slate-500">
              {ASSET_LABELS[assetType]} · n={row.count} · 평균 {fmtPrice(row.mean)} 만원/㎡
            </p>
          </div>
          <button type="button" className="text-slate-500 hover:text-slate-800" onClick={onClose}>
            ✕
          </button>
        </div>

        <section className="mb-6">
          <h3 className="text-sm font-semibold mb-2">연도별 평균 단가</h3>
          {yearQ.isLoading && <p className="text-xs text-slate-500">불러오는 중…</p>}
          {yearQ.data && yearQ.data.points.length === 0 && (
            <p className="text-xs text-slate-500">데이터 없음</p>
          )}
          <div className="space-y-1">
            {(yearQ.data?.points ?? []).map((p) => (
              <div key={p.year} className="flex items-center gap-2 text-xs">
                <span className="w-10 shrink-0">{p.year}</span>
                <div className="flex-1 h-3 bg-slate-100 rounded overflow-hidden">
                  <div
                    className="h-full bg-indigo-500"
                    style={{
                      width: `${Math.min(100, ((p.mean ?? 0) / (row.mean || 1)) * 60)}%`,
                    }}
                  />
                </div>
                <span className="w-24 text-right">{fmtPrice(p.mean)}</span>
                <span className="text-slate-400">({p.count}건)</span>
              </div>
            ))}
          </div>
        </section>

        <section className="mb-6">
          <h3 className="text-sm font-semibold mb-2">단가 분포</h3>
          <div className="flex items-end gap-1 h-24">
            {(histQ.data?.bins ?? []).map((b, i) => (
              <div key={i} className="flex-1 flex flex-col items-center justify-end h-full">
                <div
                  className="w-full bg-sky-500 rounded-t"
                  style={{ height: `${(b.count / maxHist) * 100}%`, minHeight: b.count ? 4 : 0 }}
                  title={`${b.lo}–${b.hi}: ${b.count}건`}
                />
              </div>
            ))}
          </div>
        </section>

        <section className="mb-6">
          <h3 className="text-sm font-semibold mb-2">거래 목록</h3>
          <div className="overflow-x-auto max-h-48">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-slate-500 border-b">
                  <th className="py-1 pr-2">연월</th>
                  <th className="py-1 pr-2">면적</th>
                  <th className="py-1 pr-2">금액</th>
                  <th className="py-1 pr-2">단가</th>
                  <th className="py-1 pr-2">층</th>
                  <th className="py-1">동</th>
                </tr>
              </thead>
              <tbody>
                {(txQ.data?.items ?? []).map((t) => (
                  <tr key={t.id} className="border-b border-slate-100">
                    <td className="py-1 pr-2">
                      {t.contract_year}
                      {t.contract_month ? `.${String(t.contract_month).padStart(2, "0")}` : ""}
                    </td>
                    <td className="py-1 pr-2">{fmtPrice(t.exclusive_area)}</td>
                    <td className="py-1 pr-2">{fmtPrice(t.price)}</td>
                    <td className="py-1 pr-2">{fmtPrice(t.unit_price)}</td>
                    <td className="py-1 pr-2">{t.floor ?? "—"}</td>
                    <td className="py-1">{t.dong ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold">회귀 (금액 ~ 전용면적·연식·층·동)</h3>
            <button
              type="button"
              className="text-xs px-2 py-1 rounded bg-slate-800 text-white"
              disabled={regM.isPending}
              onClick={() => regM.mutate()}
            >
              {regM.isPending ? "실행 중…" : "회귀 실행"}
            </button>
          </div>
          {regM.data && <RegressionPanel data={regM.data} />}
          {regM.isError && <p className="text-xs text-red-600">회귀 실패</p>}
        </section>
      </div>
    </div>
  );
}

function RegressionPanel({ data }: { data: CollectiveRegressionResponse }) {
  return (
    <div className="text-xs space-y-2">
      {data.warnings.map((w) => (
        <p key={w} className="text-amber-700">
          {w}
        </p>
      ))}
      <p>
        n={data.n}, R²={data.r_squared?.toFixed(3) ?? "—"}, adj R²=
        {data.adj_r_squared?.toFixed(3) ?? "—"}
      </p>
      <table className="w-full">
        <thead>
          <tr className="text-slate-500 border-b">
            <th className="text-left py-1">변수</th>
            <th className="text-right py-1">계수</th>
            <th className="text-right py-1">SE</th>
            <th className="text-right py-1">t</th>
            <th className="text-right py-1">p</th>
          </tr>
        </thead>
        <tbody>
          {data.coefficients.map((c) => (
            <tr key={c.name} className="border-b border-slate-100">
              <td className="py-1">{c.label}</td>
              <td className="text-right py-1">{c.coef.toFixed(2)}</td>
              <td className="text-right py-1">{c.se?.toFixed(2) ?? "—"}</td>
              <td className="text-right py-1">{c.t?.toFixed(2) ?? "—"}</td>
              <td className="text-right py-1">{c.p?.toFixed(3) ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function App() {
  const [assetType, setAssetType] = useState<AssetType>("apartment");
  const [addr1, setAddr1] = useState("");
  const [addr2, setAddr2] = useState("");
  const [addr3, setAddr3] = useState("");
  const [yearFrom, setYearFrom] = useState<number | "">("");
  const [yearTo, setYearTo] = useState<number | "">("");
  const [sort, setSort] = useState("count");
  const [selected, setSelected] = useState<BuildingStatsRow | null>(null);

  const metaQ = useQuery({ queryKey: ["coll-meta"], queryFn: fetchFilterMeta });
  const addr2Q = useQuery({
    queryKey: ["coll-addr2", addr1],
    queryFn: () => fetchAddr2(addr1),
    enabled: !!addr1,
  });
  const addr3Q = useQuery({
    queryKey: ["coll-addr3", addr1, addr2, assetType],
    queryFn: () => fetchAddr3(addr1, addr2, assetType),
    enabled: !!addr1 && !!addr2,
  });

  const buildingsQ = useQuery({
    queryKey: ["coll-buildings", assetType, addr1, addr2, addr3, yearFrom, yearTo, sort],
    queryFn: () =>
      fetchBuildings({
        asset_type: assetType,
        addr1: addr1 || undefined,
        addr2: addr2 || undefined,
        addr3: addr3 || undefined,
        contract_year_from: yearFrom === "" ? undefined : yearFrom,
        contract_year_to: yearTo === "" ? undefined : yearTo,
        sort,
        page_size: 500,
      }),
    enabled: !!addr2,
  });

  const years = metaQ.data?.contract_years ?? [];

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
        <aside className="w-72 shrink-0 border-r border-slate-200 bg-white p-4 overflow-y-auto">
          <h2 className="text-sm font-semibold mb-3">유형 · 지역</h2>
          <div className="space-y-3">
            <label className="text-xs block space-y-1">
              <span className="text-slate-500">유형</span>
              <select
                className="input"
                value={assetType}
                onChange={(e) => setAssetType(e.target.value as AssetType)}
              >
                {(Object.keys(ASSET_LABELS) as AssetType[]).map((t) => (
                  <option key={t} value={t}>
                    {ASSET_LABELS[t]}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs block space-y-1">
              <span className="text-slate-500">시도</span>
              <select
                className="input"
                value={addr1}
                onChange={(e) => {
                  setAddr1(e.target.value);
                  setAddr2("");
                  setAddr3("");
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
                  setAddr3("");
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
            <label className="text-xs block space-y-1">
              <span className="text-slate-500">읍·면·동 (선택)</span>
              <select className="input" value={addr3} disabled={!addr2} onChange={(e) => setAddr3(e.target.value)}>
                <option value="">전체</option>
                {(addr3Q.data ?? []).map((a) => (
                  <option key={a.name} value={a.name}>
                    {a.name} ({a.count})
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
              <span className="text-slate-500">정렬</span>
              <select className="input" value={sort} onChange={(e) => setSort(e.target.value)}>
                <option value="count">거래수</option>
                <option value="mean">평균 단가</option>
                <option value="display_name">건물명</option>
              </select>
            </label>
          </div>
        </aside>

        <div className="flex-1 p-4 overflow-auto">
          {!addr2 && (
            <p className="text-sm text-slate-500">시도·시군구를 선택하면 건물 목록이 표시됩니다.</p>
          )}
          {addr2 && buildingsQ.isLoading && <p className="text-sm text-slate-500">불러오는 중…</p>}
          {addr2 && buildingsQ.isError && (
            <p className="text-sm text-red-600">건물 목록을 불러오지 못했습니다.</p>
          )}
          {buildingsQ.data && (
            <>
              <p className="text-xs text-slate-500 mb-2">건물 {buildingsQ.data.total}개</p>
              <div className="card overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-slate-500 border-b bg-slate-50">
                      <th className="px-3 py-2">건물명</th>
                      <th className="px-3 py-2 text-right">거래수</th>
                      <th className="px-3 py-2 text-right">평균(만원/㎡)</th>
                      <th className="px-3 py-2 text-right">중앙값</th>
                      <th className="px-3 py-2 text-right">95% CI</th>
                    </tr>
                  </thead>
                  <tbody>
                    {buildingsQ.data.items.map((row) => (
                      <tr
                        key={row.building_key}
                        className="border-b border-slate-100 hover:bg-indigo-50 cursor-pointer"
                        onClick={() => setSelected(row)}
                      >
                        <td className="px-3 py-2">
                          {row.display_name}
                          {!row.is_reliable && (
                            <span className="ml-1 text-[10px] text-amber-600">n&lt;15</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right">{row.count}</td>
                        <td className="px-3 py-2 text-right">{fmtPrice(row.mean)}</td>
                        <td className="px-3 py-2 text-right">{fmtPrice(row.median)}</td>
                        <td className="px-3 py-2 text-right text-xs">{fmtCi(row.ci_lower, row.ci_upper)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </main>

      {selected && (
        <BuildingModal
          row={selected}
          assetType={assetType}
          yearFrom={yearFrom}
          yearTo={yearTo}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
