import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchFreeStats,
  fetchFreeStatsBulk,
  fetchPaidMatrixYearly,
  fetchRegions,
  fetchUpperStats,
} from "../api/client";
import { MATRIX_MODE_LABEL, type MatrixMode } from "../constants/jimokGroup";
import { yearsRangeInclusive } from "../constants/paidFilters";
import {
  basicStatsActionLabel,
  rollingStatsCaption,
} from "../constants/landAnalysisLabels";
import { REGIONS_CATALOG_QUERY_KEY } from "../constants/regionsCatalog";
import {
  buildFreeStatsExplain,
  buildMatrixLegendExplain,
} from "../constants/landStatsExplain";
import { useAppStore } from "../store";
import { type FreeStatsV2Response, type MatrixYearlyRequest, type MatrixYearlyStat, normalizeFreeStatsWindowYears } from "../types";
import { parseApiError } from "../utils/apiError";
import {
  calendarYearReferenceRows,
  rollingMatrixModalPayload,
  v2PeriodToYearRange,
} from "../utils/freeStatsV2";
import { resolveUnionBeopjungriCodes } from "../utils/regionTier";
import { statsScopeKeyFromBeopjungriCodes } from "../utils/statsScopeKey";
import { resolveUpperSingleFromTier, upperToFreeStatsShape } from "../utils/upperTierStats";
import { shouldUseBulkStats } from "../utils/statsFetchStrategy";
import MatrixStatsTable, { MatrixStatsLegend } from "./MatrixStatsTable";
import PaidMatrixYearlyModal from "./PaidMatrixYearlyModal";
import YearlyStatsTable from "./YearlyStatsTable";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import RegionalProfileLink from "./RegionalProfileLink";

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

  const [matrixMode, setMatrixMode] = useState<MatrixMode>("category");
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

  /** 단일 상위 행정(시도·시군구·읍면동·city) 선택이면 상위 사전집계 API 사용 — resolveUpperSingleFromTier */
  const upperSingle = useMemo(() => resolveUpperSingleFromTier(tierSelection), [tierSelection]);

  /** 지역 선택이 바뀌면 항상 용도×지목(category)으로 복귀 — 지목군은 버튼으로만 */
  const regionScopeKey = useMemo(() => {
    if (upperSingle != null) {
      return `upper:${upperSingle.level}:${upperSingle.code}`;
    }
    return `beop:${statsScopeKeyFromBeopjungriCodes(resolvedCodes)}`;
  }, [upperSingle, resolvedCodes]);
  const prevRegionScopeKey = useRef<string | null>(null);
  useEffect(() => {
    const prev = prevRegionScopeKey.current;
    prevRegionScopeKey.current = regionScopeKey;
    if (prev === null || prev === regionScopeKey) return;
    setMatrixMode("category");
    setPaidRequest({ matrix_mode: "category" });
    setTrendModal(null);
    setTrendRequest(null);
    setTrendLoading(false);
    setTrendError(null);
    setTrendRows([]);
  }, [regionScopeKey, setPaidRequest]);

  const isPaidBasic = paidResultView === "basic";
  /** 단일 상위 행정(시도·시군구·읍면동·city) — upper mart 경로 (D-028) */
  const useUpper = upperSingle != null && isPaidBasic;
  const useBulk =
    isPaidBasic && shouldUseBulkStats(resolvedCodes.length, upperSingle);
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
      (resolvedCodes.length > 0 && isPaidBasic && resolvedCodes.length === 1));

  const enabled = canFetch && scopeOk;

  const { data, isLoading, isError, error } = useQuery<FreeStatsV2Response>({
    queryKey: useUpper
      ? [
          "upperStats",
          upperSingle!.level,
          upperSingle!.code,
          paidBasicStatsKick,
          freeStatsWindowYears,
          matrixMode,
        ]
      : useBulk
      ? ["freeStatsBulkV2", bulkKey, paidBasicStatsKick, freeStatsWindowYears, matrixMode]
      : [
          "freeStatsV2",
          resolvedCodes[0] ?? "",
          paidBasicStatsKick,
          viewMode,
          freeStatsWindowYears,
          matrixMode,
        ],
    queryFn: async () => {
      if (useUpper) {
        const up = await fetchUpperStats(upperSingle!.level, upperSingle!.code, {
          window_years: freeStatsWindowYears,
          matrix_mode: matrixMode,
        });
        return upperToFreeStatsShape(up);
      }
      if (useBulk) {
        return fetchFreeStatsBulk(resolvedCodes, {
          window_years: freeStatsWindowYears,
          matrix_mode: matrixMode,
        });
      }
      return fetchFreeStats(resolvedCodes[0]!, {
        window_years: freeStatsWindowYears,
        matrix_mode: matrixMode,
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

  const yearlyRowsFreeReference = useMemo(() => {
    if (!data) return [];
    const cal = calendarYearReferenceRows(data);
    if (cal && cal.length > 0) return cal;
    return data.by_year ?? [];
  }, [data]);

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
      const rollingExtras = rollingMatrixModalPayload(statsData);

      /**
       * 단일 상위지역(시군구·읍면동) 모드: 백엔드 expand_region_units 가 sigungu/eupmyeondong
       * scope_type 을 DB 기준 전체 법정동으로 확장하므로, resolvedCodes(카탈로그 cap 에 걸려
       * 불완전할 수 있음) 대신 scope 전달 방식을 사용한다.
       * 시도·city 레벨은 expand_region_units 미지원 → resolvedCodes 폴백.
       */
      const upperScope =
        upperSingle != null &&
        (upperSingle.level === "sigungu" || upperSingle.level === "eupmyeondong")
          ? { scope_type: upperSingle.level as "sigungu" | "eupmyeondong", code: upperSingle.code }
          : null;

      const codesForTrend = useUpper && upperScope == null
        ? resolvedCodes
        : useUpper
          ? null
          : statsData.beopjungri_code
              ?.split(",")
              .map((x) => x.trim())
              .filter(Boolean) ?? resolvedCodes;

      const body: MatrixYearlyRequest = {
        region_selections: upperScope != null ? [upperScope] : null,
        region_codes: codesForTrend,
        ...rollingExtras,
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
        matrix_mode: matrixMode,
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
    [isPaidBasic, resolvedCodes, data, paidBasicBaseKey, useUpper, upperSingle, matrixMode]
  );

  if (regionsLoading)
    return (
      <div className="bg-white rounded-xl shadow-sm p-6 text-center text-slate-400 text-sm">
        지역 목록 불러오는 중…
      </div>
    );

  if (!canFetch)
    return (
      <div className="bg-white rounded-xl shadow-sm p-6 text-center text-slate-500 text-sm">
        <p>
          좌측에서{" "}
          <strong className="text-slate-800">
            {basicStatsActionLabel("paid")} · {rollingStatsCaption(freeStatsWindowYears)}
          </strong>
          를 눌러 주세요.
        </p>
      </div>
    );

  if (canFetch && !scopeOk) {
    return (
      <div className="bg-white rounded-xl shadow-sm p-6 text-center text-slate-500 text-sm space-y-2">
        <p>
          <strong className="text-slate-800">
            {`${basicStatsActionLabel("paid")} · ${rollingStatsCaption(freeStatsWindowYears)}`}
          </strong>
          로 데이터를 불러옵니다.
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
      </div>
    );
  }

  const legendExplain = buildMatrixLegendExplain();
  const statsExplain = buildFreeStatsExplain({
    data,
    viewMode,
    isPaidBasic,
    windowYears: freeStatsWindowYears,
    useUpper,
    upperLevelLabel: upperSingle
      ? `${upperSingle.level} (${upperSingle.code})`
      : undefined,
  });

  return (
    <div className="bg-white rounded-xl shadow-sm p-5 space-y-5">
        {useUpper &&
          upperSingle?.level === "eupmyeondong" &&
          upperSingle.code.startsWith("361101") &&
          data.total.count === 0 && (
          <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-2 py-1.5 leading-snug">
            세종 행정동(361101xx) 거래는 현재 DB에 아직 집계되지 않았을 수 있습니다. 읍·면 단위(361103xx 등)는
            조회 가능합니다. 원천 엑셀·CSV 재적재 후 상위 통계가 채워집니다.
          </p>
        )}
        {Boolean(data.stats_excluded_codes?.length) && (
          <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-2 py-1.5 leading-snug">
            사전 집계가 없는 법정코드 {(data.stats_excluded_codes ?? []).length}건은 요청과 함께 보냈지만
            합산 표본에서는 자동으로 제외되었습니다. 예: {(data.stats_excluded_codes ?? [])
              .slice(0, 8)
              .join(", ")}
            {(data.stats_excluded_codes?.length ?? 0) > 8 ? " …" : ""}
          </p>
        )}
      <div className="flex flex-wrap items-stretch gap-3 gap-y-2">
        <div className="flex items-start gap-1 shrink-0 self-start max-w-md">
          <h2 className="text-base font-bold text-slate-800 leading-tight">
            {data.beopjungri_name}
          </h2>
          <AnalysisHelpPanel explain={statsExplain} />
          <RegionalProfileLink />
        </div>
        <div className="min-w-0 flex-1 basis-[12rem]">
          <YearlyStatsTable rows={yearlyRowsFreeReference} hideTitle />
        </div>
        <MatrixStatsLegend matchYearlyStatsHeight helpExplain={legendExplain} />
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
        <span className="font-medium text-slate-700">매트릭스</span>
        {(["category", "group"] as const).map((mode) => (
          <button
            key={mode}
            type="button"
            onClick={() => setMatrixMode(mode)}
            className={
              matrixMode === mode
                ? "rounded border border-slate-700 bg-slate-800 px-2 py-0.5 text-white"
                : "rounded border border-slate-300 bg-white px-2 py-0.5 hover:bg-slate-50"
            }
          >
            {MATRIX_MODE_LABEL[mode]}
          </button>
        ))}
      </div>

      <MatrixStatsTable
        title=""
        matrix={data.matrix ?? []}
        byZone={data.by_zone}
        byLandCategory={data.by_land_category}
        landAxisLabel={matrixMode === "group" ? "지목군" : "지목"}
        showEmbeddedLegend={false}
        onPaidMatrixCellClick={isPaidBasic ? openMatrixTrend : undefined}
        suppressEscapeClose={trendModal != null}
      />

      <PaidMatrixYearlyModal
        open={trendModal != null}
        onClose={closeTrend}
        loading={trendLoading}
        error={trendError}
        zoneType={trendModal?.zoneType ?? ""}
        landCategory={trendModal?.landCategory ?? ""}
        matrixMode={matrixMode}
        rows={trendRows}
        filterRequest={trendRequest}
      />
    </div>
  );
}
