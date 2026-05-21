import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchFreeStats,
  fetchFreeStatsBulk,
  fetchPaidMatrixYearly,
  fetchRegions,
  fetchUpperStats,
} from "../api/client";
import { yearsRangeInclusive } from "../constants/paidFilters";
import { REGIONS_CATALOG_QUERY_KEY } from "../constants/regionsCatalog";
import { useAppStore } from "../store";
import { type FreeStatsV2Response, type MatrixYearlyRequest, normalizeFreeStatsWindowYears } from "../types";
import { parseApiError } from "../utils/apiError";
import { statsAsOfLabel, v2PeriodToYearRange } from "../utils/freeStatsV2";
import { resolveUnionBeopjungriCodes } from "../utils/regionTier";
import { statsScopeKeyFromBeopjungriCodes } from "../utils/statsScopeKey";
import { resolveUpperSingleFromTier, upperToFreeStatsShape } from "../utils/upperTierStats";
import MatrixStatsTable, { MatrixStatsLegend } from "./MatrixStatsTable";
import PaidMatrixYearlyModal from "./PaidMatrixYearlyModal";
import YearlyStatsTable from "./YearlyStatsTable";

export default function FreeStatsPanel() {
  const viewMode = useAppStore((s) => s.viewMode);
  const paidResultView = useAppStore((s) => s.paidResultView);
  const paidBasicStatsKick = useAppStore((s) => s.paidBasicStatsKick);
  const statsDisplayScopeKey = useAppStore((s) => s.statsDisplayScopeKey);
  const statsDisplayKick = useAppStore((s) => s.statsDisplayKick);
  const syncPaidBasicStatsMeta = useAppStore((s) => s.syncPaidBasicStatsMeta);
  const setPaidRequest = useAppStore((s) => s.setPaidRequest);
  const paidBasicBaseKey = useAppStore((s) => s.paidBasicBaseKey);
  const freeStatsWindowYears = useAppStore((s) =>
    normalizeFreeStatsWindowYears(s.freeStatsWindowYears)
  );
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

  /** 단일 상위 행정(시도·시군구·읍면동·city) 선택이면 상위 사전집계 API 사용 — resolveUpperSingleFromTier */
  const upperSingle = useMemo(() => resolveUpperSingleFromTier(tierSelection), [tierSelection]);

  const isPaidBasic = viewMode === "paid" && paidResultView === "basic";
  const useUpper = isPaidBasic && upperSingle != null;
  const useBulk =
    isPaidBasic && upperSingle == null && resolvedCodes.length > 1;
  const bulkKey = useMemo(
    () => statsScopeKeyFromBeopjungriCodes(resolvedCodes),
    [resolvedCodes]
  );
  const scopeOk =
    statsDisplayScopeKey != null &&
    statsDisplayScopeKey === bulkKey &&
    statsDisplayKick > 0;

  const canFetch =
    !regionsLoading &&
    (useUpper ||
      useBulk ||
      (resolvedCodes.length > 0 &&
        ((viewMode === "free" && resolvedCodes.length === 1) ||
          (isPaidBasic && resolvedCodes.length === 1))));

  const enabled = canFetch && scopeOk;

  const { data, isLoading, isError, error } = useQuery<FreeStatsV2Response>({
    queryKey: useUpper
      ? [
          "upperStats",
          upperSingle!.level,
          upperSingle!.code,
          paidBasicStatsKick,
          freeStatsWindowYears,
        ]
      : useBulk
      ? ["freeStatsBulkV2", bulkKey, paidBasicStatsKick, freeStatsWindowYears]
      : [
          "freeStatsV2",
          resolvedCodes[0] ?? "",
          paidBasicStatsKick,
          viewMode,
          freeStatsWindowYears,
        ],
    queryFn: async () => {
      if (useUpper) {
        const up = await fetchUpperStats(upperSingle!.level, upperSingle!.code, {
          window_years: freeStatsWindowYears,
        });
        return upperToFreeStatsShape(up);
      }
      if (useBulk) {
        return fetchFreeStatsBulk(resolvedCodes, {
          window_years: freeStatsWindowYears,
        });
      }
      return fetchFreeStats(resolvedCodes[0]!, {
        window_years: freeStatsWindowYears,
      });
    },
    enabled,
  });

  useEffect(() => {
    if (!isPaidBasic || data == null) return;
    /**
     * 단일 상위지역 모드: data.beopjungri_code 는 상위 region_code 라 paidBulkBeopjungriCodes
     * 에 잘못 들어가면 후속 분석에서 그 한 코드만 가지고 쿼리하게 된다.
     * 그 경우엔 base/code 메타를 null 로 리셋해 paidFiltered 분석이 resolvedCodes 를 다시 사용하게 함.
     */
    if (useUpper) {
      syncPaidBasicStatsMeta({ analysis_base_key: null, beopjungri_code: null });
      return;
    }
    syncPaidBasicStatsMeta({
      analysis_base_key: data.analysis_base_key ?? null,
      beopjungri_code: data.beopjungri_code ?? null,
    });
  }, [data, isPaidBasic, useUpper, syncPaidBasicStatsMeta]);

  /** 기본 통계 창과 동일 연도(period 달력 연도 범위)로 필터 칩 동기화 */
  useEffect(() => {
    if (!isPaidBasic || data == null) return;
    const { year_from, year_to } = v2PeriodToYearRange(data);
    const next = yearsRangeInclusive(year_from, year_to);
    if (next.length === 0) return;
    setPaidRequest({ years: next, year_from: null, year_to: null });
  }, [
    isPaidBasic,
    paidBasicStatsKick,
    data?.period_start,
    data?.period_end,
    setPaidRequest,
  ]);

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
      /**
       * 단일 상위지역 모드에서 statsData.beopjungri_code 는 region_code(시도/시군구/읍면동 코드)다.
       * 셀 트렌드 모달은 법정동·리 코드 리스트가 필요하므로 항상 resolvedCodes(산하 union)를 우선 사용.
       */
      const codesForTrend = useUpper
        ? resolvedCodes
        : statsData.beopjungri_code
            ?.split(",")
            .map((x) => x.trim())
            .filter(Boolean) ?? resolvedCodes;
      const { year_from, year_to } = v2PeriodToYearRange(statsData);
      const body: MatrixYearlyRequest = {
        region_selections: null,
        region_codes: codesForTrend,
        year_from,
        year_to,
        years: null,
        base_cache_key: baseKey,
        road_conditions: null,
        area_categories: null,
        area_sqm_min: null,
        area_sqm_max: null,
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
    [isPaidBasic, resolvedCodes, data, paidBasicBaseKey, useUpper]
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

  if (canFetch && !scopeOk) {
    return (
      <div className="bg-white rounded-xl shadow-sm p-6 text-center text-slate-500 text-sm space-y-2">
        <p>
          좌측에서 지역을 확정한 뒤{" "}
          <strong className="text-slate-800">
            {viewMode === "free" ? "무료 통계 조회" : "기본 통계 보기"}
          </strong>
          를 눌러 주세요.
        </p>
        <p className="text-xs text-slate-400">
          검색으로 칩만 바꾼 상태에서는 자동으로 불러오지 않습니다. 지역을 바꾼 뒤에는 버튼을 다시 눌러 주세요.
        </p>
      </div>
    );
  }

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
        {apiErr?.status === 503 && (
          <p className="text-xs text-slate-500 leading-relaxed">
            서버에 V2 사전집계 테이블(<code className="text-[11px]">land_basic_stats_v2</code>)이 없거나
            데이터가 적재되지 않았습니다. 시·도 등 상위 행정만 선택했다면{" "}
            <code className="text-[11px]">land_upper_stats_v2</code> 적재도 확인해 보세요. DB 마이그레이션과{" "}
            <code className="text-[11px]">build_stats_v2</code> · <code className="text-[11px]">build_upper_stats_v2</code>{" "}
            실행 여부를 확인합니다.
          </p>
        )}
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
              유료 · 기본 통계 (V2)
              {useUpper && (
                <span className="block text-indigo-600/90 font-normal mt-0.5">
                  시·도·시군구·읍면동·[시](자치구 묶음)만 단독 선택한 경우{" "}
                  <code className="text-[10px]">land_upper_stats_v2</code> 사전집계입니다. 아래는 롤링 계약 구간 매트릭스이며
                  필터표의 도로·면적 조건은 포함되지 않습니다.
                </span>
              )}
              {useBulk && (
                <span className="block text-indigo-600/90 font-normal mt-0.5">
                  선택 법정동·리 거래 단가를 합친 결과입니다. 매트릭스는 원장 기준 즉시 집계입니다.
                </span>
              )}
              {isPaidBasic && !useUpper && !useBulk && (
                <span className="block text-indigo-600/90 font-normal mt-0.5">
                  단일 동·리는 <code className="text-[10px]">land_basic_stats_v2</code> 사전집계(연도별 일부 원장)·롤링
                  매트릭스입니다.
                </span>
              )}
            </p>
            <p className="text-[10px] text-slate-500 leading-relaxed rounded-md bg-slate-50 border border-slate-100 px-2 py-1.5">
              <strong className="text-slate-600">필터 분석 실행</strong> 시에는 선택 범위의 법정동·리 거래 원장 위에 연도·도로·면적 등이
              적용됩니다. 같은 지역을 보더라도 숫자가 기본 통계 카드와 다를 수 있습니다.
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
        <p className="text-[11px] text-slate-500 leading-snug basis-full sm:basis-auto min-w-0">
          {/* DECISIONS D-002 — 「YYYY년 M월 말 기준」 통일 라벨 */}
          <span className="font-medium text-slate-700">
            {statsAsOfLabel({
              as_of_month: data.as_of_month,
              stats_reference_date: data.stats_reference_date,
            }) ?? `기준일 ${data.stats_reference_date ?? data.as_of_month}`}
          </span>
          <span className="text-slate-400">
            {" "}
            (계약일 구간{" "}
            <span className="tabular-nums">
              {data.period_start} ~ {data.period_end}
            </span>
            , {data.window_years}년 창)
          </span>
        </p>
        <div className="min-w-0 flex-1 basis-[12rem]">
          <p className="text-[10px] text-slate-400 mb-0.5 leading-snug">
            연도별 총계는 달력 연도(말 연도는 {String(data.period_end)}까지 포함). 아래 매트릭스는{" "}
            {data.window_years}년 롤링({String(data.period_start)} ~ {String(data.period_end)})입니다.
          </p>
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
