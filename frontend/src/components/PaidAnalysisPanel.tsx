import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchPaidMatrixYearly, fetchRegions } from "../api/client";
import { useAppStore } from "../store";
import type { MatrixYearlyRequest } from "../types";
import { parseApiError } from "../utils/apiError";
import { buildPaidPayload } from "../utils/paidAnalysisPayload";
import { resolveBeopjungriCodes } from "../utils/regionTier";
import MatrixStatsTable from "./MatrixStatsTable";
import PaidMatrixYearlyModal from "./PaidMatrixYearlyModal";
import StatsTable from "./StatsTable";

export default function PaidAnalysisPanel() {
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

  const { data: regions = [] } = useQuery({
    queryKey: ["regions"],
    queryFn: () => fetchRegions(),
  });

  const resolvedCodes = useMemo(
    () => resolveBeopjungriCodes(regions, tierSelection),
    [regions, tierSelection]
  );

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

      const base = buildPaidPayload(
        paidRequest,
        resolvedCodes,
        paidRoadExcluded,
        paidAreaExcluded,
        paidBasicBaseKey
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
    [paidRequest, resolvedCodes, paidRoadExcluded, paidAreaExcluded, paidBasicBaseKey]
  );

  return (
    <div className="space-y-4">
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
            거래량이 많으면 열 시간이 길어질 수 있습니다. 「이상치 제외」가 켜져 있으면 전체 거래 행을
            읽는 방식이라 더 느릴 수 있습니다.
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
        <div className="bg-white rounded-xl shadow-sm p-5 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-bold text-slate-800">필터 분석 결과</h2>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">{result.response_ms}ms</span>
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

          <MatrixStatsTable
            matrix={result.matrix}
            byZone={result.by_zone}
            byLandCategory={result.by_land_category}
            onPaidMatrixCellClick={openMatrixTrend}
          />

          {Object.keys(result.by_region).length > 1 && (
            <StatsTable
              title="지역별"
              rows={Object.entries(result.by_region).map(([k, v]) => ({
                label: k,
                stats: v,
              }))}
            />
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
