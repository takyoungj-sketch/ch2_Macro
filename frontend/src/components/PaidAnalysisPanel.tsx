import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { fetchPaidMatrixYearly, fetchRegions, runPaidAnalysis } from "../api/client";
import { useAppStore } from "../store";
import type { MatrixYearlyRequest } from "../types";
import { parseApiError } from "../utils/apiError";
import { buildPaidPayload } from "../utils/paidAnalysisPayload";
import { resolveBeopjungriCodes } from "../utils/regionTier";
import MatrixStatsTable from "./MatrixStatsTable";
import PaidMatrixYearlyModal from "./PaidMatrixYearlyModal";
import StatsTable from "./StatsTable";

export default function PaidAnalysisPanel() {
  const {
    tierSelection,
    paidRequest,
    paidRoadExcluded,
    paidAreaExcluded,
    paidRunKick,
    bumpPaidRunKick,
  } = useAppStore();
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

  const mutation = useMutation({
    mutationFn: runPaidAnalysis,
  });

  const [analyzeWaitSec, setAnalyzeWaitSec] = useState(0);
  useEffect(() => {
    if (!mutation.isPending) {
      setAnalyzeWaitSec(0);
      return;
    }
    const t0 = Date.now();
    const id = window.setInterval(() => {
      setAnalyzeWaitSec(Math.floor((Date.now() - t0) / 1000));
    }, 400);
    return () => window.clearInterval(id);
  }, [mutation.isPending]);

  const lastHandledKick = useRef(0);
  useEffect(() => {
    if (paidRunKick <= 0 || paidRunKick === lastHandledKick.current) return;
    lastHandledKick.current = paidRunKick;
    const st = useAppStore.getState();
    const codes = st.tierSelection.beopjungri_codes;
    if (codes.length === 0) return;
    mutation.mutate(
      buildPaidPayload(
        st.paidRequest,
        codes,
        st.paidRoadExcluded,
        st.paidAreaExcluded
      )
    );
  }, [paidRunKick, mutation]);

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
        paidAreaExcluded
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
    [paidRequest, resolvedCodes, paidRoadExcluded, paidAreaExcluded]
  );

  const result = mutation.data ?? null;
  const apiErr = mutation.isError ? parseApiError(mutation.error) : null;

  return (
    <div className="space-y-4">
      {mutation.isPending && (
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
        </div>
      )}

      {apiErr != null && (
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

      {result && (
        <div className="bg-white rounded-xl shadow-sm p-5 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-bold text-slate-800">필터 분석 결과</h2>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">{result.response_ms}ms</span>
              <button
                type="button"
                onClick={() => bumpPaidRunKick()}
                disabled={resolvedCodes.length === 0 || mutation.isPending}
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

      {!result && !mutation.isPending && !mutation.isError && (
        <p className="text-center text-[11px] text-slate-400">
          왼쪽 필터 표 하단의{" "}
          <strong className="text-slate-600">필터 분석 실행</strong>으로 조건을 적용한 매트릭스를
          불러옵니다. 셀 클릭 시 연도별 단가 추이가 열립니다.
        </p>
      )}
    </div>
  );
}
