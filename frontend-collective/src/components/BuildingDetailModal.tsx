import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  COLLECTIVE_EXPERIMENT_MODE,
  downloadBuildingTransactionsCsv,
  downloadCohortTransactionsCsv,
  fetchBuildingHistogram,
  fetchBuildingRollingStats,
  fetchBuildingTransactions,
  fetchBuildingYearlyStats,
  fetchCohortHistogram,
  fetchCohortTransactions,
  type BuildingStatsRow,
} from "../api/client";
import type { AssetSelectorType, AssetType, CollectiveTransactionRow } from "../types";
import { assetTypeLabel } from "../types";
import BuildingRegressionPanel from "./BuildingRegressionPanel";
import CohortTrendPanel from "./CohortTrendPanel";
import FloorIndexPanel from "./FloorIndexPanel";
import HistogramChart from "./HistogramChart";
import type { CohortTrendMetric } from "./MultiBuildingTrendChart";
import RollingTrendChart from "./RollingTrendChart";
import YearlyTrendChart from "./YearlyTrendChart";
import type { StatsWindowYears } from "./StatsWindowToggle";
import { buildAnalysisPeriodParams, formatPeriodLabel, type AnalysisPeriodParams } from "../utils/analysisPeriod";
import { rollingToTrendSeries, yearlyResponseToTrendSeries } from "../utils/cohortTrendSeries";

const TX_PAGE = 25;

type PanelMode = "trend" | "long_term" | "histogram" | "transactions" | "floor_index" | "regression";

const MAX_COHORT_BUILDINGS = 10;

const TABS: { id: PanelMode; label: string | ((assetType: AssetType) => string) }[] = [
  { id: "trend", label: "롤링 구간" },
  { id: "histogram", label: "단가 분포" },
  { id: "transactions", label: "거래 목록" },
  { id: "floor_index", label: (t) => (t === "presale" ? "층·권리·면적 효용지수" : "층·동·면적 효용지수") },
  { id: "regression", label: "회귀 분석" },
  { id: "long_term", label: "장기 추세" },
];

function fmtPrice(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function fmtContractDate(t: CollectiveTransactionRow) {
  if (t.contract_date) return t.contract_date;
  if (t.contract_year == null) return "—";
  if (t.contract_month) return `${t.contract_year}-${String(t.contract_month).padStart(2, "0")}-01`;
  return String(t.contract_year);
}

function dongLabel(assetType: AssetType) {
  return assetType === "presale" ? "권리" : "동";
}

function dongCell(t: CollectiveTransactionRow, assetType: AssetType) {
  return assetType === "presale" ? (t.housing_subtype ?? "—") : (t.dong ?? "—");
}

function TransactionTable({
  items,
  assetType,
  showBuilding = false,
}: {
  items: CollectiveTransactionRow[];
  assetType: AssetType;
  showBuilding?: boolean;
}) {
  const col = dongLabel(assetType);
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-100 dark:border-slate-700">
      <table className="w-full text-[11px] border-collapse min-w-[640px]">
        <thead>
          <tr className="bg-slate-50 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            {showBuilding && (
              <th className="border border-slate-200 dark:border-slate-600 px-2 py-1.5 text-left font-medium">단지</th>
            )}
            <th className="border border-slate-200 dark:border-slate-600 px-2 py-1.5 text-left font-medium">계약일</th>
            <th className="border border-slate-200 dark:border-slate-600 px-2 py-1.5 text-left font-medium">{col}</th>
            <th className="border border-slate-200 dark:border-slate-600 px-2 py-1.5 text-right font-medium">층</th>
            <th className="border border-slate-200 dark:border-slate-600 px-2 py-1.5 text-right font-medium">면적(㎡)</th>
            <th className="border border-slate-200 dark:border-slate-600 px-2 py-1.5 text-right font-medium">금액(만원)</th>
            <th className="border border-slate-200 dark:border-slate-600 px-2 py-1.5 text-right font-bold text-blue-700 dark:text-blue-400">단가</th>
            <th className="border border-slate-200 dark:border-slate-600 px-2 py-1.5 text-left font-medium">매수</th>
            <th className="border border-slate-200 dark:border-slate-600 px-2 py-1.5 text-left font-medium">매도</th>
            <th className="border border-slate-200 dark:border-slate-600 px-2 py-1.5 text-left font-medium">거래유형</th>
          </tr>
        </thead>
        <tbody className="text-slate-800 dark:text-slate-200">
          {items.map((t) => (
            <tr key={t.id}>
              {showBuilding && (
                <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 whitespace-nowrap">{t.display_name ?? "—"}</td>
              )}
              <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 tabular-nums whitespace-nowrap">
                {fmtContractDate(t)}
              </td>
              <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 whitespace-nowrap">{dongCell(t, assetType)}</td>
              <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 text-right tabular-nums">{t.floor ?? "—"}</td>
              <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 text-right tabular-nums">
                {fmtPrice(t.exclusive_area)}
              </td>
              <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 text-right tabular-nums">{fmtPrice(t.price)}</td>
              <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 text-right tabular-nums text-blue-600 dark:text-blue-400 font-semibold">
                {fmtPrice(t.unit_price)}
              </td>
              <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 whitespace-nowrap">{t.buyer_type ?? "—"}</td>
              <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 whitespace-nowrap">{t.seller_type ?? "—"}</td>
              <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 whitespace-nowrap">{t.deal_type ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

async function txExportErrorMessage(err: unknown): Promise<string> {
  const ax = err as { response?: { data?: Blob | { detail?: string } } };
  const data = ax.response?.data;
  if (data instanceof Blob) {
    try {
      const parsed = JSON.parse(await data.text()) as { detail?: string };
      if (parsed.detail) return String(parsed.detail);
    } catch {
      /* ignore */
    }
  } else if (data && typeof data === "object" && "detail" in data && data.detail) {
    return String(data.detail);
  }
  return "CSV 내보내기에 실패했습니다.";
}

export default function BuildingDetailModal({
  row,
  assetType,
  windowYears = 5,
  yearFrom,
  yearTo,
  periodStart,
  periodEnd,
  statsAsOfLabel,
  peerBuildings = [],
  onClose,
}: {
  row: BuildingStatsRow;
  assetType: AssetSelectorType;
  windowYears?: StatsWindowYears;
  yearFrom?: number;
  yearTo?: number;
  periodStart?: string | null;
  periodEnd?: string | null;
  statsAsOfLabel?: string | null;
  peerBuildings?: BuildingStatsRow[];
  onClose: () => void;
}) {
  const effectiveAssetType = (assetType === "all" ? row.asset_type : assetType) as AssetType;
  const analysisPeriod: AnalysisPeriodParams = useMemo(
    () => buildAnalysisPeriodParams(yearFrom, yearTo, periodStart, periodEnd),
    [yearFrom, yearTo, periodStart, periodEnd],
  );
  const periodLabel = formatPeriodLabel(periodStart, periodEnd);
  const usesMartPeriod = Boolean(analysisPeriod.contract_date_from && analysisPeriod.contract_date_to);
  const [panel, setPanel] = useState<PanelMode>("trend");
  const [cohortExtra, setCohortExtra] = useState<string[]>([]);
  const [cohortRunKeys, setCohortRunKeys] = useState<string[]>([]);
  const [cohortRunByPanel, setCohortRunByPanel] = useState<Partial<Record<PanelMode, number>>>({});
  const [histScope, setHistScope] = useState<"all" | "single">("all");
  const [histYear, setHistYear] = useState<number | null>(null);
  const [txPage, setTxPage] = useState(1);
  const [txExportLoading, setTxExportLoading] = useState(false);
  const [txExportError, setTxExportError] = useState<string | null>(null);
  const [cohortChartMetric, setCohortChartMetric] = useState<CohortTrendMetric>("mean");
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const dragSession = useRef<{ startX: number; startY: number; baseX: number; baseY: number } | null>(null);
  const experiment = COLLECTIVE_EXPERIMENT_MODE;

  const cohortKeys = useMemo(
    () => [row.building_key, ...cohortExtra.filter((k) => k !== row.building_key)].slice(0, MAX_COHORT_BUILDINGS),
    [row.building_key, cohortExtra],
  );
  const cohortStale =
    Object.keys(cohortRunByPanel).length > 0 &&
    (cohortRunKeys.length !== cohortKeys.length || cohortRunKeys.some((k, i) => k !== cohortKeys[i]));
  const canRunCohort = cohortKeys.length > 1;
  const cohortRunForPanel = (p: PanelMode) => (cohortStale ? 0 : cohortRunByPanel[p] ?? 0);

  const cohortBody = useMemo(
    () => ({
      building_keys: cohortRunKeys,
      asset_type: assetType === "all" ? undefined : effectiveAssetType,
      experiment,
      ...analysisPeriod,
    }),
    [cohortRunKeys, assetType, effectiveAssetType, experiment, analysisPeriod],
  );
  const peerOptions = useMemo(
    () => peerBuildings.filter((b) => b.building_key !== row.building_key && !cohortExtra.includes(b.building_key)),
    [peerBuildings, row.building_key, cohortExtra],
  );

  const rollingQ = useQuery({
    queryKey: ["b-rolling", row.building_key, windowYears],
    queryFn: () => fetchBuildingRollingStats(row.building_key, windowYears),
    enabled: cohortRunForPanel("trend") === 0 && panel === "trend",
  });

  const longTermYearQ = useQuery({
    queryKey: ["b-year-long", row.building_key],
    queryFn: () => fetchBuildingYearlyStats(row.building_key),
    enabled: cohortRunForPanel("long_term") === 0 && panel === "long_term",
  });

  const windowYearQ = useQuery({
    queryKey: ["b-year-window", row.building_key, analysisPeriod],
    queryFn: () =>
      fetchBuildingYearlyStats(row.building_key, {
        contract_date_from: analysisPeriod.contract_date_from,
        contract_date_to: analysisPeriod.contract_date_to,
      }),
    enabled: cohortRunForPanel("histogram") === 0 && panel === "histogram",
  });

  const histYears = useMemo(
    () => [...(windowYearQ.data?.points ?? [])].sort((a, b) => a.year - b.year),
    [windowYearQ.data?.points],
  );

  const longTermYears = useMemo(
    () => [...(longTermYearQ.data?.points ?? [])].sort((a, b) => a.year - b.year),
    [longTermYearQ.data?.points],
  );

  useEffect(() => {
    if (histYears.length && histYear == null) {
      setHistYear(histYears[histYears.length - 1].year);
    }
  }, [histYears, histYear]);

  const histQ = useQuery({
    queryKey: ["b-hist", row.building_key, histScope, histScope === "single" ? histYear : null, analysisPeriod],
    queryFn: () =>
      fetchBuildingHistogram(row.building_key, {
        contract_year: histScope === "single" && histYear != null ? histYear : undefined,
        ...analysisPeriod,
      }),
    enabled: cohortRunForPanel("histogram") === 0,
  });

  const txQ = useQuery({
    queryKey: ["b-tx", row.building_key, txPage, analysisPeriod],
    queryFn: () =>
      fetchBuildingTransactions(row.building_key, {
        page: txPage,
        page_size: TX_PAGE,
        ...analysisPeriod,
      }),
    enabled: cohortRunForPanel("transactions") === 0,
  });

  const cohortRollingQ = useQuery({
    queryKey: ["cohort-rolling", cohortRunKeys, windowYears, cohortRunForPanel("trend")],
    queryFn: async () => Promise.all(cohortRunKeys.map((k) => fetchBuildingRollingStats(k, windowYears))),
    enabled: cohortRunForPanel("trend") > 0 && cohortRunKeys.length > 1 && panel === "trend",
  });

  const cohortLongTermQ = useQuery({
    queryKey: ["cohort-year-long", cohortRunKeys, cohortRunForPanel("long_term")],
    queryFn: async () => Promise.all(cohortRunKeys.map((k) => fetchBuildingYearlyStats(k))),
    enabled: cohortRunForPanel("long_term") > 0 && cohortRunKeys.length > 1 && panel === "long_term",
  });

  const cohortHistQ = useQuery({
    queryKey: [
      "cohort-hist",
      cohortRunKeys,
      cohortRunForPanel("histogram"),
      histScope,
      histScope === "single" ? histYear : null,
      analysisPeriod,
    ],
    queryFn: () =>
      fetchCohortHistogram(cohortBody, {
        contract_year: histScope === "single" && histYear != null ? histYear : undefined,
      }),
    enabled: cohortRunForPanel("histogram") > 0 && cohortRunKeys.length > 1,
  });

  const cohortTxQ = useQuery({
    queryKey: ["cohort-tx", cohortRunKeys, cohortRunForPanel("transactions"), txPage, analysisPeriod],
    queryFn: () =>
      fetchCohortTransactions({
        ...cohortBody,
        page: txPage,
        page_size: TX_PAGE,
      }),
    enabled: cohortRunForPanel("transactions") > 0 && cohortRunKeys.length > 1,
  });

  useEffect(() => {
    setDragOffset({ x: 0, y: 0 });
    dragSession.current = null;
    setPanel("trend");
    setTxPage(1);
    setTxExportError(null);
    setHistScope("all");
    setCohortExtra([]);
    setCohortRunKeys([]);
    setCohortRunByPanel({});
    setCohortChartMetric("mean");
  }, [row.building_key]);

  const runCohortAnalysis = () => {
    if (!canRunCohort) return;
    setCohortRunKeys([...cohortKeys]);
    setCohortRunByPanel((prev) => ({ ...prev, [panel]: (prev[panel] ?? 0) + 1 }));
  };

  const addToCohort = (buildingKey: string) => {
    if (cohortKeys.length >= MAX_COHORT_BUILDINGS) return;
    setCohortExtra((prev) => (prev.includes(buildingKey) ? prev : [...prev, buildingKey]));
  };

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

  const trendCohortActive = cohortRunForPanel("trend") > 0;
  const longTermCohortActive = cohortRunForPanel("long_term") > 0;
  const histCohortActive = cohortRunForPanel("histogram") > 0;
  const txCohortActive = cohortRunForPanel("transactions") > 0;

  const handleTxExport = async () => {
    setTxExportLoading(true);
    setTxExportError(null);
    try {
      if (txCohortActive && cohortRunKeys.length > 1) {
        await downloadCohortTransactionsCsv(cohortBody);
      } else {
        await downloadBuildingTransactionsCsv(row.building_key, analysisPeriod);
      }
    } catch (err) {
      setTxExportError(await txExportErrorMessage(err));
    } finally {
      setTxExportLoading(false);
    }
  };

  const txExportButton = (
    <button
      type="button"
      disabled={txExportLoading}
      onClick={() => void handleTxExport()}
      className="shrink-0 px-2.5 py-1 rounded border border-slate-200 text-[11px] font-medium text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
    >
      {txExportLoading ? "내보내는 중…" : "CSV 내보내기"}
    </button>
  );

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
        className="fixed left-1/2 top-1/2 modal-shell rounded-xl shadow-xl max-w-4xl w-[calc(100%-2rem)] max-h-[85vh] flex flex-col border"
        style={{ transform: `translate(calc(-50% + ${dragOffset.x}px), calc(-50% + ${dragOffset.y}px))` }}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div
          className="px-4 py-3 modal-header cursor-move select-none shrink-0"
          onMouseDown={onHeaderMouseDown}
        >
          <div className="flex justify-between items-start gap-2">
            <div className="min-w-0 flex-1">
              <h2 className="text-sm font-bold">{row.display_name}</h2>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                {assetTypeLabel(effectiveAssetType)} · n={row.count.toLocaleString("ko-KR")} · 평균 {fmtPrice(row.mean)} 만원/㎡
                {usesMartPeriod && periodLabel && (
                  <span className="ml-1.5 text-indigo-600 dark:text-indigo-400">
                    · 분석 {periodLabel}
                    {statsAsOfLabel ? ` (${statsAsOfLabel})` : ""}
                  </span>
                )}
                {(yearFrom != null || yearTo != null) && (
                  <span className="ml-1.5 text-indigo-600 dark:text-indigo-400">
                    · 연도 {yearFrom ?? "…"}–{yearTo ?? "…"}
                  </span>
                )}
                {experiment && (
                  <span className="ml-1.5 text-indigo-600 font-medium">· 실험 모드</span>
                )}
              </p>
            </div>
            <button
              type="button"
              aria-label="닫기"
              className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 text-xl leading-none px-1 shrink-0"
              onClick={onClose}
            >
              ×
            </button>
          </div>
          <div
            className="mt-2 flex flex-wrap gap-0.5 rounded-md border modal-tab-bar p-0.5"
            role="tablist"
          >
            {TABS.map(({ id, label }) => {
              const tabLabel = typeof label === "function" ? label(effectiveAssetType) : label;
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
                      ? "modal-tab-active"
                      : "modal-tab-idle",
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
          {peerBuildings.length > 0 && (
            <div className="mt-2 rounded border border-indigo-100 bg-indigo-50/50 px-2 py-1.5 text-[10px]">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-indigo-800">분석 코호트</span>
                <span className="text-slate-600">
                  {cohortKeys.length === 1 ? "단일 단지" : `${cohortKeys.length}개 단지`}
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
              {cohortKeys.length >= MAX_COHORT_BUILDINGS && (
                <p className="mt-1 text-slate-500">최대 {MAX_COHORT_BUILDINGS}개 단지까지 포함할 수 있습니다.</p>
              )}
              {cohortExtra.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {cohortExtra.map((k) => {
                    const label = peerBuildings.find((b) => b.building_key === k)?.display_name ?? k.slice(0, 8);
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
                  <span>+ 단지 추가</span>
                  <select
                    className="text-[10px] border border-slate-200 rounded px-1 py-0.5 max-w-[180px]"
                    defaultValue=""
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v) addToCohort(v);
                      e.target.value = "";
                    }}
                    disabled={cohortKeys.length >= MAX_COHORT_BUILDINGS}
                  >
                    <option value="">선택…</option>
                    {peerOptions.slice(0, 80).map((b) => (
                      <option key={b.building_key} value={b.building_key}>
                        {b.display_name} (n={b.count})
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
                  series={cohortRollingQ.data.map(rollingToTrendSeries)}
                  metric={cohortChartMetric}
                  onMetricChange={setCohortChartMetric}
                  buildingCount={cohortRunKeys.length}
                  chartTitle="12개월 롤링 버킷 추이 (꺾은선)"
                  note={
                    cohortRollingQ.data[0]?.stats_as_of_label
                      ? `${cohortRollingQ.data[0].stats_as_of_label}${cohortRollingQ.data[0].window_years ? ` · ${cohortRollingQ.data[0].window_years}년 창` : ""}`
                      : undefined
                  }
                />
              )}
              {!trendCohortActive && panel === "trend" && rollingQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-6">롤링 구간 집계 중…</p>
              )}
              {!trendCohortActive && panel === "trend" && rollingQ.isError && (
                <p className="text-xs text-amber-700 dark:text-amber-400 text-center py-6">롤링 추세를 불러오지 못했습니다.</p>
              )}
              {!trendCohortActive && panel === "trend" && rollingQ.data && rollingQ.data.points.length > 0 && (
                <>
                  {rollingQ.data.stats_as_of_label && (
                    <p className="text-[10px] text-indigo-600 dark:text-indigo-400 mb-1">
                      {rollingQ.data.stats_as_of_label}
                      {rollingQ.data.window_years ? ` · ${rollingQ.data.window_years}년 창` : ""}
                    </p>
                  )}
                  <div className="modal-card px-2 py-3">
                    <p className="text-[10px] font-semibold text-slate-600 dark:text-slate-300 px-1 mb-2">12개월 롤링 버킷 추이</p>
                    <RollingTrendChart points={rollingQ.data.points} />
                  </div>
                  <div className="modal-table-wrap">
                    <p className="text-[10px] font-semibold text-slate-600 dark:text-slate-300 px-3 pt-3 pb-1">구간별 수치</p>
                    <table className="w-full text-xs border-collapse modal-inner-table">
                      <thead>
                        <tr>
                          <th className="border px-2 py-1.5 text-left font-medium">구간</th>
                          <th className="border px-2 py-1.5 text-right font-medium">건수</th>
                          <th className="border px-2 py-1.5 text-right font-bold text-blue-700 dark:text-blue-400">
                            평균(만원/㎡)
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...rollingQ.data.points].sort((a, b) => a.bucket_index - b.bucket_index).map((p) => (
                          <tr key={p.bucket_index}>
                            <td className="border px-2 py-1 tabular-nums">{p.label}</td>
                            <td className="border px-2 py-1 text-right tabular-nums">
                              {p.count.toLocaleString("ko-KR")}
                            </td>
                            <td className="border px-2 py-1 text-right tabular-nums text-blue-600 dark:text-blue-400 font-bold">
                              {p.mean != null ? fmtPrice(p.mean) : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
              {!trendCohortActive && panel === "trend" && rollingQ.data && rollingQ.data.points.length === 0 && (
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
                  series={cohortLongTermQ.data.map(yearlyResponseToTrendSeries)}
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
                    <p className="text-[10px] text-indigo-600 dark:text-indigo-400 mb-1">
                      2010–2020 구간 포함 · {longTermYearQ.data?.data_source === "mart" ? "annual mart" : "실시간 집계"}
                    </p>
                  )}
                  <p className="text-[10px] text-slate-500 dark:text-slate-400 mb-2">
                    만년력 연도별 추이 · 롤링 통계 창({periodLabel ?? "5년"})과 기간·표본이 다릅니다.
                  </p>
                  <div className="modal-card px-2 py-3">
                    <p className="text-[10px] font-semibold text-slate-600 dark:text-slate-300 px-1 mb-2">추이 (꺾은선)</p>
                    <YearlyTrendChart points={longTermYears} />
                  </div>
                  <div className="modal-table-wrap">
                    <p className="text-[10px] font-semibold text-slate-600 dark:text-slate-300 px-3 pt-3 pb-1">연도별 수치</p>
                    <table className="w-full text-xs border-collapse modal-inner-table">
                      <thead>
                        <tr>
                          <th className="border px-2 py-1.5 text-left font-medium">연도</th>
                          <th className="border px-2 py-1.5 text-right font-medium">건수</th>
                          <th className="border px-2 py-1.5 text-right font-bold text-blue-700 dark:text-blue-400">
                            평균(만원/㎡)
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {longTermYears.map((p) => (
                          <tr key={p.year}>
                            <td className="border px-2 py-1 tabular-nums">{p.year}</td>
                            <td className="border px-2 py-1 text-right tabular-nums">
                              {p.count.toLocaleString("ko-KR")}
                            </td>
                            <td className="border px-2 py-1 text-right tabular-nums text-blue-600 dark:text-blue-400 font-bold">
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
                  className="modal-select"
                >
                  <option value="all">{usesMartPeriod ? "분석 구간 전체" : "전체 연도"}</option>
                  <option value="single">특정 연도만</option>
                </select>
                {histScope === "single" && (
                  <select
                    value={histYear ?? ""}
                    onChange={(e) => setHistYear(Number(e.target.value))}
                    className="modal-select"
                  >
                    {histYears.map((p) => (
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
                    {cohortRunKeys.length}개 단지 통합 · 실시간 · n={cohortHistQ.data.n.toLocaleString("ko-KR")}건
                  </p>
                  <div className="rounded-lg border border-slate-100 bg-slate-50/60 px-2 py-2">
                    <HistogramChart bins={cohortHistQ.data.bins} />
                  </div>
                </>
              )}
              {!histCohortActive && histQ.isLoading && <p className="text-xs text-slate-400 text-center py-4">분포 계산 중…</p>}
              {!histCohortActive && histQ.isError && <p className="text-xs text-red-500 text-center py-4">분포를 불러오지 못했습니다.</p>}
              {!histCohortActive && histQ.data && (
                <>
                  <p className="text-[10px] text-slate-500">
                    표본 수 <strong className="text-slate-700">{histQ.data.n.toLocaleString("ko-KR")}</strong>건
                    {histScope === "single" && histYear != null && (
                      <>
                        {" "}
                        · 대상 연도 <strong className="text-slate-700">{histYear}</strong>
                      </>
                    )}
                    {histScope === "all" && usesMartPeriod && periodLabel && (
                      <span> · 분석 {periodLabel}</span>
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
                      {cohortRunKeys.length}개 단지 통합 · 실시간 · 전체 {cohortTxQ.data.total.toLocaleString("ko-KR")}건
                      {yearFrom != null || yearTo != null ? (
                        <span>
                          {" "}
                          · 연도 {yearFrom ?? "…"}–{yearTo ?? "…"}
                        </span>
                      ) : usesMartPeriod && periodLabel ? (
                        <span> · 분석 {periodLabel}</span>
                      ) : null}
                    </p>
                    {txExportButton}
                  </div>
                  {txExportError && <p className="text-[10px] text-red-500">{txExportError}</p>}
                  <TransactionTable items={cohortTxQ.data.items} assetType={effectiveAssetType} showBuilding />
                  <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
                    <span className="text-slate-400">
                      {cohortTxQ.data.total > 0
                        ? `${(txOffset + 1).toLocaleString("ko-KR")}–${Math.min(txOffset + cohortTxQ.data.items.length, cohortTxQ.data.total).toLocaleString("ko-KR")} / ${cohortTxQ.data.total.toLocaleString("ko-KR")}`
                        : "0건"}
                    </span>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        disabled={txPage <= 1}
                        onClick={() => setTxPage((p) => Math.max(1, p - 1))}
                        className="px-2 py-1 rounded border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-700"
                      >
                        이전
                      </button>
                      <button
                        type="button"
                        disabled={txOffset + TX_PAGE >= cohortTxQ.data.total}
                        onClick={() => setTxPage((p) => p + 1)}
                        className="px-2 py-1 rounded border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-700"
                      >
                        다음
                      </button>
                    </div>
                  </div>
                </>
              )}
              {!txCohortActive && txQ.isLoading && <p className="text-xs text-slate-400 text-center py-4">목록 불러오는 중…</p>}
              {!txCohortActive && txQ.isError && <p className="text-xs text-red-500 text-center py-4">목록을 불러오지 못했습니다.</p>}
              {!txCohortActive && txQ.data && (
                <>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <p className="text-[10px] text-slate-500 dark:text-slate-400">
                      전체 <strong className="text-slate-700 dark:text-slate-200">{txQ.data.total.toLocaleString("ko-KR")}</strong>건
                      {yearFrom != null || yearTo != null ? (
                        <span>
                          {" "}
                          · 연도 {yearFrom ?? "…"}–{yearTo ?? "…"}
                        </span>
                      ) : usesMartPeriod && periodLabel ? (
                        <span> · 분석 {periodLabel}</span>
                      ) : (
                        " (전체 연도)"
                      )}
                    </p>
                    {txExportButton}
                  </div>
                  {txExportError && <p className="text-[10px] text-red-500">{txExportError}</p>}
                  <TransactionTable items={txQ.data.items} assetType={effectiveAssetType} />
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
                        className="px-2 py-1 rounded border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-700"
                      >
                        이전
                      </button>
                      <button
                        type="button"
                        disabled={txOffset + TX_PAGE >= txQ.data.total}
                        onClick={() => setTxPage((p) => p + 1)}
                        className="px-2 py-1 rounded border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-700"
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
              cohortKeys={cohortRunKeys}
              cohortRunId={cohortRunForPanel("floor_index")}
              assetType={effectiveAssetType}
              yearFrom={yearFrom}
              yearTo={yearTo}
              periodStart={periodStart ?? undefined}
              periodEnd={periodEnd ?? undefined}
              experiment={experiment}
              floorIndexEligible={analysis.floor_index}
              gateTip={gateTip}
            />
          )}

          {panel === "regression" && (
            <BuildingRegressionPanel
              buildingKey={row.building_key}
              cohortKeys={cohortRunKeys}
              cohortRunId={cohortRunForPanel("regression")}
              assetType={effectiveAssetType}
              yearFrom={yearFrom}
              yearTo={yearTo}
              periodStart={periodStart ?? undefined}
              periodEnd={periodEnd ?? undefined}
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
