import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { COLLECTIVE_EXPERIMENT_MODE } from "../api/client";
import {
  fetchAllCommercialCohortTransactions,
  fetchAllCommercialTransactions,
  fetchCommercialAddresses,
  fetchCommercialCohortHistogram,
  fetchCommercialHistogram,
  fetchCommercialRollingStats,
  fetchCommercialYearlyStats,
} from "../api/commercialClient";
import {
  commercialAssetTypeLabel,
  type CommercialAssetSelectorType,
  type CommercialAssetType,
  type CommercialClusterRow,
} from "../types";
import { buildAnalysisPeriodParams, formatPeriodLabel } from "../utils/analysisPeriod";
import {
  commercialRollingToTrendSeries,
  commercialYearlyToTrendSeries,
} from "../utils/cohortTrendSeries";
import CohortTrendPanel from "./CohortTrendPanel";
import type { CohortTrendMetric } from "./MultiBuildingTrendChart";
import DraggableModalShell from "./DraggableModalShell";
import HistogramChart from "./HistogramChart";
import CommercialFloorIndexPanel from "./CommercialFloorIndexPanel";
import CommercialRegressionPanel from "./CommercialRegressionPanel";
import CommercialTransactionTable from "./CommercialTransactionTable";
import RollingTrendChart from "./RollingTrendChart";
import YearlyTrendChart, { yearlyPointPrice } from "./YearlyTrendChart";
import LongTermMetricToggle, { longTermPriceLabel, type LongTermPriceMetric } from "./LongTermMetricToggle";
import type { StatsWindowYears } from "./StatsWindowToggle";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import { commercialModalPanelHelp } from "../utils/residentialAnalysisHelp";

const MAX_COHORT_CLUSTERS = 10;

type PanelMode = "trend" | "long_term" | "histogram" | "transactions" | "addresses" | "floor_index" | "regression";

function defaultCommercialDetailSize(): { width: number; height: number } {
  if (typeof window === "undefined") return { width: 896, height: 640 };
  return {
    width: Math.min(896, window.innerWidth - 32),
    height: Math.min(Math.round(window.innerHeight * 0.85), Math.max(520, window.innerHeight - 48)),
  };
}

function fmtPrice(v: number | null | undefined, digits = 1) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function fmtCi(lo: number | null | undefined, hi: number | null | undefined) {
  if (lo == null || hi == null) return "—";
  return `${fmtPrice(lo, 0)}~${fmtPrice(hi, 0)}`;
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
  windowYears = 5,
  periodStart,
  periodEnd,
  statsAsOfLabel,
  peerClusters = [],
  onClose,
}: {
  row: CommercialClusterRow;
  scope: CommercialModalScope;
  windowYears?: StatsWindowYears;
  periodStart?: string | null;
  periodEnd?: string | null;
  statsAsOfLabel?: string | null;
  peerClusters?: CommercialClusterRow[];
  onClose: () => void;
}) {
  const analysisPeriod = useMemo(
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
  const experiment = COLLECTIVE_EXPERIMENT_MODE;
  const [panel, setPanel] = useState<PanelMode>("trend");
  const [cohortExtra, setCohortExtra] = useState<string[]>([]);
  const [cohortRunKeys, setCohortRunKeys] = useState<string[]>([]);
  const [cohortRunByPanel, setCohortRunByPanel] = useState<Partial<Record<PanelMode, number>>>({});
  const [cohortChartMetric, setCohortChartMetric] = useState<CohortTrendMetric>("mean");
  const [longTermMetric, setLongTermMetric] = useState<LongTermPriceMetric>("mean");
  const [histScope, setHistScope] = useState<"all" | "single">("all");
  const [histYear, setHistYear] = useState<number | null>(null);
  const [defaultSize] = useState(defaultCommercialDetailSize);

  const region = regionParams(scope);
  const scopeKey = { ...region, ...analysisPeriod };

  const effectiveAssetType = (
    scope.assetType === "all" || scope.assetType.includes(",")
      ? row.asset_type
      : scope.assetType
  ) as CommercialAssetType;
  const isShop = effectiveAssetType === "collective_shop";

  const cohortKeys = useMemo(
    () => [row.cluster_key, ...cohortExtra.filter((k) => k !== row.cluster_key)].slice(0, MAX_COHORT_CLUSTERS),
    [row.cluster_key, cohortExtra],
  );
  const cohortStale =
    Object.keys(cohortRunByPanel).length > 0 &&
    (cohortRunKeys.length !== cohortKeys.length || cohortRunKeys.some((k, i) => k !== cohortKeys[i]));
  const canRunCohort = cohortKeys.length > 1;
  const cohortRunForPanel = (p: PanelMode) => (cohortStale ? 0 : cohortRunByPanel[p] ?? 0);
  const cohortBody = useMemo(
    () => ({
      cluster_keys: cohortRunKeys,
      asset_type:
        scope.assetType === "all" || scope.assetType.includes(",")
          ? undefined
          : effectiveAssetType,
      experiment,
      ...analysisPeriod,
    }),
    [cohortRunKeys, scope.assetType, effectiveAssetType, experiment, analysisPeriod],
  );
  const peerOptions = useMemo(
    () => peerClusters.filter((c) => c.cluster_key !== row.cluster_key && !cohortExtra.includes(c.cluster_key)),
    [peerClusters, row.cluster_key, cohortExtra],
  );

  const tabs: { id: PanelMode; label: string; shopOnly?: boolean }[] = useMemo(
    () => [
      { id: "trend", label: "롤링 구간" },
      { id: "histogram", label: "단가 분포" },
      { id: "transactions", label: "거래 목록" },
      ...(isShop ? [{ id: "addresses" as const, label: "번지별 요약", shopOnly: true }] : []),
      { id: "floor_index", label: "층·면적 효용지수" },
      { id: "regression", label: "회귀 분석" },
      { id: "long_term", label: "장기 추세" },
    ],
    [isShop],
  );

  const rollingQ = useQuery({
    queryKey: ["comm-rolling", row.cluster_key, windowYears],
    queryFn: () => fetchCommercialRollingStats(row.cluster_key, windowYears),
    enabled: cohortRunForPanel("trend") === 0 && panel === "trend",
  });

  const longTermYearQ = useQuery({
    queryKey: ["comm-year-long", row.cluster_key],
    queryFn: () => fetchCommercialYearlyStats(row.cluster_key),
    enabled: cohortRunForPanel("long_term") === 0 && panel === "long_term",
  });

  const windowYearQ = useQuery({
    queryKey: ["comm-year-window", row.cluster_key, analysisPeriod],
    queryFn: () =>
      fetchCommercialYearlyStats(row.cluster_key, {
        ...analysisPeriod,
      }),
    enabled: cohortRunForPanel("histogram") === 0 && panel === "histogram",
  });

  const sortedYears = useMemo(
    () => [...(windowYearQ.data?.points ?? [])].sort((a, b) => a.year - b.year),
    [windowYearQ.data?.points],
  );

  const cohortRollingQ = useQuery({
    queryKey: ["comm-cohort-rolling", cohortRunKeys, windowYears, cohortRunForPanel("trend")],
    queryFn: async () => Promise.all(cohortRunKeys.map((k) => fetchCommercialRollingStats(k, windowYears))),
    enabled: cohortRunForPanel("trend") > 0 && cohortRunKeys.length > 1 && panel === "trend",
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

  const histQ = useQuery({
    queryKey: ["comm-hist", row.cluster_key, scopeKey, histScope, histScope === "single" ? histYear : null],
    queryFn: () =>
      fetchCommercialHistogram(row.cluster_key, {
        ...region,
        ...analysisPeriod,
        contract_year: histScope === "single" && histYear != null ? histYear : undefined,
      }),
    enabled: cohortRunForPanel("histogram") === 0 && panel === "histogram",
  });

  const txQ = useQuery({
    queryKey: ["comm-tx-all", row.cluster_key, scopeKey, analysisPeriod],
    queryFn: () =>
      fetchAllCommercialTransactions(row.cluster_key, {
        ...region,
        ...analysisPeriod,
        window_years: analysisPeriod.contract_date_from ? undefined : windowYears,
      }),
    enabled: cohortRunForPanel("transactions") === 0 && panel === "transactions",
  });

  const cohortTxQ = useQuery({
    queryKey: ["comm-cohort-tx-all", cohortRunKeys, cohortRunForPanel("transactions"), analysisPeriod],
    queryFn: () => fetchAllCommercialCohortTransactions(cohortBody),
    enabled:
      cohortRunForPanel("transactions") > 0 && cohortRunKeys.length > 1 && panel === "transactions",
  });

  const addrQ = useQuery({
    queryKey: ["comm-addr-modal", row.cluster_key, scopeKey],
    queryFn: () => fetchCommercialAddresses(row.cluster_key, { ...region, ...analysisPeriod }),
    enabled: isShop && panel === "addresses",
  });

  useEffect(() => {
    if (sortedYears.length && histYear == null) {
      setHistYear(sortedYears[sortedYears.length - 1].year);
    }
  }, [sortedYears, histYear]);

  useEffect(() => {
    setPanel("trend");
    setHistScope("all");
    setHistYear(null);
    setCohortExtra([]);
    setCohortRunKeys([]);
    setCohortRunByPanel({});
    setCohortChartMetric("mean");
  }, [row.cluster_key]);

  const runCohortAnalysis = () => {
    if (!canRunCohort) return;
    setCohortRunKeys([...cohortKeys]);
    setCohortRunByPanel((prev) => ({ ...prev, [panel]: (prev[panel] ?? 0) + 1 }));
  };

  const addToCohort = (clusterKey: string) => {
    if (cohortKeys.length >= MAX_COHORT_CLUSTERS) return;
    setCohortExtra((prev) => (prev.includes(clusterKey) ? prev : [...prev, clusterKey]));
  };

  const trendCohortActive = cohortRunForPanel("trend") > 0;
  const longTermCohortActive = cohortRunForPanel("long_term") > 0;
  const histCohortActive = cohortRunForPanel("histogram") > 0;
  const txCohortActive = cohortRunForPanel("transactions") > 0;

  const activeTxQ = txCohortActive ? cohortTxQ : txQ;
  const label = row.road_name || row.display_label;

  return (
    <DraggableModalShell
      open={true}
      onClose={onClose}
      titleId="commercial-cluster-detail-modal-title"
      title={label}
      subtitle={
        <>
          {commercialAssetTypeLabel(effectiveAssetType)} · n={row.count.toLocaleString("ko-KR")} · 평균{" "}
          {fmtPrice(row.mean, 0)} 만원/㎡
          {[row.addr3, row.addr4].filter(Boolean).length > 0 && (
            <> · {[row.addr3, row.addr4].filter(Boolean).join(" ")}</>
          )}
          {!row.is_reliable && <span className="ml-1 text-amber-600">· n&lt;15</span>}
        </>
      }
      headerExtra={
        <>
          <div
            className="flex flex-wrap gap-0.5 rounded-md border border-slate-200 bg-slate-50 p-0.5"
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
          {(() => {
            const help = commercialModalPanelHelp(panel);
            return help ? <AnalysisHelpPanel explain={help} className="ml-1" /> : null;
          })()}
          {peerClusters.length > 0 && (
            <div className="mt-2 rounded border border-indigo-100 bg-indigo-50/50 px-2 py-1.5 text-[10px]">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-indigo-800">분석 코호트</span>
                <span className="text-slate-600">
                  {cohortKeys.length === 1 ? "단일 cluster" : `${cohortKeys.length}개 cluster`}
                </span>
                {canRunCohort && (
                  <button
                    type="button"
                    className="ml-auto px-2 py-0.5 rounded bg-indigo-700 text-white text-[10px] font-semibold hover:bg-indigo-800"
                    onClick={runCohortAnalysis}
                  >
                    통합분석
                  </button>
                )}
              </div>
              {cohortStale && (
                <p className="mt-1 text-amber-700">코호트가 변경되었습니다. 「통합분석」을 다시 실행하세요.</p>
              )}
              {cohortExtra.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {cohortExtra.map((k) => {
                    const peerLabel =
                      peerClusters.find((c) => c.cluster_key === k)?.road_name ||
                      peerClusters.find((c) => c.cluster_key === k)?.display_label ||
                      k.slice(0, 8);
                    return (
                      <button
                        key={k}
                        type="button"
                        className="px-1.5 py-0.5 rounded bg-white border border-indigo-200 text-indigo-700"
                        onClick={() => setCohortExtra((prev) => prev.filter((x) => x !== k))}
                      >
                        {peerLabel} ×
                      </button>
                    );
                  })}
                </div>
              )}
              {peerOptions.length > 0 && (
                <label className="mt-1 flex items-center gap-1 text-slate-600">
                  <span>+ cluster 추가</span>
                  <select
                    className="text-[10px] border border-slate-200 rounded px-1 py-0.5 max-w-[180px]"
                    defaultValue=""
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v) addToCohort(v);
                      e.target.value = "";
                    }}
                    disabled={cohortKeys.length >= MAX_COHORT_CLUSTERS}
                  >
                    <option value="">선택…</option>
                    {peerOptions.slice(0, 80).map((c) => (
                      <option key={c.cluster_key} value={c.cluster_key}>
                        {c.road_name || c.display_label} (n={c.count})
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
              {trendCohortActive && cohortRollingQ.data && (
                <CohortTrendPanel
                  series={cohortRollingQ.data.map(commercialRollingToTrendSeries)}
                  metric={cohortChartMetric}
                  onMetricChange={setCohortChartMetric}
                  buildingCount={cohortRunKeys.length}
                  chartTitle={`${windowYears}년 롤링 구간 · 평균 ㎡당 단가`}
                  note={
                    cohortRollingQ.data[0]?.stats_as_of_label
                      ? `${cohortRollingQ.data[0].stats_as_of_label} · ${windowYears}년 창`
                      : undefined
                  }
                />
              )}
              {!trendCohortActive && rollingQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-6">롤링 구간 집계 중…</p>
              )}
              {!trendCohortActive && rollingQ.data && rollingQ.data.points.length > 0 && (
                <>
                  {(rollingQ.data.stats_as_of_label || statsAsOfLabel || periodLabel) && (
                    <p className="text-[10px] text-indigo-700 bg-indigo-50 border border-indigo-100 rounded px-2 py-1">
                      {rollingQ.data.stats_as_of_label || statsAsOfLabel}
                      {windowYears ? ` · ${windowYears}년 창` : ""}
                      {periodLabel ? ` · ${periodLabel}` : ""}
                    </p>
                  )}
                  <div className="rounded-lg border border-slate-100 bg-slate-50/60 px-2 py-3">
                    <p className="text-[10px] font-semibold text-slate-600 px-1 mb-2">12개월 롤링 구간 추이</p>
                    <RollingTrendChart points={rollingQ.data.points} />
                  </div>
                  <div className="rounded-lg border border-slate-100 bg-white overflow-hidden">
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
                        {[...rollingQ.data.points].sort((a, b) => a.bucket_index - b.bucket_index).map((p) => (
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
              {!trendCohortActive && rollingQ.data && rollingQ.data.points.length === 0 && (
                <p className="text-xs text-slate-400 text-center py-6">표시할 롤링 구간 데이터가 없습니다.</p>
              )}
            </>
          )}

          {panel === "long_term" && (
            <>
              {longTermCohortActive && cohortLongTermQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-6">코호트 장기 추세 집계 중…</p>
              )}
              {longTermCohortActive && cohortLongTermQ.data && (
                <CohortTrendPanel
                  series={cohortLongTermQ.data.map(commercialYearlyToTrendSeries)}
                  metric={cohortChartMetric}
                  onMetricChange={setCohortChartMetric}
                  buildingCount={cohortRunKeys.length}
                  chartTitle="연도별 장기 추세"
                  variant="longTerm"
                  priceMetric={longTermMetric}
                  onPriceMetricChange={setLongTermMetric}
                />
              )}
              {!longTermCohortActive && longTermYearQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-6">장기 추세 집계 중…</p>
              )}
              {!longTermCohortActive && longTermYearQ.data && longTermYearQ.data.points.length > 0 && (
                <>
                  {longTermYearQ.data.points.some((p) => p.year < 2021) && (
                    <p className="text-[10px] text-indigo-600 mb-1">
                      2010–2020 구간 포함 · {longTermYearQ.data.data_source === "mart" ? "annual mart" : "실시간 집계"}
                    </p>
                  )}
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                    <p className="text-[10px] text-slate-500">만년력 연도별 장기 추세</p>
                    <LongTermMetricToggle metric={longTermMetric} onChange={setLongTermMetric} />
                  </div>
                  <div className="rounded-lg border border-slate-100 bg-slate-50/60 px-2 py-3">
                    <p className="text-[10px] font-semibold text-slate-600 px-1 mb-2">연도별 장기 추세</p>
                    <YearlyTrendChart
                      points={[...longTermYearQ.data.points].sort((a, b) => a.year - b.year)}
                      metric={longTermMetric}
                    />
                  </div>
                  <div className="rounded-lg border border-slate-100 bg-white overflow-hidden">
                    <table className="w-full text-xs border-collapse">
                      <thead>
                        <tr className="bg-slate-50 text-slate-600">
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">연도</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">건수</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-blue-700">
                            {longTermPriceLabel(longTermMetric)}(만원/㎡)
                          </th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-800">
                        {[...longTermYearQ.data.points].sort((a, b) => a.year - b.year).map((p) => (
                          <tr key={p.year}>
                            <td className="border border-slate-200 px-2 py-1 tabular-nums">{p.year}</td>
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                              {p.count.toLocaleString("ko-KR")}
                            </td>
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-blue-600 font-bold">
                              {yearlyPointPrice(p, longTermMetric) != null ? fmtPrice(yearlyPointPrice(p, longTermMetric)!) : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
              {!longTermCohortActive && longTermYearQ.data && longTermYearQ.data.points.length === 0 && (
                <p className="text-xs text-slate-400 text-center py-6">표시할 장기 추세 데이터가 없습니다.</p>
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
              {histQ.isLoading && !histCohortActive && <p className="text-xs text-slate-400 text-center py-4">분포 계산 중…</p>}
              {histCohortActive && cohortHistQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-4">코호트 분포 계산 중…</p>
              )}
              {histCohortActive && cohortHistQ.data && (
                <>
                  <p className="text-[10px] text-indigo-700">
                    {cohortRunKeys.length}개 cluster 통합 · 실시간 · n={cohortHistQ.data.n.toLocaleString("ko-KR")}건
                  </p>
                  <div className="rounded-lg border border-slate-100 bg-slate-50/60 px-2 py-2">
                    <HistogramChart bins={cohortHistQ.data.bins} />
                  </div>
                </>
              )}
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
              {activeTxQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-4">목록 불러오는 중…</p>
              )}
              {activeTxQ.isError && (
                <p className="text-xs text-red-500 text-center py-4">목록을 불러오지 못했습니다.</p>
              )}
              {activeTxQ.data && (
                <>
                  <p className="text-[10px] text-slate-500 shrink-0">
                    {txCohortActive && (
                      <span className="text-indigo-700 mr-1">{cohortRunKeys.length}개 cluster 통합 ·</span>
                    )}
                    전체 <strong className="text-slate-700">{activeTxQ.data.total.toLocaleString("ko-KR")}</strong>건
                    {(scope.yearFrom !== "" || scope.yearTo !== "") && (
                      <>
                        {" "}
                        · 연도 {scope.yearFrom || "…"}–{scope.yearTo || "…"}
                      </>
                    )}
                  </p>
                  <CommercialTransactionTable
                    items={activeTxQ.data.items}
                    isShop={isShop}
                    truncated={activeTxQ.data.truncated}
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
              scope={scope}
              count={row.count}
              isFactory={!isShop}
              cohortKeys={cohortRunKeys}
              cohortRunId={cohortRunForPanel("floor_index")}
              analysisPeriod={analysisPeriod}
            />
          )}

          {panel === "regression" && (
            <CommercialRegressionPanel
              clusterKey={row.cluster_key}
              scope={scope}
              isShop={isShop}
              count={row.count}
              cohortKeys={cohortRunKeys}
              cohortRunId={cohortRunForPanel("regression")}
              analysisPeriod={analysisPeriod}
            />
          )}
    </DraggableModalShell>
  );
}
