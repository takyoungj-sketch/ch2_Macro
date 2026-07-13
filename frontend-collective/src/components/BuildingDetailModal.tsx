import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  COLLECTIVE_EXPERIMENT_MODE,
  downloadBuildingTransactionsCsv,
  downloadCohortTransactionsCsv,
  fetchAllBuildingTransactions,
  fetchAllCohortTransactions,
  fetchBuildingHistogram,
  fetchBuildingRollingStats,
  fetchBuildingYearlyStats,
  fetchCohortHistogram,
  type BuildingStatsRow,
} from "../api/client";
import type { AssetSelectorType, AssetType } from "../types";
import { assetTypeLabel } from "../types";
import BuildingRegressionPanel from "./BuildingRegressionPanel";
import CohortTrendPanel from "./CohortTrendPanel";
import CollectiveTransactionTable from "./CollectiveTransactionTable";
import DraggableModalShell from "./DraggableModalShell";
import FloorIndexPanel from "./FloorIndexPanel";
import HistogramChart from "./HistogramChart";
import type { CohortTrendMetric } from "./MultiBuildingTrendChart";
import RollingTrendChart from "./RollingTrendChart";
import YearlyTrendChart, { yearlyPointPrice } from "./YearlyTrendChart";
import LongTermMetricToggle, { longTermPriceLabel, type LongTermPriceMetric } from "./LongTermMetricToggle";
import type { StatsWindowYears } from "./StatsWindowToggle";
import { buildAnalysisPeriodParams, formatPeriodLabel, type AnalysisPeriodParams } from "../utils/analysisPeriod";
import { rollingToTrendSeries, yearlyResponseToTrendSeries } from "../utils/cohortTrendSeries";

type PanelMode = "trend" | "long_term" | "histogram" | "transactions" | "floor_index" | "regression";

const MAX_COHORT_BUILDINGS = 10;

function defaultBuildingDetailSize(): { width: number; height: number } {
  if (typeof window === "undefined") return { width: 896, height: 640 };
  return {
    width: Math.min(896, window.innerWidth - 32),
    height: Math.min(Math.round(window.innerHeight * 0.85), Math.max(520, window.innerHeight - 48)),
  };
}

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
  const [txExportLoading, setTxExportLoading] = useState(false);
  const [txExportError, setTxExportError] = useState<string | null>(null);
  const [cohortChartMetric, setCohortChartMetric] = useState<CohortTrendMetric>("mean");
  const [longTermMetric, setLongTermMetric] = useState<LongTermPriceMetric>("median");
  const [defaultSize] = useState(defaultBuildingDetailSize);
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
    queryKey: ["b-tx-all", row.building_key, analysisPeriod],
    queryFn: () => fetchAllBuildingTransactions(row.building_key, analysisPeriod),
    enabled: cohortRunForPanel("transactions") === 0 && panel === "transactions",
  });

  const cohortTxQ = useQuery({
    queryKey: ["cohort-tx-all", cohortRunKeys, cohortRunForPanel("transactions"), analysisPeriod],
    queryFn: () => fetchAllCohortTransactions(cohortBody),
    enabled:
      cohortRunForPanel("transactions") > 0 && cohortRunKeys.length > 1 && panel === "transactions",
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

  useEffect(() => {
    setPanel("trend");
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
    <DraggableModalShell
      open={true}
      onClose={onClose}
      titleId="building-detail-modal-title"
      title={row.display_name}
      subtitle={
        <>
          {assetTypeLabel(effectiveAssetType)} · n={row.count.toLocaleString("ko-KR")} · 평균 {fmtPrice(row.mean)}{" "}
          만원/㎡
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
          {experiment && <span className="ml-1.5 text-indigo-600 font-medium">· 실험 모드</span>}
        </>
      }
      headerExtra={
        <>
          <div
            className="flex flex-wrap gap-0.5 rounded-md border modal-tab-bar p-0.5"
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
        </>
      }
      resizable
      zClassName="z-[100]"
      backdropClassName="bg-black/35"
      defaultWidth={defaultSize.width}
      defaultHeight={defaultSize.height}
      maxWidthClass="max-w-4xl"
      minWidth={480}
      minHeight={360}
      bodyClassName="flex-1 min-h-0 overflow-auto px-4 py-3 space-y-4"
    >
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
                  variant="longTerm"
                  priceMetric={longTermMetric}
                  onPriceMetricChange={setLongTermMetric}
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
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                    <p className="text-[10px] text-slate-500 dark:text-slate-400">
                      만년력 연도별 추이 · 롤링 통계 창({periodLabel ?? "5년"})과 기간·표본이 다릅니다.
                    </p>
                    <LongTermMetricToggle metric={longTermMetric} onChange={setLongTermMetric} />
                  </div>
                  <div className="modal-card px-2 py-3">
                    <p className="text-[10px] font-semibold text-slate-600 dark:text-slate-300 px-1 mb-2">추이 (꺾은선)</p>
                    <YearlyTrendChart points={longTermYears} metric={longTermMetric} />
                  </div>
                  <div className="modal-table-wrap">
                    <p className="text-[10px] font-semibold text-slate-600 dark:text-slate-300 px-3 pt-3 pb-1">연도별 수치</p>
                    <table className="w-full text-xs border-collapse modal-inner-table">
                      <thead>
                        <tr>
                          <th className="border px-2 py-1.5 text-left font-medium">연도</th>
                          <th className="border px-2 py-1.5 text-right font-medium">건수</th>
                          <th className="border px-2 py-1.5 text-right font-bold text-blue-700 dark:text-blue-400">
                            {longTermPriceLabel(longTermMetric)}(만원/㎡)
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
                              {yearlyPointPrice(p, longTermMetric) != null ? fmtPrice(yearlyPointPrice(p, longTermMetric)!) : "—"}
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
            <div className="space-y-2 flex flex-col min-h-[360px]">
              {txCohortActive && cohortTxQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-4">코호트 목록 불러오는 중…</p>
              )}
              {txCohortActive && cohortTxQ.isError && (
                <p className="text-xs text-amber-700 text-center py-4">통합 거래 목록을 불러오지 못했습니다.</p>
              )}
              {txCohortActive && cohortTxQ.data && (
                <>
                  <div className="flex flex-wrap items-start justify-between gap-2 shrink-0">
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
                  <CollectiveTransactionTable
                    items={cohortTxQ.data.items}
                    assetType={effectiveAssetType}
                    showBuilding
                    truncated={cohortTxQ.data.truncated}
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
                  <div className="flex flex-wrap items-start justify-between gap-2 shrink-0">
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
                  <CollectiveTransactionTable
                    items={txQ.data.items}
                    assetType={effectiveAssetType}
                    truncated={txQ.data.truncated}
                  />
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
    </DraggableModalShell>
  );
}
