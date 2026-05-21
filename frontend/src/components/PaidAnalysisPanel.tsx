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
import { type MatrixYearlyRequest, normalizeFreeStatsWindowYears } from "../types";
import { parseApiError } from "../utils/apiError";
import { statsAsOfLabel } from "../utils/freeStatsV2";
import { buildPaidPayload } from "../utils/paidAnalysisPayload";
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
  const [trendRows, setTrendRows] = useState<
    { year: number; count: number; mean_unit_price_per_sqm: number | null }[]
  >([]);
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

  /** 필터 결과가 있으면 서버 연도별 집계(도로·면적 필터 포함)를 상단에 표시, 없으면 기본통계 by_year 에서 선택 연도만 표시 */
  const yearlyRowsForPaidFilter = useMemo(() => {
    const rows = basicData?.by_year ?? [];
    const sel = paidRequest.years ?? [];
    if (sel.length === 0) return rows;
    const want = new Set(sel);
    return rows.filter((r) => want.has(r.year));
  }, [basicData?.by_year, paidRequest.years]);

  const yearlyRowsPaidTop = useMemo(() => {
    if (
      status === "success" &&
      result?.by_year != null &&
      result.by_year.length > 0
    ) {
      return result.by_year;
    }
    return yearlyRowsForPaidFilter;
  }, [status, result?.by_year, yearlyRowsForPaidFilter]);

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
      const base = buildPaidPayload(
        paidRequest,
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

  // DECISIONS D-002 / D-006 — 무료/유료 화면 모두 같은 「YYYY년 M월 말 기준」 라벨.
  // 기본통계 박스는 basicData(/free/v2/...)에서, 필터 분석 결과는 result(/paid/analyze)에서 각각 가져온다.
  const basicAsOfLabel = useMemo(
    () =>
      basicData
        ? statsAsOfLabel({
            as_of_month: basicData.as_of_month,
            stats_reference_date: basicData.stats_reference_date,
          })
        : null,
    [basicData]
  );
  const filteredAsOfLabel = useMemo(
    () =>
      result
        ? statsAsOfLabel({
            as_of_month: result.as_of_month ?? null,
            stats_reference_date: result.stats_reference_date ?? null,
          })
        : null,
    [result]
  );

  return (
    <div className="space-y-4">
      {/* 기본 통계 보기와 동일: 상단 연도별 표 + 범례 1회만 (매트릭스에는 범례 비표시) */}
      <div className="bg-white rounded-xl shadow-sm p-5 space-y-5">
        <p className="text-[11px] text-indigo-700 font-medium leading-relaxed">
          유료 · 기본 통계 (V2)
          {basicAsOfLabel && (
            <span className="ml-2 inline-block text-slate-700 font-medium">
              · {basicAsOfLabel}
            </span>
          )}
          {useUpperPaidBasic && (
            <span className="block text-indigo-600/90 font-normal mt-0.5">
              시·도·시군구·읍면동·[시](자치구 묶음)만 단독 선택한 경우{" "}
              <code className="text-[10px]">land_upper_stats_v2</code> 사전집계입니다. 메인 기본 통계 카드와 동일 소스입니다.
            </span>
          )}
          {useBulkBasic && (
            <span className="block text-indigo-600/90 font-normal mt-0.5">
              선택 법정동·리 거래 단가를 합친 결과입니다. 매트릭스는 원장 기준 즉시 집계입니다.
            </span>
          )}
          {viewMode === "paid" && !useUpperPaidBasic && !useBulkBasic && canFetchBasic && (
            <span className="block text-indigo-600/90 font-normal mt-0.5">
              단일 동·리는 <code className="text-[10px]">land_basic_stats_v2</code> 사전집계입니다.
            </span>
          )}
        </p>
        <p className="text-[10px] text-slate-500 leading-relaxed rounded-md bg-slate-50 border border-slate-100 px-2 py-1.5">
          <strong className="text-slate-600">필터 분석</strong> 결과는 거래 원장에 연도·도로·면적 등을 적용해 다시 만듭니다.
          위 기본 통계와 수치·표본 범위가 같지 않을 수 있습니다.
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
            {Boolean(basicData.stats_excluded_codes?.length) && (
              <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-2 py-1.5 leading-snug mb-3">
                사전 집계가 없는 법정코드 {(basicData.stats_excluded_codes ?? []).length}건은 요청 목록에서는
                보냈지만 합산 표본에서는 자동으로 제외했습니다. 예: {(basicData.stats_excluded_codes ?? [])
                  .slice(0, 6)
                  .join(", ")}
                {(basicData.stats_excluded_codes?.length ?? 0) > 6 ? " …" : ""}
              </p>
            )}
            <div className="flex flex-wrap items-start gap-3 gap-y-2">
              <h2 className="text-base font-bold text-slate-800 shrink-0 leading-tight max-w-md">
                {basicData.beopjungri_name}
              </h2>
              <div className="min-w-0 flex-1 basis-[12rem]">
                <YearlyStatsTable rows={yearlyRowsPaidTop} hideTitle />
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
          {paidFilteredAnalysisScopeNotice ? (
            <p className="text-[11px] text-left text-slate-700 bg-white/70 border border-slate-200 rounded-md px-2 py-1.5 mb-2 leading-relaxed">
              {paidFilteredAnalysisScopeNotice}
            </p>
          ) : null}
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
        <div className="bg-white rounded-xl shadow-sm p-5 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-baseline gap-2 flex-wrap">
              <h2 className="text-base font-bold text-slate-800">필터 분석 결과</h2>
              {filteredAsOfLabel && (
                <span className="text-[11px] text-slate-600 font-medium">
                  · {filteredAsOfLabel}
                </span>
              )}
            </div>
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
          <p className="text-[10px] text-slate-500 leading-relaxed">
            이 화면은 <code className="text-[10px]">/paid/analyze</code>가 <code className="text-[10px]">land_transactions</code>{" "}
            원장을 필터한 결과입니다. 기본 통계(사전집계·롤링 구간)와 정의가 다릅니다.
          </p>

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
