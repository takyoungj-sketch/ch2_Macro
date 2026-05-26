import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchFreeStats,
  fetchFreeStatsBulk,
  fetchPaidMatrixYearly,
  fetchRegions,
  fetchUpperStats,
} from "../api/client";
import { REGIONS_CATALOG_QUERY_KEY } from "../constants/regionsCatalog";
import { useAppStore } from "../store";
import { type MatrixYearlyRequest, type MatrixYearlyStat, normalizeFreeStatsWindowYears } from "../types";
import { parseApiError } from "../utils/apiError";
import {
  calendarYearReferenceRows,
} from "../utils/freeStatsV2";
import { buildPaidPayload, clearRollingMatrixFields } from "../utils/paidAnalysisPayload";
import { resolveUnionBeopjungriCodes } from "../utils/regionTier";
import { resolveUpperSingleFromTier, upperToFreeStatsShape } from "../utils/upperTierStats";
import MatrixStatsTable, { MatrixStatsLegend } from "./MatrixStatsTable";
import PaidMatrixYearlyModal from "./PaidMatrixYearlyModal";
import YearlyStatsTable from "./YearlyStatsTable";

export default function PaidAnalysisPanel() {
  const viewMode = useAppStore((s) => s.viewMode);
  const paidBasicStatsKick = useAppStore((s) => s.paidBasicStatsKick);
  const syncPaidBasicStatsMeta = useAppStore((s) => s.syncPaidBasicStatsMeta);
  const tierSelection = useAppStore((s) => s.tierSelection);
  const paidRequest = useAppStore((s) => s.paidRequest);
  const paidRoadExcluded = useAppStore((s) => s.paidRoadExcluded);
  const paidAreaExcluded = useAppStore((s) => s.paidAreaExcluded);
  const paidBasicBaseKey = useAppStore((s) => s.paidBasicBaseKey);
  const freeStatsWindowYears = useAppStore((s) =>
    normalizeFreeStatsWindowYears(s.freeStatsWindowYears)
  );
  const status = useAppStore((s) => s.paidAnalysisStatus);
  const result = useAppStore((s) => s.paidAnalysisResult);
  const apiErr = useAppStore((s) => s.paidAnalysisError);
  const startedAt = useAppStore((s) => s.paidAnalysisStartedAt);
  const runPaidFilteredAnalysis = useAppStore((s) => s.runPaidFilteredAnalysis);
  const cancelPaidFilteredAnalysis = useAppStore((s) => s.cancelPaidFilteredAnalysis);
  const paidBulkBeopjungriCodes = useAppStore((s) => s.paidBulkBeopjungriCodes);
  const paidFilteredAnalysisScopeNotice = useAppStore((s) => s.paidFilteredAnalysisScopeNotice);

  const [trendModal, setTrendModal] = useState<{
    zoneType: string;
    landCategory: string;
  } | null>(null);
  const [trendLoading, setTrendLoading] = useState(false);
  const [trendError, setTrendError] = useState<string | null>(null);
  const [trendRows, setTrendRows] = useState<MatrixYearlyStat[]>([]);
  const [trendRequest, setTrendRequest] = useState<MatrixYearlyRequest | null>(null);

  const { data: regions = [], isLoading: regionsLoading } = useQuery({
    queryKey: REGIONS_CATALOG_QUERY_KEY,
    queryFn: () => fetchRegions(),
    staleTime: 6 * 60 * 60 * 1000,
  });

  const resolvedCodes = useMemo(
    () => resolveUnionBeopjungriCodes(regions, tierSelection),
    [regions, tierSelection]
  );

  const upperSingle = useMemo(() => resolveUpperSingleFromTier(tierSelection), [tierSelection]);
  const useUpperPaidBasic = viewMode === "paid" && upperSingle !== null;

  const bulkKey = useMemo(() => [...resolvedCodes].slice().sort().join(","), [resolvedCodes]);
  const useBulkBasic = viewMode === "paid" && !useUpperPaidBasic && resolvedCodes.length > 1;

  const canFetchBasic =
    !regionsLoading &&
    viewMode === "paid" &&
    (useUpperPaidBasic ||
      useBulkBasic ||
      (!upperSingle && resolvedCodes.length === 1));

  const {
    data: basicData,
    isLoading: basicLoading,
    isError: basicIsError,
    error: basicError,
  } = useQuery({
    queryKey: useUpperPaidBasic
      ? [
          "upperStats",
          upperSingle!.level,
          upperSingle!.code,
          paidBasicStatsKick,
          freeStatsWindowYears,
        ]
      : useBulkBasic
        ? ["freeStatsBulkV2", bulkKey, paidBasicStatsKick, freeStatsWindowYears]
        : ["freeStatsV2", resolvedCodes[0] ?? "", paidBasicStatsKick, viewMode, freeStatsWindowYears],
    queryFn: async () => {
      if (useUpperPaidBasic) {
        const up = await fetchUpperStats(upperSingle!.level, upperSingle!.code, {
          window_years: freeStatsWindowYears,
        });
        return upperToFreeStatsShape(up);
      }
      if (useBulkBasic) {
        return fetchFreeStatsBulk(resolvedCodes, { window_years: freeStatsWindowYears });
      }
      return fetchFreeStats(resolvedCodes[0]!, { window_years: freeStatsWindowYears });
    },
    enabled: canFetchBasic,
  });

  useEffect(() => {
    if (basicData === undefined) return;
    if (useUpperPaidBasic) {
      syncPaidBasicStatsMeta({ analysis_base_key: null, beopjungri_code: null });
      return;
    }
    syncPaidBasicStatsMeta({
      analysis_base_key: basicData.analysis_base_key ?? null,
      beopjungri_code: basicData.beopjungri_code ?? null,
    });
  }, [basicData, useUpperPaidBasic, syncPaidBasicStatsMeta]);

  /** 상단 참고표: 순수 만년력 연도(1·1~12·31). 필터 칩과 무관. */
  const yearlyReferenceRowsPaid = useMemo(() => {
    if (!basicData) return [];
    const cal = calendarYearReferenceRows(basicData);
    if (cal && cal.length > 0) return cal;
    return basicData.by_year ?? [];
  }, [basicData]);

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

  const codesForPaidMatrix = useMemo(() => {
    if (paidBulkBeopjungriCodes != null && paidBulkBeopjungriCodes.length > 0) {
      return paidBulkBeopjungriCodes;
    }
    const fromBasic = basicData?.beopjungri_code
      ?.split(",")
      .map((x) => x.trim())
      .filter(Boolean);
    if (fromBasic != null && fromBasic.length > 0) return fromBasic;
    return resolvedCodes;
  }, [paidBulkBeopjungriCodes, basicData?.beopjungri_code, resolvedCodes]);

  const closeTrend = () => {
    setTrendModal(null);
    setTrendRequest(null);
    setTrendLoading(false);
    setTrendError(null);
    setTrendRows([]);
  };

  const openMatrixTrend = useCallback(
    async (zoneType: string, landCategory: string) => {
      if (resolvedCodes.length === 0) {
        setTrendError("먼저 분석할 지역을 선택하세요.");
        setTrendModal({ zoneType, landCategory });
        setTrendRequest(null);
        setTrendLoading(false);
        return;
      }

      const cacheKey = basicData?.analysis_base_key ?? paidBasicBaseKey;
      /** 매트릭스 모달은 필터 선택 연도·조건과 동일해야 함 — 기본통계 V2 롤링(contract_date 버킷)은 합치지 않는다 */
      const base = buildPaidPayload(
        clearRollingMatrixFields(paidRequest),
        codesForPaidMatrix,
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
      setTrendRequest(body);
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
    [basicData, paidBasicBaseKey, paidRequest, paidRoadExcluded, paidAreaExcluded, codesForPaidMatrix]
  );

  return (
    <div className="space-y-4">
      {/* 기본 통계 보기와 동일: 상단 연도별 표 + 범례 1회만 (매트릭스에는 범례 비표시) */}
      <div className="bg-white rounded-xl shadow-sm p-5 space-y-5">
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
            {Boolean(basicData.stats_excluded_codes?.length) && (
              <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-2 py-1.5 leading-snug mb-3">
                사전 집계가 없는 법정코드 {(basicData.stats_excluded_codes ?? []).length}건은 요청 목록에서는 보냈지만
                합산 표본에서는 자동으로 제외했습니다. 예:{" "}
                {(basicData.stats_excluded_codes ?? []).slice(0, 6).join(", ")}
                {(basicData.stats_excluded_codes?.length ?? 0) > 6 ? " …" : ""}
              </p>
            )}
            <div className="flex flex-wrap items-start gap-3 gap-y-2">
              <h2 className="text-base font-bold text-slate-800 shrink-0 leading-tight max-w-md">
                {basicData.beopjungri_name}
              </h2>
              <div className="min-w-0 flex-1 basis-[12rem]">
                <YearlyStatsTable rows={yearlyReferenceRowsPaid} hideTitle />
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
          {paidFilteredAnalysisScopeNotice ? (
            <p className="text-[11px] text-amber-900 bg-amber-50 border border-amber-200 rounded-md px-3 py-2 max-w-lg leading-relaxed text-left">
              {paidFilteredAnalysisScopeNotice}
            </p>
          ) : null}
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
          {paidFilteredAnalysisScopeNotice ? (
            <p className="text-[11px] text-left text-slate-700 bg-white/70 border border-slate-200 rounded-md px-2 py-1.5 mb-2 leading-relaxed">
              {paidFilteredAnalysisScopeNotice}
            </p>
          ) : null}
          <p className="font-medium">{apiErr.message}</p>
        </div>
      )}

      {!isLoading && status === "success" && result && (
        <div className="bg-white rounded-xl shadow-sm p-5 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-bold text-slate-800">필터 분석 결과</h2>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">{result.response_ms}ms</span>
              <button
                type="button"
                onClick={() => void runPaidFilteredAnalysis(codesForPaidMatrix)}
                disabled={resolvedCodes.length === 0 || isLoading}
                className="text-xs font-medium text-blue-600 hover:text-blue-800 disabled:opacity-40"
              >
                동일 조건 재실행
              </button>
            </div>
          </div>

          {paidFilteredAnalysisScopeNotice ? (
            <p className="text-[11px] text-amber-900 bg-amber-50 border border-amber-200 rounded-md px-2 py-1.5 leading-relaxed">
              {paidFilteredAnalysisScopeNotice}
            </p>
          ) : null}

          <MatrixStatsTable
            title=""
            matrix={result.matrix}
            byZone={result.by_zone}
            byLandCategory={result.by_land_category}
            showEmbeddedLegend={false}
            onPaidMatrixCellClick={openMatrixTrend}
          />
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
        filterRequest={trendRequest}
      />
    </div>
  );
}
