import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  fetchCommercialAddresses,
  fetchCommercialHistogram,
  fetchCommercialTransactions,
  fetchCommercialYearlyStats,
} from "../api/commercialClient";
import {
  COMMERCIAL_ASSET_LABELS,
  type CommercialAssetType,
  type CommercialClusterRow,
} from "../types";
import HistogramChart from "./HistogramChart";
import CommercialFloorIndexPanel from "./CommercialFloorIndexPanel";
import CommercialRegressionPanel from "./CommercialRegressionPanel";
import YearlyTrendChart from "./YearlyTrendChart";

const TX_PAGE = 25;

type PanelMode = "trend" | "histogram" | "transactions" | "addresses" | "floor_index" | "regression";

function fmtPrice(v: number | null | undefined, digits = 1) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function fmtCi(lo: number | null | undefined, hi: number | null | undefined) {
  if (lo == null || hi == null) return "—";
  return `${fmtPrice(lo, 0)}~${fmtPrice(hi, 0)}`;
}

function fmtRoadWidth(t: { road_width_label?: string | null; road_code?: number | null }) {
  if (t.road_width_label) return t.road_width_label;
  if (t.road_code != null) return `${t.road_code}m`;
  return "—";
}

export type CommercialModalScope = {
  assetType: CommercialAssetType;
  addr1: string;
  addr2: string;
  guList: string[];
  leafList: string[];
  hasIntermediate: boolean;
  yearFrom: number | "";
  yearTo: number | "";
};

function regionParams(scope: CommercialModalScope) {
  return scope.hasIntermediate
    ? {
        addr1: scope.addr1,
        addr2: scope.addr2,
        addr3_list: scope.guList.length ? scope.guList : undefined,
        addr4_list: scope.leafList.length ? scope.leafList : undefined,
      }
    : {
        addr1: scope.addr1,
        addr2: scope.addr2,
        addr3_list: scope.leafList.length ? scope.leafList : undefined,
      };
}

function yearParams(scope: CommercialModalScope) {
  return {
    contract_year_from: scope.yearFrom === "" ? undefined : scope.yearFrom,
    contract_year_to: scope.yearTo === "" ? undefined : scope.yearTo,
  };
}

export default function CommercialClusterDetailModal({
  row,
  scope,
  onClose,
}: {
  row: CommercialClusterRow;
  scope: CommercialModalScope;
  onClose: () => void;
}) {
  const [panel, setPanel] = useState<PanelMode>("trend");
  const [histScope, setHistScope] = useState<"all" | "single">("all");
  const [histYear, setHistYear] = useState<number | null>(null);
  const [txPage, setTxPage] = useState(1);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const dragSession = useRef<{ startX: number; startY: number; baseX: number; baseY: number } | null>(null);

  const region = regionParams(scope);
  const years = yearParams(scope);
  const scopeKey = { ...region, ...years };

  const isShop = scope.assetType === "collective_shop";

  const tabs: { id: PanelMode; label: string; shopOnly?: boolean }[] = useMemo(
    () => [
      { id: "trend", label: "추세·요약" },
      { id: "histogram", label: "단가 분포" },
      { id: "transactions", label: "거래 목록" },
      ...(isShop ? [{ id: "addresses" as const, label: "번지별 요약", shopOnly: true }] : []),
      { id: "floor_index", label: "층·면적 효용지수" },
      { id: "regression", label: "회귀 분석" },
    ],
    [isShop],
  );

  const yearQ = useQuery({
    queryKey: ["comm-year", row.cluster_key, scopeKey],
    queryFn: () => fetchCommercialYearlyStats(row.cluster_key, { ...region, ...years }),
  });

  const sortedYears = useMemo(
    () => [...(yearQ.data?.points ?? [])].sort((a, b) => a.year - b.year),
    [yearQ.data?.points],
  );

  useEffect(() => {
    if (sortedYears.length && histYear == null) {
      setHistYear(sortedYears[sortedYears.length - 1].year);
    }
  }, [sortedYears, histYear]);

  const histQ = useQuery({
    queryKey: ["comm-hist", row.cluster_key, scopeKey, histScope, histScope === "single" ? histYear : null],
    queryFn: () =>
      fetchCommercialHistogram(row.cluster_key, {
        ...region,
        ...years,
        contract_year: histScope === "single" && histYear != null ? histYear : undefined,
      }),
  });

  const txQ = useQuery({
    queryKey: ["comm-tx-modal", row.cluster_key, scopeKey, txPage],
    queryFn: () =>
      fetchCommercialTransactions(row.cluster_key, {
        ...region,
        ...years,
        page: txPage,
        page_size: TX_PAGE,
      }),
  });

  const addrQ = useQuery({
    queryKey: ["comm-addr-modal", row.cluster_key, scopeKey],
    queryFn: () => fetchCommercialAddresses(row.cluster_key, { ...region, ...years }),
    enabled: isShop && panel === "addresses",
  });

  useEffect(() => {
    setDragOffset({ x: 0, y: 0 });
    dragSession.current = null;
    setPanel("trend");
    setTxPage(1);
    setHistScope("all");
    setHistYear(null);
  }, [row.cluster_key]);

  const onDragMove = (e: MouseEvent) => {
    const s = dragSession.current;
    if (!s) return;
    setDragOffset({ x: s.baseX + (e.clientX - s.startX), y: s.baseY + (e.clientY - s.startY) });
  };

  const onDragEnd = () => {
    dragSession.current = null;
    window.removeEventListener("mousemove", onDragMove);
    window.removeEventListener("mouseup", onDragEnd);
  };

  const onHeaderMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest("button")) return;
    dragSession.current = { startX: e.clientX, startY: e.clientY, baseX: dragOffset.x, baseY: dragOffset.y };
    window.addEventListener("mousemove", onDragMove);
    window.addEventListener("mouseup", onDragEnd);
  };

  const txOffset = (txPage - 1) * TX_PAGE;
  const label = row.road_name || row.display_label;

  return (
    <div
      className="fixed inset-0 z-[100] bg-black/35"
      role="dialog"
      aria-modal="true"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="fixed left-1/2 top-1/2 bg-white rounded-xl shadow-xl max-w-4xl w-[calc(100%-2rem)] max-h-[85vh] flex flex-col border border-slate-200"
        style={{ transform: `translate(calc(-50% + ${dragOffset.x}px), calc(-50% + ${dragOffset.y}px))` }}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div
          className="px-4 py-3 border-b border-slate-100 cursor-move select-none shrink-0"
          onMouseDown={onHeaderMouseDown}
        >
          <div className="flex justify-between items-start gap-2">
            <div className="min-w-0 flex-1">
              <h2 className="text-sm font-bold text-slate-800">{label}</h2>
              <p className="text-[11px] text-slate-500 mt-0.5">
                {COMMERCIAL_ASSET_LABELS[scope.assetType]} · n={row.count.toLocaleString("ko-KR")} · 평균{" "}
                {fmtPrice(row.mean, 0)} 만원/㎡
                {[row.addr3, row.addr4].filter(Boolean).length > 0 && (
                  <> · {[row.addr3, row.addr4].filter(Boolean).join(" ")}</>
                )}
                {!row.is_reliable && <span className="ml-1 text-amber-600">· n&lt;15</span>}
              </p>
            </div>
            <button
              type="button"
              aria-label="닫기"
              className="text-slate-400 hover:text-slate-700 text-xl leading-none px-1 shrink-0"
              onClick={onClose}
            >
              ×
            </button>
          </div>
          <div
            className="mt-2 flex flex-wrap gap-0.5 rounded-md border border-slate-200 bg-slate-50 p-0.5"
            role="tablist"
          >
            {tabs.map(({ id, label: tabLabel }) => {
              const showWarn =
                (id === "regression" && row.count < 30) || (id === "floor_index" && row.count < 50);
              return (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={panel === id}
                  title={
                    showWarn
                      ? id === "floor_index"
                        ? "표본 50건 미만 — 참고용 조회 가능"
                        : "표본 30건 미만 — 참고용 실행 가능"
                      : undefined
                  }
                  className={clsx(
                    "px-2 py-1 text-[11px] font-medium rounded transition-colors whitespace-nowrap",
                    panel === id
                      ? "bg-white text-slate-800 shadow-sm border border-slate-100"
                      : "text-slate-500 hover:text-slate-700",
                    showWarn && panel !== id && "text-amber-700",
                  )}
                  onClick={() => setPanel(id)}
                >
                  {tabLabel}
                  {showWarn && <span className="ml-0.5 text-[9px]">*</span>}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex-1 overflow-auto px-4 py-3 space-y-4">
          {panel === "trend" && (
            <>
              {yearQ.isLoading && <p className="text-xs text-slate-400 text-center py-6">연도별 집계 중…</p>}
              {!yearQ.isLoading && sortedYears.length === 0 && (
                <p className="text-xs text-slate-400 text-center py-6">표시할 연도별 데이터가 없습니다.</p>
              )}
              {sortedYears.length > 0 && (
                <>
                  <div className="rounded-lg border border-slate-100 bg-slate-50/60 px-2 py-3">
                    <p className="text-[10px] font-semibold text-slate-600 px-1 mb-2">추이 (꺾은선)</p>
                    <YearlyTrendChart points={sortedYears} />
                  </div>
                  <div className="rounded-lg border border-slate-100 bg-white overflow-hidden">
                    <p className="text-[10px] font-semibold text-slate-600 px-3 pt-3 pb-1">연도별 수치</p>
                    <table className="w-full text-xs border-collapse">
                      <thead>
                        <tr className="bg-slate-50 text-slate-600">
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">연도</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">건수</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-blue-700">
                            평균(만원/㎡)
                          </th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-800">
                        {sortedYears.map((p) => (
                          <tr key={p.year}>
                            <td className="border border-slate-200 px-2 py-1 tabular-nums">{p.year}</td>
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                              {p.count.toLocaleString("ko-KR")}
                            </td>
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-blue-600 font-bold">
                              {p.mean != null ? fmtPrice(p.mean) : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </>
          )}

          {panel === "histogram" && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-[11px]">
                <span className="text-slate-500">표본 범위</span>
                <select
                  value={histScope}
                  onChange={(e) => setHistScope(e.target.value === "single" ? "single" : "all")}
                  className="border border-slate-200 rounded px-2 py-1 bg-white text-slate-800"
                >
                  <option value="all">전체 연도</option>
                  <option value="single">특정 연도만</option>
                </select>
                {histScope === "single" && (
                  <select
                    value={histYear ?? ""}
                    onChange={(e) => setHistYear(Number(e.target.value))}
                    className="border border-slate-200 rounded px-2 py-1 bg-white text-slate-800"
                  >
                    {sortedYears.map((p) => (
                      <option key={p.year} value={p.year}>
                        {p.year} ({p.count.toLocaleString("ko-KR")}건)
                      </option>
                    ))}
                  </select>
                )}
              </div>
              {histQ.isLoading && <p className="text-xs text-slate-400 text-center py-4">분포 계산 중…</p>}
              {histQ.isError && <p className="text-xs text-red-500 text-center py-4">분포를 불러오지 못했습니다.</p>}
              {histQ.data && (
                <>
                  <p className="text-[10px] text-slate-500">
                    표본 수 <strong className="text-slate-700">{histQ.data.n.toLocaleString("ko-KR")}</strong>건
                    {histScope === "single" && histYear != null && (
                      <>
                        {" "}
                        · 대상 연도 <strong className="text-slate-700">{histYear}</strong>
                      </>
                    )}
                  </p>
                  <div className="rounded-lg border border-slate-100 bg-slate-50/60 px-2 py-2">
                    <HistogramChart bins={histQ.data.bins} />
                  </div>
                </>
              )}
            </div>
          )}

          {panel === "transactions" && (
            <div className="space-y-2">
              {txQ.isLoading && <p className="text-xs text-slate-400 text-center py-4">목록 불러오는 중…</p>}
              {txQ.isError && <p className="text-xs text-red-500 text-center py-4">목록을 불러오지 못했습니다.</p>}
              {txQ.data && (
                <>
                  <p className="text-[10px] text-slate-500">
                    전체 <strong className="text-slate-700">{txQ.data.total.toLocaleString("ko-KR")}</strong>건
                    {(scope.yearFrom !== "" || scope.yearTo !== "") && (
                      <>
                        {" "}
                        · 연도 {scope.yearFrom || "…"}–{scope.yearTo || "…"}
                      </>
                    )}
                  </p>
                  <div className="overflow-x-auto rounded-lg border border-slate-100">
                    <table className="w-full text-[11px] border-collapse min-w-[720px]">
                      <thead>
                        <tr className="bg-slate-50 text-slate-600">
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">계약</th>
                          {isShop && (
                            <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">번지</th>
                          )}
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">동</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">용도지역</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">건축물용도</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">도로폭</th>
                          {!isShop && (
                            <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">면적구간</th>
                          )}
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">연면적(㎡)</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">층</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">준공</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">금액(만원)</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-blue-700">단가</th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-800">
                        {txQ.data.items.map((t) => (
                          <tr key={t.id}>
                            <td className="border border-slate-200 px-2 py-1 tabular-nums whitespace-nowrap">
                              {t.contract_year ?? "—"}
                              {t.contract_month ? `.${String(t.contract_month).padStart(2, "0")}` : ""}
                            </td>
                            {isShop && (
                              <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                                {t.lot_number ?? "—"}
                              </td>
                            )}
                            <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                              {[t.addr3, t.addr4].filter(Boolean).join(" · ") || "—"}
                            </td>
                            <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">{t.zone_type ?? "—"}</td>
                            <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">{t.building_use ?? "—"}</td>
                            <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">{fmtRoadWidth(t)}</td>
                            {!isShop && (
                              <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                                {t.area_bucket_label ?? "—"}
                              </td>
                            )}
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                              {fmtPrice(t.gross_area)}
                            </td>
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                              {t.floor != null ? (Number.isInteger(t.floor) ? t.floor : t.floor.toFixed(1)) : "—"}
                            </td>
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                              {t.building_year ?? "—"}
                            </td>
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                              {fmtPrice(t.price, 0)}
                            </td>
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-blue-600 font-semibold">
                              {fmtPrice(t.unit_price)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
                    <span className="text-slate-400">
                      {txQ.data.total > 0
                        ? `${(txOffset + 1).toLocaleString("ko-KR")}–${Math.min(txOffset + txQ.data.items.length, txQ.data.total).toLocaleString("ko-KR")} / ${txQ.data.total.toLocaleString("ko-KR")}`
                        : "0건"}
                    </span>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        disabled={txPage <= 1}
                        onClick={() => setTxPage((p) => Math.max(1, p - 1))}
                        className="px-2 py-1 rounded border border-slate-200 text-slate-600 disabled:opacity-40 hover:bg-slate-50"
                      >
                        이전
                      </button>
                      <button
                        type="button"
                        disabled={txOffset + TX_PAGE >= txQ.data.total}
                        onClick={() => setTxPage((p) => p + 1)}
                        className="px-2 py-1 rounded border border-slate-200 text-slate-600 disabled:opacity-40 hover:bg-slate-50"
                      >
                        다음
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {panel === "addresses" && isShop && (
            <div className="space-y-2">
              {addrQ.isLoading && <p className="text-xs text-slate-400 text-center py-4">번지별 집계 중…</p>}
              {addrQ.isError && <p className="text-xs text-red-500 text-center py-4">번지별 데이터를 불러오지 못했습니다.</p>}
              {addrQ.data && (
                <>
                  <p className="text-[10px] text-slate-500">
                    번지·동 조합 <strong className="text-slate-700">{addrQ.data.total.toLocaleString("ko-KR")}</strong>
                    개 · 23년 이전 데이터는 번지·동 정보가 불명확할 수 있습니다.
                  </p>
                  <div className="overflow-x-auto rounded-lg border border-slate-100">
                    <table className="w-full text-[11px] border-collapse min-w-[480px]">
                      <thead>
                        <tr className="bg-slate-50 text-slate-600">
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">번지</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">동</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">거래</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">평균</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">중앙</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">95% CI</th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-800">
                        {addrQ.data.items.map((a) => (
                          <tr key={`${a.lot_number}|${a.addr4 ?? ""}`}>
                            <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">{a.lot_number}</td>
                            <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                              {[a.addr3, a.addr4].filter(Boolean).join(" · ") || "—"}
                            </td>
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">{a.count}</td>
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                              {fmtPrice(a.mean, 0)}
                            </td>
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                              {fmtPrice(a.median, 0)}
                            </td>
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-[10px]">
                              {fmtCi(a.ci_lower, a.ci_upper)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          )}

          {panel === "floor_index" && (
            <CommercialFloorIndexPanel
              clusterKey={row.cluster_key}
              scope={scope}
              count={row.count}
              isFactory={!isShop}
            />
          )}

          {panel === "regression" && (
            <CommercialRegressionPanel
              clusterKey={row.cluster_key}
              scope={scope}
              isShop={isShop}
              count={row.count}
            />
          )}
        </div>
      </div>
    </div>
  );
}
