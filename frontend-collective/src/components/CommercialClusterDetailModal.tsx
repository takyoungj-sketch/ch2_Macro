import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  downloadCommercialCohortTransactionsCsv,
  downloadCommercialTransactionsCsv,
  fetchCommercialAddresses,
  fetchCommercialCohortHistogram,
  fetchCommercialCohortTransactions,
  fetchCommercialHistogram,
  fetchCommercialRollingStats,
  fetchCommercialTransactions,
  fetchCommercialYearlyStats,
} from "../api/commercialClient";
import {
  commercialAssetTypeLabel,
  type CommercialAssetSelectorType,
  type CommercialAssetType,
  type CommercialClusterRow,
  type CommercialTransactionRow,
} from "../types";
import { buildAnalysisPeriodParams, formatPeriodLabel, type AnalysisPeriodParams } from "../utils/analysisPeriod";
import { commercialRollingToTrendSeries, commercialYearlyResponseToTrendSeries } from "../utils/cohortTrendSeries";
import CohortTrendPanel from "./CohortTrendPanel";
import HistogramChart from "./HistogramChart";
import CommercialFloorIndexPanel from "./CommercialFloorIndexPanel";
import CommercialRegressionPanel from "./CommercialRegressionPanel";
import RollingTrendChart from "./RollingTrendChart";
import YearlyTrendChart from "./YearlyTrendChart";
import type { CohortTrendMetric } from "./MultiBuildingTrendChart";

const TX_PAGE = 25;
const MAX_COHORT_CLUSTERS = 10;

type PanelMode = "trend" | "long_term" | "histogram" | "transactions" | "addresses" | "floor_index" | "regression";

function fmtPrice(v: number | null | undefined, digits = 1) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function fmtCi(lo: number | null | undefined, hi: number | null | undefined) {
  if (lo == null || hi == null) return "—";
  return `${fmtPrice(lo, 0)}~${fmtPrice(hi, 0)}`;
}

function fmtContractDate(t: CommercialTransactionRow) {
  if (t.contract_date) return t.contract_date;
  if (t.contract_year == null) return "—";
  if (t.contract_month) return `${t.contract_year}-${String(t.contract_month).padStart(2, "0")}-01`;
  return String(t.contract_year);
}

function fmtRoadWidth(t: { road_width_label?: string | null; road_code?: number | null }) {
  if (t.road_width_label) return t.road_width_label;
  if (t.road_code != null) return `${t.road_code}m`;
  return "—";
}

function fmtDong(t: CommercialTransactionRow) {
  const parts = [t.addr3, t.addr4].filter(Boolean);
  return parts.length ? parts.join(" ") : "—";
}

function CommercialTransactionTable({
  items,
  showCluster = false,
}: {
  items: CommercialTransactionRow[];
  showCluster?: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-100">
      <table className="w-full text-[11px] border-collapse min-w-[960px]">
        <thead>
          <tr className="bg-slate-50 text-slate-600">
            {showCluster && (
              <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">도로</th>
            )}
            <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">계약일</th>
            <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">동</th>
            <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">번지</th>
            <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">용도지역</th>
            <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">도로폭</th>
            <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">건축물용도</th>
            <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">준공</th>
            <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">층</th>
            <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">연면적(㎡)</th>
            <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">금액(만원)</th>
            <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-blue-700">단가</th>
            <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">매수</th>
            <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">매도</th>
          </tr>
        </thead>
        <tbody className="text-slate-800">
          {items.map((t) => (
            <tr key={t.id}>
              {showCluster && (
                <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">{t.road_name ?? "—"}</td>
              )}
              <td className="border border-slate-200 px-2 py-1 tabular-nums whitespace-nowrap">
                {fmtContractDate(t)}
              </td>
              <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">{fmtDong(t)}</td>
              <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">{t.lot_number ?? "—"}</td>
              <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">{t.zone_type ?? "—"}</td>
              <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">{fmtRoadWidth(t)}</td>
              <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">{t.building_use ?? "—"}</td>
              <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">{t.building_year ?? "—"}</td>
              <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                {t.floor != null ? (Number.isInteger(t.floor) ? t.floor : t.floor.toFixed(1)) : "—"}
              </td>
              <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">{fmtPrice(t.gross_area)}</td>
              <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">{fmtPrice(t.price, 0)}</td>
              <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-blue-600 font-semibold">
                {fmtPrice(t.unit_price)}
              </td>
              <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">{t.buyer_type ?? "—"}</td>
              <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">{t.seller_type ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CommercialTransactionPager({
  total,
  offset,
  pageSize,
  onPrev,
  onNext,
}: {
  total: number;
  offset: number;
  pageSize: number;
  onPrev: () => void;
  onNext: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
      <span className="text-slate-400">
        {total > 0
          ? `${(offset + 1).toLocaleString("ko-KR")}–${Math.min(offset + pageSize, total).toLocaleString("ko-KR")} / ${total.toLocaleString("ko-KR")}`
          : "0건"}
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={offset <= 0}
          onClick={onPrev}
          className="px-2 py-1 rounded border border-slate-200 text-slate-600 disabled:opacity-40 hover:bg-slate-50"
        >
          이전
        </button>
        <button
          type="button"
          disabled={offset + pageSize >= total}
          onClick={onNext}
          className="px-2 py-1 rounded border border-slate-200 text-slate-600 disabled:opacity-40 hover:bg-slate-50"
        >
          다음
        </button>
      </div>
    </div>
  );
}

export type CommercialModalScope = {
  assetType: CommercialAssetSelectorType;
  addr1: string;
  addr2: string;
  guList: string[];
  leafList: string[];
  hasIntermediate: boolean;
  yearFrom: number | "";
  yearTo: number | "";
  windowYears: number;
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

export default function CommercialClusterDetailModal({
  row,
  scope,
  periodStart,
  periodEnd,
  statsAsOfLabel,
  peerClusters = [],
  onClose,
}: {
  row: CommercialClusterRow;
  scope: CommercialModalScope;
  periodStart?: string | null;
  periodEnd?: string | null;
  statsAsOfLabel?: string | null;
  peerClusters?: CommercialClusterRow[];
  onClose: () => void;
}) {
  const [panel, setPanel] = useState<PanelMode>("trend");
  const [histScope, setHistScope] = useState<"all" | "single">("all");
  const [histYear, setHistYear] = useState<number | null>(null);
  const [txPage, setTxPage] = useState(1);
  const [txExportLoading, setTxExportLoading] = useState(false);
  const [txExportError, setTxExportError] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const dragSession = useRef<{ startX: number; startY: number; baseX: number; baseY: number } | null>(null);
  const [cohortExtra, setCohortExtra] = useState<string[]>([]);
  const [cohortRunKeys, setCohortRunKeys] = useState<string[]>([]);
  const [cohortRunByPanel, setCohortRunByPanel] = useState<Partial<Record<PanelMode, number>>>({});
  const [cohortChartMetric, setCohortChartMetric] = useState<CohortTrendMetric>("mean");

  const effectiveAssetType = (scope.assetType === "all" ? row.asset_type : scope.assetType) as CommercialAssetType;

  const cohortKeys = useMemo(
    () => [row.cluster_key, ...cohortExtra.filter((k) => k !== row.cluster_key)].slice(0, MAX_COHORT_CLUSTERS),
    [row.cluster_key, cohortExtra],
  );
  const cohortStale =
    Object.keys(cohortRunByPanel).length > 0 &&
    (cohortRunKeys.length !== cohortKeys.length || cohortRunKeys.some((k, i) => k !== cohortKeys[i]));
  const canRunCohort = cohortKeys.length > 1;
  const cohortRunForPanel = (p: PanelMode) => (cohortStale ? 0 : cohortRunByPanel[p] ?? 0);

  const region = regionParams(scope);
  const analysisPeriod: AnalysisPeriodParams = useMemo(
    () =>
      buildAnalysisPeriodParams(
        scope.yearFrom === "" ? undefined : scope.yearFrom,
        scope.yearTo === "" ? undefined : scope.yearTo,
        periodStart,
        periodEnd,
      ),
    [scope.yearFrom, scope.yearTo, periodStart, periodEnd],
  );
  const periodLabel = formatPeriodLabel(periodStart, periodEnd);
  const usesMartPeriod = Boolean(analysisPeriod.contract_date_from && analysisPeriod.contract_date_to);
  const scopeKey = { ...region, ...analysisPeriod };

  const cohortBody = useMemo(
    () => ({
      cluster_keys: cohortRunKeys,
      asset_type: scope.assetType === "all" ? undefined : effectiveAssetType,
      ...region,
      ...analysisPeriod,
    }),
    [cohortRunKeys, scope.assetType, effectiveAssetType, region, analysisPeriod],
  );

  const isShop = effectiveAssetType === "collective_shop";

  const tabs: { id: PanelMode; label: string; shopOnly?: boolean }[] = useMemo(
    () => [
      { id: "trend", label: "추세·요약" },
      { id: "histogram", label: "단가 분포" },
      { id: "transactions", label: "거래 목록" },
      ...(isShop ? [{ id: "addresses" as const, label: "번지별 요약", shopOnly: true }] : []),
      { id: "floor_index", label: "층·면적 효용지수" },
      { id: "regression", label: "회귀 분석" },
      { id: "long_term", label: "장기 추세" },
    ],
    [isShop],
  );

  const yearQ = useQuery({
    queryKey: ["comm-year", row.cluster_key, scopeKey],
    queryFn: () => fetchCommercialYearlyStats(row.cluster_key, { ...region, ...analysisPeriod }),
    enabled: panel === "histogram" && histScope === "single",
  });

  const longTermYearQ = useQuery({
    queryKey: ["comm-year-long", row.cluster_key],
    queryFn: () => fetchCommercialYearlyStats(row.cluster_key),
    enabled: cohortRunForPanel("long_term") === 0 && panel === "long_term",
  });

  const longTermYears = useMemo(
    () => [...(longTermYearQ.data?.points ?? [])].sort((a, b) => a.year - b.year),
    [longTermYearQ.data?.points],
  );

  const rollingQ = useQuery({
    queryKey: ["comm-rolling", row.cluster_key, scope.windowYears],
    queryFn: () =>
      fetchCommercialRollingStats(row.cluster_key, { window_years: scope.windowYears }),
    enabled:
      cohortRunForPanel("trend") === 0 &&
      panel === "trend" &&
      scope.yearFrom === "" &&
      scope.yearTo === "",
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
        ...analysisPeriod,
        contract_year: histScope === "single" && histYear != null ? histYear : undefined,
      }),
    enabled: cohortRunForPanel("histogram") === 0,
  });

  const txQ = useQuery({
    queryKey: ["comm-tx-modal", row.cluster_key, scopeKey, txPage],
    queryFn: () =>
      fetchCommercialTransactions(row.cluster_key, {
        ...region,
        ...analysisPeriod,
        page: txPage,
        page_size: TX_PAGE,
      }),
    enabled: cohortRunForPanel("transactions") === 0,
  });

  const addrQ = useQuery({
    queryKey: ["comm-addr-modal", row.cluster_key, scopeKey],
    queryFn: () => fetchCommercialAddresses(row.cluster_key, { ...region, ...analysisPeriod }),
    enabled: isShop && panel === "addresses",
  });

  const peerOptions = useMemo(
    () =>
      peerClusters.filter(
        (p) => p.cluster_key !== row.cluster_key && !cohortExtra.includes(p.cluster_key),
      ),
    [peerClusters, row.cluster_key, cohortExtra],
  );

  const analysisCount = useMemo(() => {
    const keys = cohortRunKeys.length > 1 ? cohortRunKeys : [row.cluster_key];
    return keys.reduce((sum, k) => {
      if (k === row.cluster_key) return sum + row.count;
      const hit = peerClusters.find((p) => p.cluster_key === k);
      return sum + (hit?.count ?? 0);
    }, 0);
  }, [cohortRunKeys, row.cluster_key, row.count, peerClusters]);

  const cohortRollingQ = useQuery({
    queryKey: ["comm-cohort-rolling", cohortRunKeys, scope.windowYears, cohortRunForPanel("trend")],
    queryFn: async () =>
      Promise.all(
        cohortRunKeys.map((k) =>
          fetchCommercialRollingStats(k, { window_years: scope.windowYears }),
        ),
      ),
    enabled:
      cohortRunForPanel("trend") > 0 &&
      cohortRunKeys.length > 1 &&
      panel === "trend" &&
      scope.yearFrom === "" &&
      scope.yearTo === "",
  });

  const cohortLongTermQ = useQuery({
    queryKey: ["comm-cohort-year-long", cohortRunKeys, cohortRunForPanel("long_term")],
    queryFn: async () => Promise.all(cohortRunKeys.map((k) => fetchCommercialYearlyStats(k))),
    enabled: cohortRunForPanel("long_term") > 0 && cohortRunKeys.length > 1 && panel === "long_term",
  });

  const cohortHistQ = useQuery({
    queryKey: [
      "comm-cohort-hist",
      cohortRunKeys,
      cohortRunForPanel("histogram"),
      histScope,
      histScope === "single" ? histYear : null,
      analysisPeriod,
    ],
    queryFn: () =>
      fetchCommercialCohortHistogram(cohortBody, {
        contract_year: histScope === "single" && histYear != null ? histYear : undefined,
      }),
    enabled: cohortRunForPanel("histogram") > 0 && cohortRunKeys.length > 1,
  });

  const cohortTxQ = useQuery({
    queryKey: ["comm-cohort-tx", cohortRunKeys, cohortRunForPanel("transactions"), txPage, analysisPeriod],
    queryFn: () =>
      fetchCommercialCohortTransactions({
        ...cohortBody,
        page: txPage,
        page_size: TX_PAGE,
      }),
    enabled: cohortRunForPanel("transactions") > 0 && cohortRunKeys.length > 1,
  });

  const trendCohortActive = cohortRunForPanel("trend") > 0;
  const longTermCohortActive = cohortRunForPanel("long_term") > 0;
  const histCohortActive = cohortRunForPanel("histogram") > 0;
  const txCohortActive = cohortRunForPanel("transactions") > 0;

  const runCohortAnalysis = () => {
    if (!canRunCohort) return;
    setCohortRunKeys([...cohortKeys]);
    setCohortRunByPanel((prev) => ({ ...prev, [panel]: (prev[panel] ?? 0) + 1 }));
  };

  const addToCohort = (clusterKey: string) => {
    if (cohortKeys.length >= MAX_COHORT_CLUSTERS) return;
    setCohortExtra((prev) => (prev.includes(clusterKey) ? prev : [...prev, clusterKey]));
  };

  useEffect(() => {
    setDragOffset({ x: 0, y: 0 });
    dragSession.current = null;
    setPanel("trend");
    setTxPage(1);
    setTxExportError(null);
    setHistScope("all");
    setHistYear(null);
    setCohortExtra([]);
    setCohortRunKeys([]);
    setCohortRunByPanel({});
    setCohortChartMetric("mean");
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

  const handleTxExport = async () => {
    setTxExportLoading(true);
    setTxExportError(null);
    try {
      if (txCohortActive && cohortRunKeys.length > 1) {
        await downloadCommercialCohortTransactionsCsv(cohortBody);
      } else {
        await downloadCommercialTransactionsCsv(row.cluster_key, { ...region, ...analysisPeriod });
      }
    } catch (err) {
      const ax = err as { response?: { data?: Blob | { detail?: string } } };
      const data = ax.response?.data;
      if (data instanceof Blob) {
        try {
          const parsed = JSON.parse(await data.text()) as { detail?: string };
          setTxExportError(parsed.detail ? String(parsed.detail) : "CSV 내보내기에 실패했습니다.");
        } catch {
          setTxExportError("CSV 내보내기에 실패했습니다.");
        }
      } else if (data && typeof data === "object" && "detail" in data && data.detail) {
        setTxExportError(String(data.detail));
      } else {
        setTxExportError("CSV 내보내기에 실패했습니다.");
      }
    } finally {
      setTxExportLoading(false);
    }
  };

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
                {commercialAssetTypeLabel(scope.assetType === "all" ? row.asset_type : scope.assetType)} · n=
                {row.count.toLocaleString("ko-KR")} · 평균 {fmtPrice(row.mean, 0)} 만원/㎡
                {usesMartPeriod && periodLabel && (
                  <>
                    {" "}
                    · 분석 {periodLabel}
                  </>
                )}
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
          {peerClusters.length > 0 && (
            <div className="mt-2 rounded border border-indigo-100 bg-indigo-50/50 px-2 py-1.5 text-[10px]">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-indigo-800">분석 코호트</span>
                <span className="text-slate-600">
                  {cohortKeys.length === 1 ? "단일 도로" : `${cohortKeys.length}개 도로 cluster`}
                </span>
                {canRunCohort && (
                  <button
                    type="button"
                    className="ml-auto px-2 py-0.5 rounded bg-indigo-700 text-white text-[10px] font-semibold hover:bg-indigo-800 disabled:opacity-50"
                    title="현재 탭 기준 실시간 통합 분석"
                    onClick={runCohortAnalysis}
                  >
                    통합분석
                  </button>
                )}
              </div>
              {cohortStale && (
                <p className="mt-1 text-amber-700">코호트가 변경되었습니다. 「통합분석」을 다시 실행하세요.</p>
              )}
              {cohortKeys.length >= MAX_COHORT_CLUSTERS && (
                <p className="mt-1 text-slate-500">최대 {MAX_COHORT_CLUSTERS}개 도로까지 포함할 수 있습니다.</p>
              )}
              {cohortExtra.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {cohortExtra.map((k) => {
                    const label =
                      peerClusters.find((p) => p.cluster_key === k)?.display_label ?? k.slice(0, 8);
                    return (
                      <button
                        key={k}
                        type="button"
                        className="px-1.5 py-0.5 rounded bg-white border border-indigo-200 text-indigo-700"
                        onClick={() => setCohortExtra((prev) => prev.filter((x) => x !== k))}
                        title="코호트에서 제거"
                      >
                        {label} ×
                      </button>
                    );
                  })}
                </div>
              )}
              {peerOptions.length > 0 && (
                <label className="mt-1 flex items-center gap-1 text-slate-600">
                  <span>+ 도로 추가</span>
                  <select
                    className="text-[10px] border border-slate-200 rounded px-1 py-0.5 max-w-[220px]"
                    defaultValue=""
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v) addToCohort(v);
                      e.currentTarget.value = "";
                    }}
                    disabled={cohortKeys.length >= MAX_COHORT_CLUSTERS}
                  >
                    <option value="">선택…</option>
                    {peerOptions.slice(0, 80).map((p) => (
                      <option key={p.cluster_key} value={p.cluster_key}>
                        {p.display_label} (n={p.count})
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
          )}
        </div>

        <div className="flex-1 overflow-auto px-4 py-3 space-y-4">
          {panel === "trend" && (
            <>
              {trendCohortActive && cohortRollingQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-6">코호트 롤링 구간 집계 중…</p>
              )}
              {trendCohortActive && cohortRollingQ.isError && (
                <p className="text-xs text-amber-700 text-center py-6">
                  {String(
                    (cohortRollingQ.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
                      "통합 롤링 추세를 불러오지 못했습니다.",
                  )}
                </p>
              )}
              {trendCohortActive && cohortRollingQ.data && (
                <CohortTrendPanel
                  series={cohortRollingQ.data.map(commercialRollingToTrendSeries)}
                  metric={cohortChartMetric}
                  onMetricChange={setCohortChartMetric}
                  buildingCount={cohortRunKeys.length}
                  chartTitle="12개월 롤링 버킷 추이 (꺾은선)"
                  note={
                    statsAsOfLabel || cohortRollingQ.data[0]?.as_of_month
                      ? `${statsAsOfLabel ?? cohortRollingQ.data[0]?.as_of_month?.slice(0, 7)}${cohortRollingQ.data[0]?.window_years ? ` · ${cohortRollingQ.data[0].window_years}년 창` : ""}`
                      : undefined
                  }
                />
              )}
              {!trendCohortActive && (scope.yearFrom !== "" || scope.yearTo !== "") && (
                <p className="text-xs text-slate-400 text-center py-6">
                  연도 필터가 선택되어 있습니다. 롤링 추세는 분석 구간(3·5년 창) 선택 시 표시됩니다.
                </p>
              )}
              {!trendCohortActive && scope.yearFrom === "" && scope.yearTo === "" && rollingQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-6">롤링 구간 집계 중…</p>
              )}
              {!trendCohortActive && scope.yearFrom === "" && scope.yearTo === "" && rollingQ.isError && (
                <p className="text-xs text-amber-700 text-center py-6">롤링 추세를 불러오지 못했습니다.</p>
              )}
              {!trendCohortActive &&
                scope.yearFrom === "" &&
                scope.yearTo === "" &&
                rollingQ.data &&
                rollingQ.data.points.length > 0 && (
                <>
                  {(statsAsOfLabel || rollingQ.data.as_of_month) && (
                    <p className="text-[10px] text-indigo-600 mb-1">
                      {statsAsOfLabel ?? `${rollingQ.data.as_of_month?.slice(0, 7)} 기준`}
                      {rollingQ.data.window_years ? ` · ${rollingQ.data.window_years}년 창` : ""}
                    </p>
                  )}
                  <div className="rounded-lg border border-slate-100 bg-slate-50/60 px-2 py-3">
                    <p className="text-[10px] font-semibold text-slate-600 px-1 mb-2">12개월 롤링 버킷 추이</p>
                    <RollingTrendChart points={rollingQ.data.points} />
                  </div>
                  <div className="rounded-lg border border-slate-100 bg-white overflow-hidden">
                    <p className="text-[10px] font-semibold text-slate-600 px-3 pt-3 pb-1">구간별 수치</p>
                    <table className="w-full text-xs border-collapse">
                      <thead>
                        <tr className="bg-slate-50 text-slate-600">
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">구간</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">건수</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-blue-700">
                            평균(만원/㎡)
                          </th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-800">
                        {[...rollingQ.data.points]
                          .sort((a, b) => a.bucket_index - b.bucket_index)
                          .map((p) => (
                            <tr key={p.bucket_index}>
                              <td className="border border-slate-200 px-2 py-1 tabular-nums">{p.label}</td>
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
              {!trendCohortActive &&
                scope.yearFrom === "" &&
                scope.yearTo === "" &&
                rollingQ.data &&
                rollingQ.data.points.length === 0 && (
                <p className="text-xs text-slate-400 text-center py-6">표시할 롤링 데이터가 없습니다.</p>
              )}
            </>
          )}

          {panel === "long_term" && (
            <>
              {longTermCohortActive && cohortLongTermQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-6">코호트 연도별 집계 중…</p>
              )}
              {longTermCohortActive && cohortLongTermQ.isError && (
                <p className="text-xs text-amber-700 text-center py-6">
                  {String(
                    (cohortLongTermQ.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
                      "통합 장기 추세를 불러오지 못했습니다.",
                  )}
                </p>
              )}
              {longTermCohortActive && cohortLongTermQ.data && (
                <CohortTrendPanel
                  series={cohortLongTermQ.data.map(commercialYearlyResponseToTrendSeries)}
                  metric={cohortChartMetric}
                  onMetricChange={setCohortChartMetric}
                  buildingCount={cohortRunKeys.length}
                  chartTitle="연도별 추이 (꺾은선)"
                  note="만년력 · 롤링 통계 창과 기간·표본이 다를 수 있음"
                />
              )}
              {!longTermCohortActive && longTermYearQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-6">연도별 집계 중…</p>
              )}
              {!longTermCohortActive && !longTermYearQ.isLoading && longTermYears.length === 0 && (
                <p className="text-xs text-slate-400 text-center py-6">표시할 연도별 데이터가 없습니다.</p>
              )}
              {!longTermCohortActive && longTermYears.length > 0 && (
                <>
                  {longTermYears.some((p) => p.year < 2021) && (
                    <p className="text-[10px] text-indigo-600 mb-1">
                      2010–2020 구간 포함 · {longTermYearQ.data?.data_source === "mart" ? "annual mart" : "실시간 집계"}
                    </p>
                  )}
                  <p className="text-[10px] text-slate-500 mb-2">
                    만년력 연도별 추이 · 롤링 통계 창({periodLabel ?? `${scope.windowYears}년`})과 기간·표본이 다릅니다.
                  </p>
                  <div className="rounded-lg border border-slate-100 bg-slate-50/60 px-2 py-3">
                    <p className="text-[10px] font-semibold text-slate-600 px-1 mb-2">추이 (꺾은선)</p>
                    <YearlyTrendChart points={longTermYears} />
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
                        {longTermYears.map((p) => (
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
                  <option value="all">{usesMartPeriod ? "분석 구간 전체" : "전체 연도"}</option>
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
              {histCohortActive && cohortHistQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-4">코호트 분포 계산 중…</p>
              )}
              {histCohortActive && cohortHistQ.isError && (
                <p className="text-xs text-amber-700 text-center py-4">통합 분포를 불러오지 못했습니다.</p>
              )}
              {histCohortActive && cohortHistQ.data && (
                <>
                  <p className="text-[10px] text-indigo-700 bg-indigo-50 border border-indigo-100 rounded px-2 py-1">
                    {cohortRunKeys.length}개 도로 cluster 통합 · 실시간 · n=
                    {cohortHistQ.data.n.toLocaleString("ko-KR")}건
                  </p>
                  <div className="rounded-lg border border-slate-100 bg-slate-50/60 px-2 py-2">
                    <HistogramChart bins={cohortHistQ.data.bins} />
                  </div>
                </>
              )}
              {!histCohortActive && histQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-4">분포 계산 중…</p>
              )}
              {!histCohortActive && histQ.isError && (
                <p className="text-xs text-red-500 text-center py-4">분포를 불러오지 못했습니다.</p>
              )}
              {!histCohortActive && histQ.data && (
                <>
                  <p className="text-[10px] text-slate-500">
                    표본 수 <strong className="text-slate-700">{histQ.data.n.toLocaleString("ko-KR")}</strong>건
                    {histScope === "all" && usesMartPeriod && periodLabel && (
                      <>
                        {" "}
                        · 분석 {periodLabel}
                      </>
                    )}
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
              {txCohortActive && cohortTxQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-4">코호트 목록 불러오는 중…</p>
              )}
              {txCohortActive && cohortTxQ.isError && (
                <p className="text-xs text-amber-700 text-center py-4">통합 거래 목록을 불러오지 못했습니다.</p>
              )}
              {txCohortActive && cohortTxQ.data && (
                <>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <p className="text-[10px] text-indigo-700 bg-indigo-50 border border-indigo-100 rounded px-2 py-1">
                      {cohortRunKeys.length}개 도로 cluster 통합 · 실시간 · 전체{" "}
                      {cohortTxQ.data.total.toLocaleString("ko-KR")}건
                      {usesMartPeriod && periodLabel ? (
                        <>
                          {" "}
                          · 분석 {periodLabel}
                        </>
                      ) : scope.yearFrom !== "" || scope.yearTo !== "" ? (
                        <>
                          {" "}
                          · 연도 {scope.yearFrom || "…"}–{scope.yearTo || "…"}
                        </>
                      ) : null}
                    </p>
                    <button
                      type="button"
                      disabled={txExportLoading || cohortTxQ.data.total === 0}
                      onClick={() => void handleTxExport()}
                      className="shrink-0 px-2.5 py-1 rounded border border-slate-200 text-[11px] font-medium text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
                    >
                      {txExportLoading ? "내보내는 중…" : "CSV 내보내기"}
                    </button>
                  </div>
                  {txExportError && <p className="text-[10px] text-red-500">{txExportError}</p>}
                  <CommercialTransactionTable items={cohortTxQ.data.items} showCluster />
                  <CommercialTransactionPager
                    total={cohortTxQ.data.total}
                    pageSize={TX_PAGE}
                    offset={txOffset}
                    onPrev={() => setTxPage((p) => Math.max(1, p - 1))}
                    onNext={() => setTxPage((p) => p + 1)}
                  />
                </>
              )}
              {!txCohortActive && txQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-4">목록 불러오는 중…</p>
              )}
              {!txCohortActive && txQ.isError && (
                <p className="text-xs text-red-500 text-center py-4">목록을 불러오지 못했습니다.</p>
              )}
              {!txCohortActive && txQ.data && (
                <>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <p className="text-[10px] text-slate-500">
                      전체 <strong className="text-slate-700">{txQ.data.total.toLocaleString("ko-KR")}</strong>건
                      {usesMartPeriod && periodLabel ? (
                        <>
                          {" "}
                          · 분석 {periodLabel}
                        </>
                      ) : scope.yearFrom !== "" || scope.yearTo !== "" ? (
                        <>
                          {" "}
                          · 연도 {scope.yearFrom || "…"}–{scope.yearTo || "…"}
                        </>
                      ) : null}
                    </p>
                    <button
                      type="button"
                      disabled={txExportLoading || txQ.data.total === 0}
                      onClick={() => void handleTxExport()}
                      className="shrink-0 px-2.5 py-1 rounded border border-slate-200 text-[11px] font-medium text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
                    >
                      {txExportLoading ? "내보내는 중…" : "CSV 내보내기"}
                    </button>
                  </div>
                  {txExportError && <p className="text-[10px] text-red-500">{txExportError}</p>}
                  <CommercialTransactionTable items={txQ.data.items} />
                  <CommercialTransactionPager
                    total={txQ.data.total}
                    offset={txOffset}
                    pageSize={TX_PAGE}
                    onPrev={() => setTxPage((p) => Math.max(1, p - 1))}
                    onNext={() => setTxPage((p) => p + 1)}
                  />
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
              cohortKeys={cohortRunKeys}
              cohortRunId={cohortRunForPanel("floor_index")}
              scope={scope}
              periodStart={periodStart}
              periodEnd={periodEnd}
              count={cohortRunKeys.length > 1 ? analysisCount : row.count}
              isFactory={!isShop}
            />
          )}

          {panel === "regression" && (
            <CommercialRegressionPanel
              clusterKey={row.cluster_key}
              cohortKeys={cohortRunKeys}
              cohortRunId={cohortRunForPanel("regression")}
              scope={scope}
              periodStart={periodStart}
              periodEnd={periodEnd}
              isShop={isShop}
              count={cohortRunKeys.length > 1 ? analysisCount : row.count}
            />
          )}
        </div>
      </div>
    </div>
  );
}
