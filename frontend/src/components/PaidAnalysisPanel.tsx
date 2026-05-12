import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchFreeStats,
  fetchFreeStatsBulk,
  fetchPaidMatrixYearly,
  fetchRegions,
} from "../api/client";
import { REGIONS_CATALOG_QUERY_KEY } from "../constants/regionsCatalog";
import { useAppStore } from "../store";
import type { MatrixYearlyRequest } from "../types";
import { COMPARE_SESSION_KEY } from "../constants/compareStorage";
import type { ComparePayloadV1 } from "../types/comparePayload";
import { resolveCompareHref } from "../utils/appPaths";
import { downloadByRegionCsv, downloadMatrixCsv } from "../utils/exportCsv";
import { parseApiError } from "../utils/apiError";
import { safeFileStem } from "../utils/safeFilename";
import { buildPaidPayload } from "../utils/paidAnalysisPayload";
import { beopjungriNameForCode, resolveBeopjungriCodes } from "../utils/regionTier";
import MatrixStatsTable, { MatrixStatsLegend } from "./MatrixStatsTable";
import PaidMatrixYearlyModal from "./PaidMatrixYearlyModal";
import StatsTable from "./StatsTable";
import YearlyStatsTable from "./YearlyStatsTable";

export default function PaidAnalysisPanel() {
  const viewMode = useAppStore((s) => s.viewMode);
  const paidBasicStatsKick = useAppStore((s) => s.paidBasicStatsKick);
  const setPaidBasicBaseKey = useAppStore((s) => s.setPaidBasicBaseKey);
  const tierSelection = useAppStore((s) => s.tierSelection);
  const paidRequest = useAppStore((s) => s.paidRequest);
  const paidRoadExcluded = useAppStore((s) => s.paidRoadExcluded);
  const paidAreaExcluded = useAppStore((s) => s.paidAreaExcluded);
  const paidBasicBaseKey = useAppStore((s) => s.paidBasicBaseKey);
  const status = useAppStore((s) => s.paidAnalysisStatus);
  const result = useAppStore((s) => s.paidAnalysisResult);
  const apiErr = useAppStore((s) => s.paidAnalysisError);
  const startedAt = useAppStore((s) => s.paidAnalysisStartedAt);
  const runPaidFilteredAnalysis = useAppStore((s) => s.runPaidFilteredAnalysis);
  const cancelPaidFilteredAnalysis = useAppStore((s) => s.cancelPaidFilteredAnalysis);

  const [trendModal, setTrendModal] = useState<{
    zoneType: string;
    landCategory: string;
  } | null>(null);
  const [trendLoading, setTrendLoading] = useState(false);
  const [trendError, setTrendError] = useState<string | null>(null);
  const [trendRows, setTrendRows] = useState<
    { year: number; count: number; mean_unit_price_per_sqm: number | null }[]
  >([]);

  const { data: regions = [], isLoading: regionsLoading } = useQuery({
    queryKey: REGIONS_CATALOG_QUERY_KEY,
    queryFn: () => fetchRegions(),
    staleTime: 6 * 60 * 60 * 1000,
  });

  const resolvedCodes = useMemo(
    () => resolveBeopjungriCodes(regions, tierSelection),
    [regions, tierSelection]
  );

  const bulkKey = useMemo(() => [...resolvedCodes].slice().sort().join(","), [resolvedCodes]);
  const useBulkBasic = resolvedCodes.length > 1;

  const canFetchBasic =
    resolvedCodes.length > 0 && !regionsLoading && (useBulkBasic || resolvedCodes.length === 1);

  const {
    data: basicData,
    isLoading: basicLoading,
    isError: basicIsError,
    error: basicError,
  } = useQuery({
    queryKey: useBulkBasic
      ? ["freeStatsBulk", bulkKey, paidBasicStatsKick]
      : ["freeStats", resolvedCodes[0] ?? "", paidBasicStatsKick, viewMode],
    queryFn: () =>
      useBulkBasic ? fetchFreeStatsBulk(resolvedCodes) : fetchFreeStats(resolvedCodes[0]!),
    enabled: canFetchBasic && viewMode === "paid",
  });

  useEffect(() => {
    if (basicData?.analysis_base_key) {
      setPaidBasicBaseKey(basicData.analysis_base_key);
    }
  }, [basicData?.analysis_base_key, setPaidBasicBaseKey]);

  const isLoading = status === "loading";
  const [analyzeWaitSec, setAnalyzeWaitSec] = useState(0);
  useEffect(() => {
    if (!isLoading || startedAt == null) {
      setAnalyzeWaitSec(0);
      return;
    }
    const update = () =>
      setAnalyzeWaitSec(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)));
    update();
    const id = window.setInterval(update, 400);
    return () => window.clearInterval(id);
  }, [isLoading, startedAt]);

  const filterAnalysisDerived = useMemo(() => {
    if (!result?.by_region) return null;
    const enriched = Object.entries(result.by_region).map(([code, stats]) => ({
      code,
      label: beopjungriNameForCode(regions, code),
      stats,
    }));
    enriched.sort((a, b) => a.label.localeCompare(b.label, "ko-KR"));
    return {
      regionBreakdownRows: enriched.map(({ label, stats }) => ({ label, stats })),
      regionLabels: Object.fromEntries(enriched.map((e) => [e.code, e.label])) as Record<
        string,
        string
      >,
      regionOrder: enriched.map((e) => e.code),
    };
  }, [result?.by_region, regions]);

  const regionBreakdownRows = filterAnalysisDerived?.regionBreakdownRows ?? [];

  const closeTrend = () => {
    setTrendModal(null);
    setTrendLoading(false);
    setTrendError(null);
    setTrendRows([]);
  };

  const openMatrixTrend = useCallback(
    async (zoneType: string, landCategory: string) => {
      if (resolvedCodes.length === 0) {
        setTrendError("먼저 분석할 지역을 선택하세요.");
        setTrendModal({ zoneType, landCategory });
        setTrendLoading(false);
        return;
      }

      const cacheKey = basicData?.analysis_base_key ?? paidBasicBaseKey;
      const base = buildPaidPayload(
        paidRequest,
        resolvedCodes,
        paidRoadExcluded,
        paidAreaExcluded,
        cacheKey
      );
      const body: MatrixYearlyRequest = {
        ...base,
        zone_type: zoneType,
        land_category: landCategory,
      };

      setTrendModal({ zoneType, landCategory });
      setTrendLoading(true);
      setTrendError(null);
      setTrendRows([]);
      try {
        const data = await fetchPaidMatrixYearly(body);
        setTrendRows(data.rows ?? []);
      } catch (e) {
        setTrendError(parseApiError(e).message);
      } finally {
        setTrendLoading(false);
      }
    },
    [basicData?.analysis_base_key, paidBasicBaseKey, paidRequest, paidRoadExcluded, paidAreaExcluded, resolvedCodes]
  );

  const triggerPrintPaid = useCallback(() => {
    document.body.classList.add("print-paid-active");
    const cleanup = () => document.body.classList.remove("print-paid-active");
    window.addEventListener("afterprint", cleanup, { once: true });
    window.setTimeout(cleanup, 4000);
    window.print();
  }, []);

  const openCompareWindow = useCallback(() => {
    if (!result) return;
    const fd = filterAnalysisDerived;
    const payload: ComparePayloadV1 = {
      v: 1,
      savedAt: Date.now(),
      title: `필터 분석 · ${resolvedCodes.length}개 법정단위`,
      matrix: result.matrix,
      by_zone: result.by_zone,
      by_land_category: result.by_land_category,
      by_region: result.by_region,
      regionOrder: fd?.regionOrder ?? [],
      regionLabels: fd?.regionLabels ?? {},
    };
    sessionStorage.setItem(COMPARE_SESSION_KEY, JSON.stringify(payload));
    window.open(resolveCompareHref(), "_blank", "noopener,noreferrer");
  }, [filterAnalysisDerived, resolvedCodes.length, result]);

  return (
    <div className="space-y-4">
      {/* 기본 통계 보기와 동일: 상단 연도별 표 + 범례 1회만 (매트릭스에는 범례 비표시) */}
      <div className="bg-white rounded-xl shadow-sm p-5 space-y-5">
        <p className="text-[11px] text-indigo-700 font-medium leading-relaxed">
          유료 · 기본 통계
          {useBulkBasic && (
            <span className="block text-indigo-600/90 font-normal mt-0.5">
              선택 법정동·리 거래 단가를 합친 결과입니다. 매트릭스는 원장 기준 즉시 집계입니다.
            </span>
          )}
        </p>
        {basicLoading && (
          <p className="text-xs text-slate-400 text-center py-4">연도별 요약 불러오는 중…</p>
        )}
        {basicIsError && (
          <p className="text-xs text-amber-700 text-center py-2">
            연도별 요약을 불러오지 못했습니다
            {basicError ? ` — ${parseApiError(basicError).message}` : ""}
          </p>
        )}
        {!basicLoading && basicData && (
          <>
            <div className="flex flex-wrap items-start gap-3 gap-y-2">
              <h2 className="text-base font-bold text-slate-800 shrink-0 leading-tight max-w-md">
                {basicData.beopjungri_name}
              </h2>
              <div className="min-w-0 flex-1 basis-[12rem]">
                <YearlyStatsTable rows={basicData.by_year ?? []} hideTitle />
              </div>
              <div className="shrink-0">
                <MatrixStatsLegend />
              </div>
            </div>
          </>
        )}
        {!basicLoading && !basicData && !basicIsError && canFetchBasic && (
          <p className="text-xs text-slate-400 text-center py-4">연도별 요약 데이터가 없습니다.</p>
        )}
      </div>

      {isLoading && (
        <div className="flex flex-col items-center justify-center gap-3 py-8 px-4 text-center rounded-xl bg-white shadow-sm border border-slate-100">
          <div
            className="h-9 w-9 rounded-full border-2 border-slate-200 border-t-blue-600 animate-spin shrink-0"
            aria-hidden
          />
          <div className="text-sm text-slate-700">
            필터 분석 중…{" "}
            {analyzeWaitSec > 0 && (
              <span className="text-slate-500 font-medium tabular-nums">({analyzeWaitSec}초 경과)</span>
            )}
          </div>
          <p className="text-[11px] text-slate-400 max-w-sm leading-relaxed">
            거래량이 많으면 열 시간이 길어질 수 있습니다. 「이상치 제외」가 켜져 있으면 IQR 배수와
            관계없이 전체 거래 행을 읽는 방식이라 더 느릴 수 있습니다.
          </p>
          {analyzeWaitSec >= 5 && (
            <button
              type="button"
              onClick={() => cancelPaidFilteredAnalysis()}
              className="mt-1 text-[11px] text-slate-500 underline underline-offset-2 hover:text-red-600"
            >
              취소하고 초기 상태로
            </button>
          )}
        </div>
      )}

      {!isLoading && apiErr != null && (
        <div
          className={`rounded-xl border px-4 py-3 text-center text-sm leading-relaxed ${
            apiErr.status === 404
              ? "border-amber-200 bg-amber-50 text-amber-950"
              : "border-red-200 bg-red-50 text-red-800"
          }`}
          role="alert"
        >
          <p className="font-medium">{apiErr.message}</p>
          {apiErr.status === 404 ? (
            <p className="mt-2 text-xs text-amber-800/90">
              연도·도로·면적 선택을 완화해 보세요. 조건에 맞는 거래가 없을 수 있습니다.
            </p>
          ) : apiErr.status === 422 ? (
            <p className="mt-2 text-xs text-red-700/90">
              요청 형식이 서버 검증을 통과하지 못했습니다. 필터 값을 확인해 주세요.
            </p>
          ) : null}
        </div>
      )}

      {!isLoading && status === "success" && result && (
        <div className="paid-analysis-print-root bg-white rounded-xl shadow-sm p-5 space-y-6">
          <div className="no-print flex flex-wrap items-start justify-between gap-3 pb-4 border-b border-slate-100">
            <h2 className="text-base font-bold text-slate-800 shrink-0">필터 분석 결과</h2>
            <div className="flex flex-wrap items-center justify-end gap-2">
              <span className="text-xs text-slate-400 tabular-nums">{result.response_ms}ms</span>
              <button
                type="button"
                onClick={openCompareWindow}
                className="text-xs font-medium px-2.5 py-1 rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
              >
                비교 새 창
              </button>
              <button
                type="button"
                onClick={() =>
                  downloadMatrixCsv(
                    `${safeFileStem(`matrix_${resolvedCodes.slice(0, 2).join("_")}_${Date.now()}`)}.csv`,
                    result.matrix
                  )
                }
                className="text-xs font-medium px-2.5 py-1 rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
              >
                CSV 매트릭스
              </button>
              {regionBreakdownRows.length > 0 ? (
                <button
                  type="button"
                  onClick={() =>
                    downloadByRegionCsv(
                      `${safeFileStem(`by_region_${Date.now()}`)}.csv`,
                      result.by_region,
                      filterAnalysisDerived?.regionLabels
                    )
                  }
                  className="text-xs font-medium px-2.5 py-1 rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                >
                  CSV 지역별
                </button>
              ) : null}
              <button
                type="button"
                onClick={triggerPrintPaid}
                className="text-xs font-medium px-2.5 py-1 rounded-lg border border-slate-800 bg-slate-800 text-white hover:bg-slate-900"
              >
                인쇄 / PDF
              </button>
              <button
                type="button"
                onClick={() => void runPaidFilteredAnalysis()}
                disabled={resolvedCodes.length === 0 || isLoading}
                className="text-xs font-medium text-blue-600 hover:text-blue-800 disabled:opacity-40"
              >
                동일 조건 재실행
              </button>
            </div>
          </div>

          <p className="no-print text-[11px] text-slate-500 leading-relaxed -mt-2">
            새 창에서는 법정단위별 요약 블록이 위에서부터 이어지고, 맨 아래에 선택 지역 통합 매트릭스가 표시됩니다.
          </p>

          <div className="no-print flex justify-end">
            <MatrixStatsLegend />
          </div>

          <MatrixStatsTable
            title=""
            matrix={result.matrix}
            byZone={result.by_zone}
            byLandCategory={result.by_land_category}
            showEmbeddedLegend={false}
            onPaidMatrixCellClick={openMatrixTrend}
          />

          {regionBreakdownRows.length > 0 && (
            <StatsTable title="지역별 (법정동·리)" rows={regionBreakdownRows} />
          )}
        </div>
      )}
      <PaidMatrixYearlyModal
        open={trendModal != null}
        onClose={closeTrend}
        loading={trendLoading}
        error={trendError}
        zoneType={trendModal?.zoneType ?? ""}
        landCategory={trendModal?.landCategory ?? ""}
        rows={trendRows}
      />

      {!isLoading && status === "idle" && !apiErr && (
        <p className="text-center text-[11px] text-slate-400">
          왼쪽 필터 표 하단의{" "}
          <strong className="text-slate-600">필터 분석 실행</strong>으로 조건을 적용한 매트릭스를
          불러옵니다. 셀 클릭 시 연도별 단가 추이가 열립니다.
        </p>
      )}
    </div>
  );
}
