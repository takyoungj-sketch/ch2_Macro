import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchRegions } from "../api/client";
import {
  AREA_CATEGORIES,
  getPaidYearButtonYears,
  ROAD_CONDITIONS,
} from "../constants/paidFilters";
import { REGIONS_CATALOG_QUERY_KEY } from "../constants/regionsCatalog";
import { MAX_V2_STATS_BULK_CODES } from "../constants/v2BulkLimits";
import { MAX_PAID_LEAF_BEOPJUNGRI_PICK } from "../constants/tierPickLimits";
import { useAppStore } from "../store";
import { resolveUnionBeopjungriCodes } from "../utils/regionTier";
import { resolveUpperSingleFromTier } from "../utils/upperTierStats";
import { paidUsesCustomAreaSpan } from "../utils/paidFiltersMap";

export default function PaidFilterTable() {
  const {
    paidRequest,
    setPaidRequest,
    paidRoadExcluded,
    paidAreaExcluded,
    togglePaidRoadExclude,
    togglePaidAreaExclude,
    togglePaidYear,
    runPaidFilteredAnalysis,
    tierSelection,
  } = useAppStore();
  const [advanced, setAdvanced] = useState(false);
  const [filterError, setFilterError] = useState<string | null>(null);

  const yearOptions = useMemo(() => [...getPaidYearButtonYears()], []);
  const selectedYears = paidRequest.years ?? [];

  const { data: regions = [] } = useQuery({
    queryKey: REGIONS_CATALOG_QUERY_KEY,
    queryFn: () => fetchRegions(),
    staleTime: 6 * 60 * 60 * 1000,
  });
  const resolvedRegionCodes = useMemo(
    () => resolveUnionBeopjungriCodes(regions, tierSelection),
    [regions, tierSelection]
  );
  const upperOnlySelection = useMemo(() => resolveUpperSingleFromTier(tierSelection), [tierSelection]);
  const customAreaSpan = paidUsesCustomAreaSpan(paidRequest);

  const runFiltered = () => {
    setFilterError(null);
    if (resolvedRegionCodes.length === 0) {
      setFilterError("먼저 지역을 입력하고 기본 통계 보기까지 반영해 주세요.");
      return;
    }
    if ((paidRequest.years ?? []).length === 0) {
      setFilterError("분석할 연도를 하나 이상 선택해 주세요.");
      return;
    }
    if (customAreaSpan) {
      const amin = paidRequest.area_sqm_min;
      const amax = paidRequest.area_sqm_max;
      const hasLo = amin != null && Number.isFinite(amin);
      const hasHi = amax != null && Number.isFinite(amax);
      if (!hasLo && !hasHi) {
        setFilterError("면적 최소 또는 최대(㎡) 중 하나 이상 입력하세요.");
        return;
      }
      if (hasLo && amin! <= 0) {
        setFilterError("면적 최소(㎡)는 0보다 커야 합니다.");
        return;
      }
      if (hasHi && amax! <= 0) {
        setFilterError("면적 최대(㎡)는 0보다 커야 합니다.");
        return;
      }
      if (hasLo && hasHi && amin! > amax!) {
        setFilterError("면적 최소(㎡)는 최대(㎡)보다 클 수 없습니다.");
        return;
      }
    }
    void runPaidFilteredAnalysis(resolvedRegionCodes);
  };

  return (
    <div className="border border-slate-200 rounded-xl bg-white text-xs text-slate-700 overflow-hidden">
      <table className="w-full border-collapse">
        <tbody>
          <tr className="border-b border-slate-100 align-top">
            <th className="w-[6.75rem] align-top px-2 py-2 bg-slate-50 text-[11px] font-semibold text-slate-600 text-left">
              연도
            </th>
            <td className="px-2 py-2">
              <p className="text-[10px] text-slate-500 mb-1.5">
                클릭으로 포함·제외합니다. 선택된 해에만 따라 집계됩니다 (비연속 가능).
                기본통계 표에 없던 연도만 골라도, 후보 거래 행에는 칩에 나온 연도(올해 기준 과거 최대 5개년)까지 포함됩니다.
              </p>
              <div className="flex flex-wrap gap-1">
                {yearOptions.map((y) => {
                  const on = selectedYears.includes(y);
                  const yy = String(y % 100).padStart(2, "0");
                  return (
                    <button
                      key={y}
                      type="button"
                      onClick={() => togglePaidYear(y)}
                      disabled={on && selectedYears.length <= 1}
                      title={String(y)}
                      className={`min-w-[2.35rem] px-1 py-1 rounded text-[11px] font-semibold border transition-colors ${
                        on
                          ? "bg-blue-600 text-white border-blue-600"
                          : "bg-white text-slate-500 border-slate-300 hover:border-blue-400"
                      } disabled:opacity-40`}
                    >
                      {yy}
                    </button>
                  );
                })}
              </div>
            </td>
          </tr>

          <tr className="border-b border-slate-100 align-top">
            <th className="align-top px-2 py-2 bg-slate-50 text-[11px] font-semibold text-slate-600 text-left leading-snug">
              도로조건
              <span className="block font-normal text-[10px] text-slate-400 mt-0.5">
                ✓ 포함 · 체크 해제 시 제외(DB 축약명)
              </span>
            </th>
            <td className="px-2 py-1.5">
              <IncludeToggleGrid
                options={ROAD_CONDITIONS}
                excluded={paidRoadExcluded}
                onToggle={togglePaidRoadExclude}
              />
            </td>
          </tr>

          <tr className="border-b border-slate-100 align-top">
            <th className="align-top px-2 py-2 bg-slate-50 text-[11px] font-semibold text-slate-600 text-left leading-snug">
              면적구분
              <span className="block font-normal text-[10px] text-slate-400 mt-0.5">
                ✓ 포함 · 체크 해제 시 제외
              </span>
            </th>
            <td className="px-2 py-1.5">
              <div className={customAreaSpan ? "opacity-45 pointer-events-none" : ""}>
                <IncludeToggleGrid
                  options={AREA_CATEGORIES}
                  excluded={paidAreaExcluded}
                  onToggle={togglePaidAreaExclude}
                />
              </div>
              {customAreaSpan && (
                <p className="text-[10px] text-amber-800 mt-1 leading-snug">
                  면적(㎡) 직접 범위를 쓰는 동안에는 광소·정상·광대 구분이 적용되지 않습니다.
                </p>
              )}
            </td>
          </tr>

          <tr className="border-b border-slate-100 align-top">
            <th className="align-top px-2 py-2 bg-slate-50 text-[11px] font-semibold text-slate-600 text-left leading-snug">
              면적(㎡) 범위
              <span className="block font-normal text-[10px] text-slate-400 mt-0.5">
                선택 시 계약면적만 필터 (광소/정상/광대 무시)
              </span>
            </th>
            <td className="px-2 py-2 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <label className="flex items-center gap-1 text-[11px] text-slate-600">
                  <span className="text-slate-500 w-8 shrink-0">최소</span>
                  <input
                    type="number"
                    min={0}
                    step={0.01}
                    placeholder="—"
                    value={paidRequest.area_sqm_min ?? ""}
                    onChange={(e) => {
                      const raw = e.target.value.trim();
                      if (raw === "") {
                        setPaidRequest({ area_sqm_min: null });
                        return;
                      }
                      const n = Number(raw);
                      setPaidRequest({
                        area_sqm_min: Number.isFinite(n) ? n : null,
                      });
                    }}
                    className="w-24 rounded border border-slate-200 px-1.5 py-0.5 text-[11px] tabular-nums"
                  />
                </label>
                <span className="text-slate-300">~</span>
                <label className="flex items-center gap-1 text-[11px] text-slate-600">
                  <span className="text-slate-500 w-8 shrink-0">최대</span>
                  <input
                    type="number"
                    min={0}
                    step={0.01}
                    placeholder="—"
                    value={paidRequest.area_sqm_max ?? ""}
                    onChange={(e) => {
                      const raw = e.target.value.trim();
                      if (raw === "") {
                        setPaidRequest({ area_sqm_max: null });
                        return;
                      }
                      const n = Number(raw);
                      setPaidRequest({
                        area_sqm_max: Number.isFinite(n) ? n : null,
                      });
                    }}
                    className="w-24 rounded border border-slate-200 px-1.5 py-0.5 text-[11px] tabular-nums"
                  />
                </label>
                <button
                  type="button"
                  className="text-[10px] text-blue-600 underline-offset-2 hover:underline"
                  onClick={() => setPaidRequest({ area_sqm_min: null, area_sqm_max: null })}
                >
                  범위 지우기
                </button>
              </div>
              <p className="text-[10px] text-slate-400 leading-snug">
                한쪽만 넣으면 반대쪽은 제한 없음. 비우면 다시 면적구분(광소·정상·광대) 칩이 적용됩니다.
              </p>
            </td>
          </tr>

          <tr className="align-top">
            <th className="align-top px-2 py-2 bg-slate-50 text-[11px] font-semibold text-slate-600 text-left">
              지분거래
            </th>
            <td className="px-2 py-2">
              <label className="flex items-center gap-1.5 text-[11px] text-slate-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={paidRequest.exclude_partial}
                  onChange={(e) =>
                    setPaidRequest({ exclude_partial: e.target.checked })
                  }
                  className="rounded"
                />
                지분거래 제외
              </label>
            </td>
          </tr>

          <tr className="border-t border-slate-100 bg-slate-50/60">
            <td colSpan={2} className="px-2 py-1">
              <button
                type="button"
                className="text-[11px] text-blue-600 font-medium underline-offset-2 hover:underline"
                onClick={() => setAdvanced((v) => !v)}
              >
                {advanced ? "고급 필터 접기" : "고급 필터 (이상치)"}
              </button>
            </td>
          </tr>

          {advanced && (
            <>
              <tr className="border-t border-slate-100 align-top">
                <th className="px-2 py-2 bg-slate-50 text-[11px] font-semibold text-slate-600 text-left whitespace-nowrap">
                  이상치
                </th>
                <td className="px-2 py-2 space-y-2">
                  <label className="flex items-center gap-1.5 text-[11px] text-slate-600 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={paidRequest.exclude_outlier}
                      onChange={(e) =>
                        setPaidRequest({ exclude_outlier: e.target.checked })
                      }
                      className="rounded"
                    />
                    단가 Tukey 펜스로 이상치 제외 후 집계 (Q1−k×IQR ~ Q3+k×IQR)
                  </label>
                  <div
                    className={`flex flex-wrap items-center gap-2 pt-0.5 ${
                      paidRequest.exclude_outlier ? "" : "opacity-40 pointer-events-none"
                    }`}
                    aria-disabled={!paidRequest.exclude_outlier}
                  >
                    <span className="text-[10px] text-slate-500 shrink-0">IQR 배수 k:</span>
                    {([1.5, 2, 3] as const).map((k) => (
                      <label
                        key={k}
                        className={`inline-flex items-center gap-0.5 text-[11px] cursor-pointer ${paidRequest.outlier_iqr_multiplier === k ? "text-blue-700 font-semibold" : "text-slate-600"}`}
                      >
                        <input
                          type="radio"
                          name="outlier-iqr-k"
                          className="rounded-full border-slate-300"
                          checked={paidRequest.outlier_iqr_multiplier === k}
                          onChange={() => setPaidRequest({ outlier_iqr_multiplier: k })}
                          disabled={!paidRequest.exclude_outlier}
                        />
                        {k}
                      </label>
                    ))}
                  </div>
                  <p className="text-[10px] text-slate-400 leading-snug">
                    k가 작을수록 더 많은 극단 단가가 제외됩니다. 기존 고정값은 k=3(보수적)에 해당합니다.
                  </p>
                </td>
              </tr>
            </>
          )}

          <tr className="border-t border-slate-200 bg-slate-50/80">
            <td colSpan={2} className="p-3">
              <p className="text-[10px] text-slate-600 leading-relaxed mb-2">
                <span className="font-semibold text-slate-700">필터 분석에 쓰이는 법정동·리 코드</span>:{" "}
                <span className="tabular-nums font-bold text-indigo-800">
                  {resolvedRegionCodes.length.toLocaleString()}
                </span>
                곳 (지역 선택이 카탈로그에서 확장된 수). 동·리 법정단위 줄과 읍·면 행정 단위 칩을 합쳐 선택한 개수 최대{" "}
                {MAX_PAID_LEAF_BEOPJUNGRI_PICK}곳까지입니다. 상위 행정(시도·구·읍면동·[시] 등)만 골라도 매칭되는
                동·리 코드 전부가 포함됩니다.
                {resolvedRegionCodes.length > MAX_V2_STATS_BULK_CODES ? (
                  <span className="block mt-1.5 text-amber-900/90">
                    기본통계 벌크 선조회(/free/v2/stats/bulk)는 코드{" "}
                    <span className="tabular-nums">{MAX_V2_STATS_BULK_CODES}</span>
                    건 한도입니다. 초과하면 선조회에 실패할 수 있고, 그때는 동일 선택의 전 코드로 거래 원장 집계로
                    이어져 기본통계 카드와 표본이 달라질 수 있습니다(화면 안내 참고).
                  </span>
                ) : null}
                {upperOnlySelection != null && resolvedRegionCodes.length > 0 ? (
                  <span className="block mt-1.5 text-slate-500">
                    지금은 상위 행정만 선택된 상태입니다. 위 기본통계 카드가 사전집계라면 필터 분석은 산하{" "}
                    {resolvedRegionCodes.length.toLocaleString()}곳을 원장에서 다시 거릅니다.
                  </span>
                ) : null}
              </p>
              {filterError ? (
                <p className="text-[11px] text-red-600 mb-2">{filterError}</p>
              ) : null}
              <button
                type="button"
                onClick={runFiltered}
                className="w-full py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 shadow-sm transition-colors"
              >
                필터 분석 실행
              </button>
              <p className="mt-2 text-[10px] text-slate-500 text-center">
                위 설정(연도·도로·면적 등)으로 용도×지목 매트릭스를 만듭니다.
              </p>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function IncludeToggleGrid({
  options,
  excluded,
  onToggle,
}: {
  options: readonly string[];
  excluded: readonly string[];
  onToggle: (value: string) => void;
}) {
  const includedCount = options.filter((o) => !excluded.includes(o)).length;
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1.5 leading-tight">
      {options.map((opt) => {
        const included = !excluded.includes(opt);
        return (
          <label
            key={opt}
            className={`inline-flex items-center gap-1 text-[10px] text-slate-700 cursor-pointer select-none ${included && includedCount <= 1 ? "opacity-90" : ""}`}
          >
            <input
              type="checkbox"
              checked={included}
              disabled={included && includedCount <= 1}
              onChange={() => onToggle(opt)}
              className="rounded border-slate-300 shrink-0"
            />
            <span>{opt}</span>
          </label>
        );
      })}
    </div>
  );
}
