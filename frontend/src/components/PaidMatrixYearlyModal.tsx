import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  fetchLongTermTrend,
  fetchMatrixCellHistogram,
  fetchMatrixCellTransactions,
  fetchLandRegression,
  downloadMatrixCellTransactionsCsv,
} from "../api/client";
import { simpleTableHeadClass } from "../constants/displayUi";
import type {
  LandRegressionVariables,
  LandRegressionResponse,
  LandRegressionCoeff,
  LongTermTrendPoint,
  LongTermTrendResponse,
  MatrixCellHistogramRequest,
  MatrixCellHistogramResponse,
  MatrixCellTransactionsResponse,
  MatrixCellTransactionItem,
  MatrixYearlyRequest,
  MatrixYearlyStat,
} from "../types";
import { parseApiError, parseApiErrorAsync } from "../utils/apiError";
import { formatMatrixBucketAxisLabel } from "../utils/matrixYearlyLabels";
import { resolveLongTermTargetsForFetch } from "../utils/longTermTargets";
import { useAppStore } from "../store";
import MatrixCellHistogramChart from "./MatrixCellHistogramChart";
import MatrixYearlyTrendChart from "./MatrixYearlyTrendChart";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import { buildLongTermTrendExplain } from "../constants/longTermTrendExplain";
import {
  buildHistogramExplain,
  buildMatrixCellTrendExplain,
  buildTransactionListExplain,
} from "../constants/landStatsExplain";

function sortMatrixRows(rows: MatrixYearlyStat[]): MatrixYearlyStat[] {
  return [...rows].sort((a, b) => {
    const ka =
      a.bucket_index != null && Number.isFinite(Number(a.bucket_index))
        ? Number(a.bucket_index)
        : a.year ?? 0;
    const kb =
      b.bucket_index != null && Number.isFinite(Number(b.bucket_index))
        ? Number(b.bucket_index)
        : b.year ?? 0;
    return ka - kb;
  });
}

function detectRollingBucketRows(rows: MatrixYearlyStat[]): boolean {
  return rows.some(
    (r) => r.bucket_index != null && Number.isFinite(Number(r.bucket_index)),
  );
}

function formatIsoDateBrief(d: string | null | undefined): string {
  if (!d || typeof d !== "string") return "";
  const t = d.slice(0, 10);
  return t || d;
}

function formatTxContractDate(r: MatrixCellTransactionItem): string {
  const brief = formatIsoDateBrief(r.contract_date ?? undefined);
  if (brief) return brief;
  return `${r.contract_year}.${String(r.contract_month).padStart(2, "0")}`;
}

function formatTxCell(value: string | null | undefined): string {
  const t = (value ?? "").trim();
  return t || "—";
}

function rowStableKey(r: MatrixYearlyStat, idx: number): string {
  if (r.bucket_index != null && Number.isFinite(Number(r.bucket_index))) {
    return `b:${r.bucket_index}`;
  }
  if (r.year != null) return `y:${r.year}`;
  return `i:${idx}`;
}

interface Props {
  open: boolean;
  onClose: () => void;
  loading: boolean;
  error: string | null;
  zoneType: string;
  landCategory: string;
  rows: MatrixYearlyStat[];
  /** matrix-yearly 호출과 동일한 필터 본문 (분포·원데이터 API 재사용) */
  filterRequest: MatrixYearlyRequest | null;
  /** 적용 범위 안내(기본: 필터 분석 기준 문구) */
  scopeNote?: string;
}

type PanelMode = "trend" | "longTerm" | "histogram" | "transactions" | "regression";
type LtPriceMetric = "mean" | "median";

function ltPointsToChartRows(
  points: LongTermTrendPoint[],
  metric: LtPriceMetric,
): MatrixYearlyStat[] {
  return [...points]
    .sort((a, b) => a.year - b.year)
    .map((p) => ({
      year: p.year,
      bucket_index: null,
      period_start: null,
      period_end: null,
      chart_label: null,
      count: p.count,
      mean_unit_price_per_sqm:
        metric === "median" ? (p.median ?? null) : (p.mean ?? null),
    }));
}

const TX_PAGE = 25;

/** 유료 매트릭스 칸: 연도별 추이 + 단가 분포 + 원거래 목록 */
export default function PaidMatrixYearlyModal({
  open,
  onClose,
  loading,
  error,
  zoneType,
  landCategory,
  rows,
  filterRequest,
  scopeNote,
}: Props) {
  const [panel, setPanel] = useState<PanelMode>("trend");
  const [histScope, setHistScope] = useState<"all" | "single">("all");
  /** calendar year 또는 롤링 bucket_index (histogram single 대상 키) */
  const [histSliceKey, setHistSliceKey] = useState<number | null>(null);
  const [histLoading, setHistLoading] = useState(false);
  const [histError, setHistError] = useState<string | null>(null);
  const [histData, setHistData] = useState<MatrixCellHistogramResponse | null>(null);

  const [txOffset, setTxOffset] = useState(0);
  const [txLoading, setTxLoading] = useState(false);
  const [txError, setTxError] = useState<string | null>(null);
  const [txData, setTxData] = useState<MatrixCellTransactionsResponse | null>(null);

  // 회귀 탭 state
  const [regVars, setRegVars] = useState<LandRegressionVariables>({
    area_sqm: true,
    log_area: true,
    road_condition: true,
    deal_type: true,
    partial_ownership: false,
    year_trend: true,
    beopjungri_fe: false,
  });
  const [regModelType, setRegModelType] = useState<"log" | "linear">("log");
  const [regExcludeOutlier, setRegExcludeOutlier] = useState(false);
  const [regLoading, setRegLoading] = useState(false);
  const [regError, setRegError] = useState<string | null>(null);
  const [regResult, setRegResult] = useState<LandRegressionResponse | null>(null);
  const [txExportLoading, setTxExportLoading] = useState(false);
  const [txExportError, setTxExportError] = useState<string | null>(null);

  const [ltLoading, setLtLoading] = useState(false);
  const [ltError, setLtError] = useState<string | null>(null);
  const [ltData, setLtData] = useState<LongTermTrendResponse | null>(null);
  const [ltMetric, setLtMetric] = useState<LtPriceMetric>("median");

  /** 모달 드래그 이동 (헤더 잡고 끌기) */
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const dragSession = useRef<{
    startX: number;
    startY: number;
    baseX: number;
    baseY: number;
  } | null>(null);

  useEffect(() => {
    if (open) {
      setDragOffset({ x: 0, y: 0 });
      dragSession.current = null;
    }
  }, [open, zoneType, landCategory]);

  const onDragMove = useCallback((e: MouseEvent) => {
    const s = dragSession.current;
    if (!s) return;
    setDragOffset({
      x: s.baseX + (e.clientX - s.startX),
      y: s.baseY + (e.clientY - s.startY),
    });
  }, []);

  const onDragEnd = useCallback(() => {
    dragSession.current = null;
    window.removeEventListener("mousemove", onDragMove);
    window.removeEventListener("mouseup", onDragEnd);
  }, [onDragMove]);

  const onHeaderMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (e.button !== 0) return;
      const target = e.target as HTMLElement;
      if (target.closest("button")) return;
      e.preventDefault();
      dragSession.current = {
        startX: e.clientX,
        startY: e.clientY,
        baseX: dragOffset.x,
        baseY: dragOffset.y,
      };
      window.addEventListener("mousemove", onDragMove);
      window.addEventListener("mouseup", onDragEnd);
    },
    [dragOffset.x, dragOffset.y, onDragMove, onDragEnd],
  );

  useEffect(
    () => () => {
      window.removeEventListener("mousemove", onDragMove);
      window.removeEventListener("mouseup", onDragEnd);
    },
    [onDragMove, onDragEnd],
  );

  useEffect(() => {
    if (open) {
      setPanel("trend");
      setHistScope("all");
      setHistSliceKey(null);
      setHistData(null);
      setHistError(null);
      setTxOffset(0);
      setTxData(null);
      setTxError(null);
      setLtData(null);
      setLtError(null);
      setLtMetric("median");
    }
  }, [open, zoneType, landCategory]);

  const sortedRows = useMemo(() => sortMatrixRows(rows), [rows]);

  const isRolling = useMemo(
    () =>
      Boolean(
        (filterRequest?.rolling_matrix_period_end &&
          filterRequest?.rolling_bucket_count != null &&
          filterRequest.rolling_bucket_count > 0) ||
          detectRollingBucketRows(rows),
      ),
    [filterRequest, rows],
  );

  /** 만년력 연도(필터 분석)에서만 장기 추세 — 기본통계 롤링 창과 기간 축이 다름 */
  const showLongTermTab = !isRolling;

  useEffect(() => {
    if (!showLongTermTab && panel === "longTerm") {
      setPanel("trend");
    }
  }, [showLongTermTab, panel]);

  useEffect(() => {
    if (sortedRows.length === 0) return;
    const keys = sortedRows
      .map((r) => (isRolling ? r.bucket_index : r.year))
      .filter((k): k is number => typeof k === "number" && Number.isFinite(k));
    if (keys.length === 0) return;
    setHistSliceKey((prev) => {
      if (prev != null && keys.includes(prev)) return prev;
      return keys[0]!;
    });
  }, [sortedRows, isRolling]);

  const tierSelection = useAppStore((s) => s.tierSelection);

  useEffect(() => {
    if (!open || panel !== "longTerm" || !filterRequest) return;
    const targets = resolveLongTermTargetsForFetch(
      tierSelection,
      filterRequest.region_codes ?? [],
    );
    if (targets.length === 0) {
      setLtError("장기 추세는 지역 코드가 필요합니다.");
      setLtData(null);
      return;
    }
    let cancelled = false;
    setLtLoading(true);
    setLtError(null);
    setLtData(null);
    (async () => {
      try {
        const data = await fetchLongTermTrend({
          region_targets: targets,
          zone_type: zoneType,
          land_category: landCategory,
        });
        if (!cancelled) setLtData(data);
      } catch (e) {
        if (!cancelled) {
          setLtData(null);
          setLtError(parseApiError(e).message);
        }
      } finally {
        if (!cancelled) setLtLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, panel, filterRequest, zoneType, landCategory, tierSelection]);

  useEffect(() => {
    if (!open || panel !== "histogram" || !filterRequest) return;
    const sliceKeyForReq =
      histScope === "single"
        ? isRolling
          ? histSliceKey ?? sortedRows[0]?.bucket_index ?? null
          : histSliceKey ?? sortedRows[0]?.year ?? null
        : null;
    if (histScope === "single" && sliceKeyForReq == null) return;

    let cancelled = false;
    (async () => {
      setHistLoading(true);
      setHistError(null);
      try {
        const body: MatrixCellHistogramRequest = {
          ...filterRequest,
          histogram_scope: histScope,
          bin_count: 20,
        };
        if (histScope === "all") {
          body.histogram_year = null;
          body.histogram_bucket_index = null;
        } else if (isRolling) {
          body.histogram_bucket_index = sliceKeyForReq;
          body.histogram_year = null;
        } else {
          body.histogram_year = sliceKeyForReq;
          body.histogram_bucket_index = null;
        }
        const data = await fetchMatrixCellHistogram(body);
        if (!cancelled) setHistData(data);
      } catch (e) {
        if (!cancelled) {
          setHistData(null);
          setHistError(parseApiError(e).message);
        }
      } finally {
        if (!cancelled) setHistLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, panel, filterRequest, histScope, histSliceKey, isRolling, sortedRows]);

  useEffect(() => {
    if (!open || panel !== "transactions" || !filterRequest) return;
    let cancelled = false;
    (async () => {
      setTxLoading(true);
      setTxError(null);
      try {
        const data = await fetchMatrixCellTransactions({
          ...filterRequest,
          offset: txOffset,
          limit: TX_PAGE,
        });
        if (!cancelled) setTxData(data);
      } catch (e) {
        if (!cancelled) {
          setTxData(null);
          setTxError(parseApiError(e).message);
        }
      } finally {
        if (!cancelled) setTxLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, panel, filterRequest, txOffset]);

  useEffect(() => {
    if (panel !== "transactions") return;
    setTxOffset(0);
    setTxExportError(null);
  }, [panel, filterRequest]);

  const handleTxExport = useCallback(async () => {
    if (!filterRequest) return;
    setTxExportLoading(true);
    setTxExportError(null);
    try {
      await downloadMatrixCellTransactionsCsv(filterRequest);
    } catch (e) {
      const parsed = await parseApiErrorAsync(e);
      setTxExportError(parsed.message);
    } finally {
      setTxExportLoading(false);
    }
  }, [filterRequest]);

  const canDetail = Boolean(filterRequest) && !loading && !error && rows.length > 0;

  const detailTabs = useMemo(() => {
    const tabs: { id: PanelMode; label: string }[] = [
      { id: "trend", label: isRolling ? "롤링 구간" : "선택 연도" },
      { id: "histogram", label: "단가 분포" },
      { id: "transactions", label: "거래 목록" },
      { id: "regression", label: "회귀 분석" },
    ];
    if (showLongTermTab) {
      tabs.push({ id: "longTerm", label: "장기 추세" });
    }
    return tabs;
  }, [isRolling, showLongTermTab]);

  const ltPriceLabel = ltMetric === "median" ? "중앙값" : "평균";

  const ltExplain = useMemo(() => {
    if (!showLongTermTab || !filterRequest) return null;
    const targets = resolveLongTermTargetsForFetch(
      tierSelection,
      filterRequest.region_codes ?? [],
    );
    let referenceOnlyYears = 0;
    if (ltData) {
      const refYears = new Set<number>();
      for (const s of ltData.series) {
        for (const p of s.points) {
          if (p.reference_only) refYears.add(p.year);
        }
      }
      referenceOnlyYears = refYears.size;
    }
    return buildLongTermTrendExplain({
      zoneType,
      landCategory,
      metric: ltMetric,
      targets,
      yearFrom: ltData?.year_from,
      yearTo: ltData?.year_to,
      seriesCount: ltData?.series.length ?? targets.length,
      referenceOnlyYears,
    });
  }, [
    showLongTermTab,
    filterRequest,
    tierSelection,
    zoneType,
    landCategory,
    ltMetric,
    ltData,
  ]);

  const histogramRollingBucketLabel =
    histData?.histogram_bucket_index != null
      ? (() => {
          const bi = histData.histogram_bucket_index;
          const rm = sortedRows.find(
            (r) => r.bucket_index != null && r.bucket_index === bi,
          );
          return rm ? formatMatrixBucketAxisLabel(rm) : `버킷 ${bi}`;
        })()
      : null;

  const trendExplain = useMemo(
    () => buildMatrixCellTrendExplain(isRolling),
    [isRolling],
  );
  const histogramExplain = useMemo(() => buildHistogramExplain(), []);
  const txExplain = useMemo(
    () =>
      filterRequest
        ? buildTransactionListExplain({
            zoneType,
            landCategory,
            total: txData?.total,
            excludeOutlier: filterRequest.exclude_outlier,
            outlierMultiplier: filterRequest.outlier_iqr_multiplier,
          })
        : null,
    [
      filterRequest,
      zoneType,
      landCategory,
      txData?.total,
    ],
  );

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[130] bg-black/35"
      role="dialog"
      aria-modal="true"
      aria-labelledby="paid-matrix-yearly-title"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="fixed left-1/2 top-1/2 bg-white rounded-xl shadow-xl max-w-4xl w-[calc(100%-2rem)] max-h-[85vh] flex flex-col border border-slate-200"
        style={{
          transform: `translate(calc(-50% + ${dragOffset.x}px), calc(-50% + ${dragOffset.y}px))`,
        }}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div
          className="flex justify-between items-start gap-2 px-4 py-3 border-b border-slate-100 cursor-move select-none"
          onMouseDown={onHeaderMouseDown}
        >
          <div className="min-w-0 flex-1">
            <h2 id="paid-matrix-yearly-title" className="text-sm font-bold text-slate-800">
              {isRolling ? "롤링 구간별 평균 변동" : "연도별 평균 변동"}
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">
              용도 <span className="font-semibold text-slate-700">{zoneType}</span> · 지목{" "}
              <span className="font-semibold text-slate-700">{landCategory}</span>
              {scopeNote ? (
                <span className="block text-[10px] mt-1 text-slate-400">{scopeNote}</span>
              ) : null}
            </p>
            {canDetail && (
              <div
                className="mt-2 inline-flex flex-wrap rounded-md border border-slate-200 bg-slate-50 p-0.5 gap-0.5"
                role="tablist"
                aria-label="보기 형식"
              >
                {detailTabs.map(({ id, label }) => (
                  <button
                    key={id}
                    type="button"
                    role="tab"
                    aria-selected={panel === id}
                    className={`px-2.5 py-1 text-[11px] font-medium rounded transition-colors ${
                      panel === id
                        ? "bg-white text-slate-800 shadow-sm border border-slate-100"
                        : "text-slate-500 hover:text-slate-700"
                    }`}
                    onClick={() => setPanel(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button
            type="button"
            aria-label="닫기"
            className="shrink-0 text-slate-400 hover:text-slate-700 text-xl leading-none px-1"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <div className="flex-1 overflow-auto px-4 py-3 space-y-4">
          {loading && (
            <p className="text-xs text-slate-400 text-center py-6">
              {isRolling ? "구간별 집계 중…" : "연도별 집계 중…"}
            </p>
          )}
          {error && (
            <p className="text-xs text-red-500 text-center py-6">{error}</p>
          )}
          {!loading && !error && rows.length === 0 && (
            <p className="text-xs text-slate-400 text-center py-6">
              {isRolling ? "표시할 구간별 데이터가 없습니다." : "표시할 연도별 데이터가 없습니다."}
            </p>
          )}

          {canDetail && showLongTermTab && panel === "longTerm" && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="text-[11px] text-amber-900 bg-amber-50 border border-amber-200 rounded-md px-2 py-1.5 leading-relaxed flex-1 min-w-[12rem]">
                  {ltData?.disclaimer ??
                    "장기 추세: 만년력 연도·용도×지목 기준 · 도로·면적·이상치·지분 필터 미적용 · 지역별 선 분리"}
                </p>
                <div className="flex items-center gap-2 shrink-0">
                  <AnalysisHelpPanel explain={ltExplain} />
                  <div
                    className="inline-flex rounded-md border border-slate-200 bg-slate-50 p-0.5"
                    role="group"
                    aria-label="추세선 기준"
                  >
                  {(
                    [
                      ["median", "중앙값"],
                      ["mean", "평균"],
                    ] as const
                  ).map(([id, label]) => (
                    <button
                      key={id}
                      type="button"
                      aria-pressed={ltMetric === id}
                      className={`px-2.5 py-1 text-[11px] font-medium rounded transition-colors ${
                        ltMetric === id
                          ? "bg-white text-slate-800 shadow-sm border border-slate-100"
                          : "text-slate-500 hover:text-slate-700"
                      }`}
                      onClick={() => setLtMetric(id)}
                    >
                      {label}
                    </button>
                  ))}
                  </div>
                </div>
              </div>
              {ltLoading && (
                <p className="text-xs text-slate-400 text-center py-6">장기 추세 불러오는 중…</p>
              )}
              {ltError && (
                <p className="text-xs text-red-500 text-center py-6">{ltError}</p>
              )}
              {!ltLoading && !ltError && ltData && ltData.series.length === 0 && (
                <p className="text-xs text-slate-400 text-center py-6">
                  표시할 장기 추세 데이터가 없습니다.
                </p>
              )}
              {!ltLoading &&
                !ltError &&
                ltData?.series.map((s) => {
                  const chartRows = ltPointsToChartRows(s.points, ltMetric);
                  if (chartRows.length === 0) return null;
                  return (
                    <div key={`${s.region_level}:${s.region_code}`} className="space-y-2">
                      <p className="text-[11px] font-semibold text-slate-700">
                        {s.region_name}{" "}
                        <span className="font-normal text-slate-400">
                          ({ltData.year_from}–{ltData.year_to} · {ltPriceLabel})
                        </span>
                      </p>
                      <div className="rounded-lg border border-slate-100 bg-slate-50/60 px-2 py-3 overflow-x-auto">
                        <MatrixYearlyTrendChart rows={chartRows} xSpacingScale={1.5} />
                      </div>
                      <div className="rounded-lg border border-slate-100 bg-white overflow-hidden">
                        <table className="w-full text-xs border-collapse">
                          <thead>
                            <tr className={simpleTableHeadClass("neutral")}>
                              <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">
                                연도
                              </th>
                              <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">
                                건수
                              </th>
                              <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-blue-700">
                                {ltPriceLabel}(만원/㎡)
                              </th>
                            </tr>
                          </thead>
                          <tbody className="text-slate-800">
                            {chartRows.map((r) => (
                              <tr
                                key={`${s.region_code}-${r.year}`}
                                className={
                                  s.points.find((p) => p.year === r.year)?.reference_only
                                    ? "opacity-60"
                                    : undefined
                                }
                              >
                                <td className="border border-slate-200 px-2 py-1 tabular-nums">
                                  {r.year}
                                  {s.points.find((p) => p.year === r.year)?.reference_only ? (
                                    <span className="ml-1 text-[10px] text-amber-700">참고</span>
                                  ) : null}
                                </td>
                                <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                                  {r.count.toLocaleString("ko-KR")}
                                </td>
                                <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-blue-600 font-bold">
                                  {r.mean_unit_price_per_sqm != null
                                    ? Number(r.mean_unit_price_per_sqm).toLocaleString("ko-KR", {
                                        minimumFractionDigits: 1,
                                        maximumFractionDigits: 1,
                                      })
                                    : "—"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  );
                })}
            </div>
          )}

          {canDetail && panel === "trend" && (
            <>
              <div className="rounded-lg border border-slate-100 bg-slate-50/60 px-2 py-3">
                <div className="flex items-center gap-1 px-1 mb-2">
                  <p className="text-[10px] font-semibold text-slate-600">추이 (꺾은선)</p>
                  <AnalysisHelpPanel explain={trendExplain} />
                </div>
                <MatrixYearlyTrendChart rows={sortedRows} />
              </div>
              <div className="rounded-lg border border-slate-100 bg-white overflow-hidden">
                <p className="text-[10px] font-semibold text-slate-600 px-3 pt-3 pb-1">
                  {isRolling
                    ? "구간별 수치 (같은 조건 요약 집계)"
                    : "연도별 수치 (같은 조건 요약 집계)"}
                </p>
                <table className="w-full text-xs border-collapse">
                  <thead>
                    <tr className={simpleTableHeadClass("neutral")}>
                      <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">
                        {isRolling ? "구간" : "연도"}
                      </th>
                      <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">
                        건수
                      </th>
                      <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-blue-700">
                        평균(만원/㎡)
                      </th>
                    </tr>
                  </thead>
                  <tbody className="text-slate-800">
                    {sortedRows.map((r, ri) => (
                      <tr key={rowStableKey(r, ri)}>
                        <td className="border border-slate-200 px-2 py-1 tabular-nums">
                          {formatMatrixBucketAxisLabel(r)}
                        </td>
                        <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                          {r.count.toLocaleString("ko-KR")}
                        </td>
                        <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-blue-600 font-bold">
                          {r.mean_unit_price_per_sqm != null
                            ? Number(r.mean_unit_price_per_sqm).toLocaleString("ko-KR", {
                                minimumFractionDigits: 1,
                                maximumFractionDigits: 1,
                              })
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {canDetail && panel === "histogram" && filterRequest && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-[11px]">
                <span className="text-slate-500">표본 범위</span>
                <select
                  value={histScope}
                  onChange={(e) =>
                    setHistScope(e.target.value === "single" ? "single" : "all")
                  }
                  className="border border-slate-200 rounded px-2 py-1 bg-white text-slate-800"
                >
                  <option value="all">{isRolling ? "필터 구간 전체" : "필터 연도 전체"}</option>
                  <option value="single">{isRolling ? "특정 구간만" : "특정 연도만"}</option>
                </select>
                {histScope === "single" && (
                  <select
                    value={histSliceKey ?? ""}
                    onChange={(e) => setHistSliceKey(Number(e.target.value))}
                    className="border border-slate-200 rounded px-2 py-1 bg-white text-slate-800"
                  >
                    {sortedRows.map((r, ri) => {
                      const optVal = isRolling ? r.bucket_index : r.year;
                      if (optVal == null) return null;
                      return (
                        <option key={rowStableKey(r, ri)} value={optVal}>
                          {formatMatrixBucketAxisLabel(r)} ({r.count.toLocaleString("ko-KR")}건)
                        </option>
                      );
                    })}
                  </select>
                )}
                <AnalysisHelpPanel explain={histogramExplain} className="ml-auto" />
              </div>
              {histLoading && (
                <p className="text-xs text-slate-400 text-center py-4">분포 계산 중…</p>
              )}
              {histError && (
                <p className="text-xs text-red-500 text-center py-4">{histError}</p>
              )}
              {!histLoading && !histError && histData && (
                <>
                  <p className="text-[10px] text-slate-500 leading-relaxed">
                    표본 수 <strong className="text-slate-700">{histData.n.toLocaleString("ko-KR")}</strong>
                    건 · 이상치 제외{" "}
                    <strong className="text-slate-700">{histData.exclude_outlier ? "적용" : "안 함"}</strong>
                    {histData.exclude_outlier ? (
                      <span>
                        {" "}
                        (IQR×{histData.outlier_iqr_multiplier})
                      </span>
                    ) : null}
                    {histData.histogram_scope === "single" ? (
                      isRolling && histogramRollingBucketLabel ? (
                        <span>
                          {" "}
                          · 대상 구간{" "}
                          <strong className="text-slate-700">
                            {histogramRollingBucketLabel}
                          </strong>
                          {histData.histogram_period_start &&
                          histData.histogram_period_end ? (
                            <span className="text-slate-500">
                              {" "}
                              ({formatIsoDateBrief(histData.histogram_period_start)}{" "}
                              ~ {formatIsoDateBrief(histData.histogram_period_end)})
                            </span>
                          ) : null}
                        </span>
                      ) : histData.histogram_year != null ? (
                        <span>
                          {" "}
                          · 대상 연도{" "}
                          <strong className="text-slate-700">{histData.histogram_year}</strong>
                        </span>
                      ) : null
                    ) : null}
                  </p>
                  <div className="rounded-lg border border-slate-100 bg-slate-50/60 px-2 py-2">
                    <MatrixCellHistogramChart data={histData} />
                  </div>
                </>
              )}
            </div>
          )}

          {canDetail && panel === "transactions" && filterRequest && (
            <div className="space-y-2">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0 flex-1 space-y-1">
                  {txLoading && (
                    <p className="text-xs text-slate-400">목록 불러오는 중…</p>
                  )}
                  {txError && (
                    <p className="text-xs text-red-500">{txError}</p>
                  )}
                  {!txLoading && !txError && txData && (
                    <p className="text-[10px] text-slate-500">
                      전체{" "}
                      <strong className="text-slate-700">
                        {txData.total.toLocaleString("ko-KR")}
                      </strong>
                      건 · 이상치 제외{" "}
                      <strong className="text-slate-700">
                        {txData.exclude_outlier ? "적용" : "안 함"}
                      </strong>
                      {txData.exclude_outlier ? (
                        <span> (IQR×{txData.outlier_iqr_multiplier})</span>
                      ) : null}
                    </p>
                  )}
                  {txExportError && (
                    <p className="text-[10px] text-red-500">{txExportError}</p>
                  )}
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <AnalysisHelpPanel explain={txExplain} />
                  <button
                    type="button"
                    disabled={txExportLoading}
                    onClick={() => void handleTxExport()}
                    className="shrink-0 px-2.5 py-1 rounded border border-slate-200 text-[11px] font-medium text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
                  >
                    {txExportLoading ? "내보내는 중…" : "CSV 내보내기"}
                  </button>
                </div>
              </div>
              {txLoading && (
                <p className="text-xs text-slate-400 text-center py-4">목록 불러오는 중…</p>
              )}
              {!txLoading && !txError && txData && (
                <>
                  <div className="overflow-x-auto rounded-lg border border-slate-100">
                    <table className="w-full text-[11px] border-collapse min-w-[900px]">
                      <thead>
                        <tr className={simpleTableHeadClass("neutral")}>
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium whitespace-nowrap">
                            계약일
                          </th>
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium whitespace-nowrap">
                            주소
                          </th>
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium whitespace-nowrap">
                            지번
                          </th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium whitespace-nowrap">
                            면적(㎡)
                          </th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium whitespace-nowrap">
                            금액(만원)
                          </th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-blue-700 whitespace-nowrap">
                            단가
                          </th>
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium whitespace-nowrap">
                            도로
                          </th>
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium whitespace-nowrap">
                            지분
                          </th>
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium whitespace-nowrap">
                            유형
                          </th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-800">
                        {txData.items.map((r) => (
                          <tr key={r.id}>
                            <td className="border border-slate-200 px-2 py-1 tabular-nums whitespace-nowrap">
                              {formatTxContractDate(r)}
                            </td>
                            <td
                              className="border border-slate-200 px-2 py-1 max-w-[180px] truncate whitespace-nowrap"
                              title={[r.sigungu_name, r.eupmyeondong_name, r.beopjungri_name].filter(Boolean).join(" ") || undefined}
                            >
                              {[r.sigungu_name, r.eupmyeondong_name, r.beopjungri_name].filter(Boolean).join(" ") || "—"}
                            </td>
                            <td
                              className="border border-slate-200 px-2 py-1 max-w-[120px] truncate"
                              title={r.lot_display?.trim() || undefined}
                            >
                              {formatTxCell(r.lot_display)}
                            </td>
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums whitespace-nowrap">
                              {r.area_sqm != null
                                ? Number(r.area_sqm).toLocaleString("ko-KR", {
                                    maximumFractionDigits: 2,
                                  })
                                : "—"}
                            </td>
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums whitespace-nowrap">
                              {Number(r.total_price_10k).toLocaleString("ko-KR", {
                                maximumFractionDigits: 0,
                              })}
                            </td>
                            <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-blue-600 font-semibold whitespace-nowrap">
                              {r.unit_price_per_sqm != null
                                ? Number(r.unit_price_per_sqm).toLocaleString("ko-KR", {
                                    minimumFractionDigits: 1,
                                    maximumFractionDigits: 1,
                                  })
                                : "—"}
                            </td>
                            <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                              {r.road_condition ?? "—"}
                            </td>
                            <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                              {formatTxCell(r.partial_ownership_label)}
                            </td>
                            <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                              {formatTxCell(r.deal_type)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
                    <span className="text-slate-400">
                      {txData.total > 0
                        ? `${(txData.offset + 1).toLocaleString("ko-KR")}–${Math.min(txData.offset + txData.items.length, txData.total).toLocaleString("ko-KR")} / ${txData.total.toLocaleString("ko-KR")}`
                        : "0건"}
                    </span>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        disabled={txOffset <= 0}
                        onClick={() => setTxOffset((o) => Math.max(0, o - TX_PAGE))}
                        className="px-2 py-1 rounded border border-slate-200 text-slate-600 disabled:opacity-40 hover:bg-slate-50"
                      >
                        이전
                      </button>
                      <button
                        type="button"
                        disabled={txOffset + TX_PAGE >= txData.total}
                        onClick={() => setTxOffset((o) => o + TX_PAGE)}
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

          {/* ── 회귀 분석 탭 ── */}
          {canDetail && panel === "regression" && filterRequest && (
            <div className="space-y-4">
              {/* 변수 선택 */}
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-3">
                <p className="text-xs font-semibold text-slate-600">투입 변수 선택</p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                  {(
                    [
                      ["area_sqm", "면적(㎡)"],
                      ["road_condition", "도로조건"],
                      ["deal_type", "거래유형"],
                      ["partial_ownership", "지분여부"],
                      ["year_trend", "연도추세"],
                      ["beopjungri_fe", "법정동 FE"],
                    ] as [keyof LandRegressionVariables, string][]
                  ).map(([key, label]) => (
                    <label key={key} className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={regVars[key]}
                        onChange={(e) =>
                          setRegVars((v) => ({ ...v, [key]: e.target.checked }))
                        }
                        className="accent-blue-600"
                      />
                      <span>{label}</span>
                    </label>
                  ))}
                </div>
                {regVars.area_sqm && (
                  <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                    <input
                      type="checkbox"
                      checked={regVars.log_area}
                      onChange={(e) =>
                        setRegVars((v) => ({ ...v, log_area: e.target.checked }))
                      }
                      className="accent-blue-600"
                    />
                    <span className="text-slate-500">면적 로그 변환 (log area)</span>
                  </label>
                )}
                <div className="flex flex-wrap gap-4 text-xs">
                  <span className="text-slate-500 font-medium">종속변수:</span>
                  {(["log", "linear"] as const).map((mt) => (
                    <label key={mt} className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="radio"
                        name="regModelType"
                        value={mt}
                        checked={regModelType === mt}
                        onChange={() => setRegModelType(mt)}
                        className="accent-blue-600"
                      />
                      <span>{mt === "log" ? "log(단가)" : "단가(선형)"}</span>
                    </label>
                  ))}
                  <label className="flex items-center gap-1.5 cursor-pointer ml-4">
                    <input
                      type="checkbox"
                      checked={regExcludeOutlier}
                      onChange={(e) => setRegExcludeOutlier(e.target.checked)}
                      className="accent-blue-600"
                    />
                    <span className="text-slate-500">IQR 이상치 제외</span>
                  </label>
                </div>
                <button
                  type="button"
                  disabled={regLoading}
                  onClick={async () => {
                    if (!filterRequest) return;
                    setRegLoading(true);
                    setRegError(null);
                    setRegResult(null);
                    try {
                      const res = await fetchLandRegression({
                        ...filterRequest,
                        variables: regVars,
                        model_type: regModelType,
                        exclude_outliers_iqr: regExcludeOutlier,
                        outlier_iqr_multiplier: 3,
                        min_n: 15,
                      });
                      setRegResult(res);
                    } catch (e) {
                      setRegError(parseApiError(e).message);
                    } finally {
                      setRegLoading(false);
                    }
                  }}
                  className="px-4 py-1.5 rounded bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 disabled:opacity-50"
                >
                  {regLoading ? "계산 중…" : "회귀 실행"}
                </button>
              </div>

              {regError && (
                <p className="text-xs text-red-500 bg-red-50 rounded p-2">{regError}</p>
              )}

              {regResult && (
                <div className="space-y-3">
                  {/* 요약 */}
                  <div className="flex flex-wrap gap-4 text-xs text-slate-600 bg-white border border-slate-200 rounded-lg p-3">
                    <span>
                      <span className="font-medium">n</span> = {regResult.n.toLocaleString("ko-KR")}
                    </span>
                    <span>
                      <span className="font-medium">모델</span> {regResult.model_type === "log" ? "log(단가)" : "선형"}
                    </span>
                    <span>
                      <span className="font-medium">R²</span>{" "}
                      {regResult.r_squared.toFixed(3)}
                    </span>
                    <span>
                      <span className="font-medium">adj R²</span>{" "}
                      {regResult.adj_r_squared.toFixed(3)}
                    </span>
                    {Object.entries(regResult.reference_categories).map(([k, v]) => (
                      <span key={k} className="text-slate-400">
                        기준[{k}]: {v}
                      </span>
                    ))}
                  </div>

                  {/* 경고 */}
                  {regResult.warnings.length > 0 && (
                    <ul className="text-xs text-amber-700 bg-amber-50 rounded p-2 space-y-0.5">
                      {regResult.warnings.map((w, i) => (
                        <li key={i}>⚠ {w}</li>
                      ))}
                    </ul>
                  )}

                  {/* 계수 테이블 */}
                  <div className="overflow-x-auto rounded-lg border border-slate-100">
                    <table className="w-full text-[11px] border-collapse min-w-[520px]">
                      <thead>
                        <tr className={simpleTableHeadClass("neutral")}>
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">변수</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">계수</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">SE</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">t</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">p-값</th>
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">유의</th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-800">
                        {regResult.coefficients.map((c: LandRegressionCoeff) => {
                          const sig =
                            c.p < 0.001 ? "***" : c.p < 0.01 ? "**" : c.p < 0.05 ? "*" : c.p < 0.1 ? "." : "";
                          const pRow =
                            c.p < 0.05 ? "bg-blue-50" : "";
                          return (
                            <tr key={c.name} className={pRow}>
                              <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">{c.label}</td>
                              <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                                {c.coef.toFixed(4)}
                              </td>
                              <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-slate-500">
                                {c.se.toFixed(4)}
                              </td>
                              <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-slate-500">
                                {c.t.toFixed(2)}
                              </td>
                              <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                                {c.p < 0.0001 ? "<0.0001" : c.p.toFixed(4)}
                              </td>
                              <td className="border border-slate-200 px-2 py-1 font-semibold text-blue-700 text-center w-10">
                                {sig}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <p className="text-[10px] text-slate-400">
                    유의수준: *** p&lt;0.001 &nbsp;** p&lt;0.01 &nbsp;* p&lt;0.05 &nbsp;. p&lt;0.1 &nbsp;· p≥0.1
                    {regResult.model_type === "log" && " · log 모델: 계수는 단가 log 기준 (e^coef ≈ 배율)"}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
