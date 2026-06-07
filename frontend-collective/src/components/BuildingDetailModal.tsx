import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  COLLECTIVE_EXPERIMENT_MODE,
  fetchBuildingHistogram,
  fetchBuildingTransactions,
  fetchBuildingYearlyStats,
  type BuildingStatsRow,
} from "../api/client";
import type { AssetType } from "../types";
import { ASSET_LABELS } from "../types";
import BuildingRegressionPanel from "./BuildingRegressionPanel";
import FloorIndexPanel from "./FloorIndexPanel";
import HistogramChart from "./HistogramChart";
import YearlyTrendChart from "./YearlyTrendChart";

const TX_PAGE = 25;

type PanelMode = "trend" | "histogram" | "transactions" | "floor_index" | "regression";

const TABS: { id: PanelMode; label: string | ((assetType: AssetType) => string) }[] = [
  { id: "trend", label: "추세·요약" },
  { id: "histogram", label: "단가 분포" },
  { id: "transactions", label: "거래 목록" },
  { id: "floor_index", label: (t) => (t === "presale" ? "층·권리·면적 효용지수" : "층·동·면적 효용지수") },
  { id: "regression", label: "회귀 분석" },
];

function fmtPrice(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

export default function BuildingDetailModal({
  row,
  assetType,
  yearFrom,
  yearTo,
  onClose,
}: {
  row: BuildingStatsRow;
  assetType: AssetType;
  yearFrom?: number;
  yearTo?: number;
  onClose: () => void;
}) {
  const [panel, setPanel] = useState<PanelMode>("trend");
  const [histScope, setHistScope] = useState<"all" | "single">("all");
  const [histYear, setHistYear] = useState<number | null>(null);
  const [txPage, setTxPage] = useState(1);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const dragSession = useRef<{ startX: number; startY: number; baseX: number; baseY: number } | null>(null);

  const yearQ = useQuery({
    queryKey: ["b-year", row.building_key],
    queryFn: () => fetchBuildingYearlyStats(row.building_key),
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
    queryKey: ["b-hist", row.building_key, histScope, histScope === "single" ? histYear : null],
    queryFn: () =>
      fetchBuildingHistogram(row.building_key, {
        contract_year: histScope === "single" && histYear != null ? histYear : undefined,
      }),
  });

  const txQ = useQuery({
    queryKey: ["b-tx", row.building_key, txPage, yearFrom, yearTo],
    queryFn: () =>
      fetchBuildingTransactions(row.building_key, {
        page: txPage,
        page_size: TX_PAGE,
        contract_year_from: yearFrom,
        contract_year_to: yearTo,
      }),
  });

  useEffect(() => {
    setDragOffset({ x: 0, y: 0 });
    dragSession.current = null;
    setPanel("trend");
    setTxPage(1);
    setHistScope("all");
  }, [row.building_key]);

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

  const analysis = row.analysis ?? {
    floor_index: row.count >= 50,
    regression: row.count >= 30,
    count_total: row.count,
    count_recent: 0,
    messages: [],
  };
  const gateTip =
    analysis.messages.join(" ") ||
    "선택 연도 구간 거래건수가 부족하여 통계 분석을 제공하지 않습니다.";

  const experiment = COLLECTIVE_EXPERIMENT_MODE;

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
              <h2 className="text-sm font-bold text-slate-800">{row.display_name}</h2>
              <p className="text-[11px] text-slate-500 mt-0.5">
                {ASSET_LABELS[assetType]} · n={row.count.toLocaleString("ko-KR")} · 평균 {fmtPrice(row.mean)} 만원/㎡
                {experiment && (
                  <span className="ml-1.5 text-indigo-600 font-medium">· 실험 모드</span>
                )}
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
            {TABS.map(({ id, label }) => {
              const tabLabel = typeof label === "function" ? label(assetType) : label;
              const needsGate = id === "floor_index" || id === "regression";
              const eligible =
                id === "floor_index" ? analysis.floor_index : id === "regression" ? analysis.regression : true;
              const showWarn = needsGate && !eligible && !experiment;
              return (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={panel === id}
                  title={showWarn ? gateTip : undefined}
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
                    {yearFrom != null || yearTo != null ? (
                      <>
                        {" "}
                        · 연도 {yearFrom ?? "…"}–{yearTo ?? "…"}
                      </>
                    ) : (
                      " (전체 연도)"
                    )}
                  </p>
                  <div className="overflow-x-auto rounded-lg border border-slate-100">
                    <table className="w-full text-[11px] border-collapse min-w-[480px]">
                      <thead>
                        <tr className="bg-slate-50 text-slate-600">
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">계약</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">면적(㎡)</th>
                          {assetType === "rowhouse" && (
                            <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">대지(㎡)</th>
                          )}
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">금액(만원)</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-blue-700">단가</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">층</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">
                            {assetType === "presale" ? "권리" : "동"}
                          </th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-800">
                        {txQ.data.items.map((t) => (
                          <tr key={t.id}>
                            <td className="border border-slate-200 px-2 py-1 tabular-nums whitespace-nowrap">
                              {t.contract_year ?? "—"}
                              {t.contract_month ? `.${String(t.contract_month).padStart(2, "0")}` : ""}
                            </td>
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                              {fmtPrice(t.exclusive_area)}
                            </td>
                            {assetType === "rowhouse" && (
                              <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                                {fmtPrice(t.land_area)}
                              </td>
                            )}
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">{fmtPrice(t.price)}</td>
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-blue-600 font-semibold">
                              {fmtPrice(t.unit_price)}
                            </td>
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">{t.floor ?? "—"}</td>
                            <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                              {assetType === "presale" ? (t.housing_subtype ?? "—") : (t.dong ?? "—")}
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

          {panel === "floor_index" && (
            <FloorIndexPanel
              buildingKey={row.building_key}
              assetType={assetType}
              yearFrom={yearFrom}
              yearTo={yearTo}
              experiment={experiment}
              floorIndexEligible={analysis.floor_index}
              gateTip={gateTip}
            />
          )}

          {panel === "regression" && (
            <BuildingRegressionPanel
              buildingKey={row.building_key}
              assetType={assetType}
              yearFrom={yearFrom}
              yearTo={yearTo}
              experiment={experiment}
              regressionEligible={analysis.regression}
              gateTip={gateTip}
            />
          )}
        </div>
      </div>
    </div>
  );
}
