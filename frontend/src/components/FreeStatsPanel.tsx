import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchFreeStats, fetchFreeStatsBulk, fetchPaidMatrixYearly, fetchRegions } from "../api/client";
import { yearsRangeInclusive } from "../constants/paidFilters";
import { REGIONS_CATALOG_QUERY_KEY } from "../constants/regionsCatalog";
import { useAppStore } from "../store";
import type { MatrixYearlyRequest } from "../types";
import { parseApiError } from "../utils/apiError";
import { resolveUnionBeopjungriCodes } from "../utils/regionTier";
import MatrixStatsTable, { MatrixStatsLegend } from "./MatrixStatsTable";
import PaidMatrixYearlyModal from "./PaidMatrixYearlyModal";
import YearlyStatsTable from "./YearlyStatsTable";

export default function FreeStatsPanel() {
  const viewMode = useAppStore((s) => s.viewMode);
  const paidResultView = useAppStore((s) => s.paidResultView);
  const paidBasicStatsKick = useAppStore((s) => s.paidBasicStatsKick);
  const setPaidBasicBaseKey = useAppStore((s) => s.setPaidBasicBaseKey);
  const setPaidRequest = useAppStore((s) => s.setPaidRequest);
  const paidBasicBaseKey = useAppStore((s) => s.paidBasicBaseKey);
  const { tierSelection } = useAppStore();

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

  const isPaidBasic = viewMode === "paid" && paidResultView === "basic";
  const bulkKey = [...resolvedCodes].slice().sort().join(",");
  const useBulk = isPaidBasic && resolvedCodes.length > 1;

  const canFetch =
    resolvedCodes.length > 0 &&
    !regionsLoading &&
    (useBulk ||
      (viewMode === "free" && resolvedCodes.length === 1) ||
      (isPaidBasic && resolvedCodes.length === 1));

  const { data, isLoading, isError, error } = useQuery({
    queryKey: useBulk
      ? ["freeStatsBulk", bulkKey, paidBasicStatsKick]
      : ["freeStats", resolvedCodes[0] ?? "", paidBasicStatsKick, viewMode],
    queryFn: () =>
      useBulk
        ? fetchFreeStatsBulk(resolvedCodes)
        : fetchFreeStats(resolvedCodes[0]!),
    enabled: canFetch,
  });

  useEffect(() => {
    if (!isPaidBasic) return;
    setPaidBasicBaseKey(data?.analysis_base_key ?? null);
  }, [data?.analysis_base_key, isPaidBasic, setPaidBasicBaseKey]);

  /** 기본 통계 창과 동일 연도(year_from∼year_to)로 필터 칩 동기화 */
  useEffect(() => {
    if (!isPaidBasic || data == null) return;
    const next = yearsRangeInclusive(data.year_from, data.year_to);
    if (next.length === 0) return;
    setPaidRequest({ years: next, year_from: null, year_to: null });
  }, [isPaidBasic, paidBasicStatsKick, data?.year_from, data?.year_to, setPaidRequest]);

  const closeTrend = () => {
    setTrendModal(null);
    setTrendRequest(null);
    setTrendLoading(false);
    setTrendError(null);
    setTrendRows([]);
  };

  const openMatrixTrend = useCallback(
    async (zoneType: string, landCategory: string) => {
      if (!isPaidBasic || resolvedCodes.length === 0) return;
      const statsData = data;
      if (!statsData) {
        setTrendError("통계 데이터가 없습니다.");
        setTrendModal({ zoneType, landCategory });
        setTrendRequest(null);
        setTrendLoading(false);
        return;
      }

      const baseKey = statsData.analysis_base_key ?? paidBasicBaseKey;
      const codesForTrend = (
        statsData.beopjungri_code
          ?.split(",")
          .map((x) => x.trim())
          .filter(Boolean) ?? resolvedCodes
      );
      const body: MatrixYearlyRequest = {
        region_selections: null,
        region_codes: codesForTrend,
        year_from: statsData.year_from,
        year_to: statsData.year_to,
        years: null,
        base_cache_key: baseKey,
        road_conditions: null,
        area_categories: null,
        land_categories: null,
        zone_types: null,
        exclude_partial: false,
        exclude_outlier: false,
        outlier_iqr_multiplier: 3,
        zone_type: zoneType,
        land_category: landCategory,
      };

      setTrendModal({ zoneType, landCategory });
      setTrendRequest(body);
      setTrendLoading(true);
      setTrendError(null);
      setTrendRows([]);
      try {
        const res = await fetchPaidMatrixYearly(body);
        setTrendRows(res.rows ?? []);
      } catch (e) {
        setTrendError(parseApiError(e).message);
      } finally {
        setTrendLoading(false);
      }
    },
    [isPaidBasic, resolvedCodes, data, paidBasicBaseKey]
  );

  if (regionsLoading)
    return (
      <div className="bg-white rounded-xl shadow-sm p-6 text-center text-slate-400 text-sm">
        지역 목록 불러오는 중…
      </div>
    );

  if (!canFetch && viewMode === "free" && resolvedCodes.length !== 1) {
    const n = resolvedCodes.length;
    return (
      <div className="bg-white rounded-xl shadow-sm p-6 text-center text-slate-500 text-sm space-y-2">
        <p>
          무료 통계는 <strong className="text-slate-800">법정단위가 정확히 1곳</strong>일 때만
          제공됩니다.
        </p>
        <p className="text-xs text-slate-400">
          {n === 0
            ? "좌측에서 시도·동 등을 선택해 조건을 맞추세요."
            : `현재 선택에 해당하는 법정동·리가 ${n}곳입니다. 조건을 좁히거나 법정동·리 하나만 지정해 주세요.`}
        </p>
      </div>
    );
  }

  if (!canFetch)
    return (
      <div className="bg-white rounded-xl shadow-sm p-6 text-center text-slate-500 text-sm space-y-2">
        <p>좌측에서 법정동·리를 매칭한 뒤 <strong className="text-slate-800">기본 통계 보기</strong>를 눌러 주세요.</p>
        <p className="text-xs text-slate-400">복수 동·면을 선택한 경우 선택한 모든 법정단위를 합산해 표시합니다.</p>
      </div>
    );

  if (isLoading)
    return (
      <div className="bg-white rounded-xl shadow-sm p-6 text-center text-slate-400 text-sm">
        통계 불러오는 중...
      </div>
    );

  if (isError || !data) {
    const apiErr = isError ? parseApiError(error) : null;
    return (
      <div className="bg-white rounded-xl shadow-sm p-6 text-center space-y-2">
        <p className="text-red-600 text-sm font-medium">
          데이터를 불러올 수 없습니다
          {apiErr?.message ? ` — ${apiErr.message}` : ""}
        </p>
        {apiErr?.status === 404 && (
          <p className="text-xs text-slate-500 leading-relaxed">
            복수 합산은 각 법정코드별 사전 집계와 원장 거래 단가 데이터가 필요합니다. 파이프라인에서 해당 지역 통계가
            생성되어 있는지 확인해 보세요.
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm p-5 space-y-5">
        {viewMode === "paid" && (
          <>
            <p className="text-[11px] text-indigo-700 font-medium leading-relaxed">
              유료 · 기본 통계
              {useBulk && (
                <span className="block text-indigo-600/90 font-normal mt-0.5">
                  선택 법정동·리 거래 단가를 합친 결과입니다. 매트릭스는 원장 기준 즉시 집계입니다.
                </span>
              )}
            </p>
            {Boolean(data.stats_excluded_codes?.length) && (
              <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-2 py-1.5 leading-snug">
                사전 집계가 없는 법정코드 {(data.stats_excluded_codes ?? []).length}건은 요청과 함께 보냈지만
                합산 표본에서는 자동으로 제외되었습니다. 예: {(data.stats_excluded_codes ?? [])
                  .slice(0, 8)
                  .join(", ")}
                {(data.stats_excluded_codes?.length ?? 0) > 8 ? " …" : ""}
              </p>
            )}
          </>
        )}
      <div className="flex flex-wrap items-start gap-3 gap-y-2">
        <h2 className="text-base font-bold text-slate-800 shrink-0 leading-tight max-w-md">
          {data.beopjungri_name}
        </h2>
        <div className="min-w-0 flex-1 basis-[12rem]">
          <YearlyStatsTable rows={data.by_year ?? []} hideTitle />
        </div>
        <div className="shrink-0">
          <MatrixStatsLegend />
        </div>
      </div>

      <MatrixStatsTable
        title=""
        matrix={data.matrix ?? []}
        byZone={data.by_zone}
        byLandCategory={data.by_land_category}
        showEmbeddedLegend={false}
        onPaidMatrixCellClick={isPaidBasic ? openMatrixTrend : undefined}
      />

      <PaidMatrixYearlyModal
        open={trendModal != null}
        onClose={closeTrend}
        loading={trendLoading}
        error={trendError}
        zoneType={trendModal?.zoneType ?? ""}
        landCategory={trendModal?.landCategory ?? ""}
        rows={trendRows}
        filterRequest={trendRequest}
        scopeNote="기본 통계에 표시된 지역·연도 범위가 적용됩니다. (유료 필터 표의 도로·면적 등은 이 단계에 포함되지 않습니다.)"
      />
    </div>
  );
}
