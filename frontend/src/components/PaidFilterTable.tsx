import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchRegions } from "../api/client";
import {
  AREA_CATEGORIES,
  getPaidYearButtonYears,
  ROAD_CONDITIONS,
} from "../constants/paidFilters";
import { REGIONS_CATALOG_QUERY_KEY } from "../constants/regionsCatalog";
import { useAppStore } from "../store";
import type { TwinCitySearchTarget } from "../types";
import { resolveUnionBeopjungriCodes } from "../utils/regionTier";
import { resolveTwinAnchorEupmyeondong, resolveTwinAnchorSigungu, resolveTwinV8Query } from "../utils/twinRegionAnchor";
import TwinCityModal from "./TwinCityModal";
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
  const [twinModalTarget, setTwinModalTarget] = useState<TwinCitySearchTarget | null>(null);

  const yearOptions = useMemo(() => [...getPaidYearButtonYears()], []);
  const selectedYears = paidRequest.years ?? [];

  const { data: regions = [] } = useQuery({
    queryKey: REGIONS_CATALOG_QUERY_KEY,
    queryFn: () => fetchRegions(),
    staleTime: 6 * 60 * 60 * 1000,
  });
  const resolvedRegionCodes = useMemo(
    () => resolveUnionBeopjungriCodes(regions, tierSelection),
    [regions, tierSelection],
  );

  const twinEupAnchor = useMemo(
    () => resolveTwinAnchorEupmyeondong(regions, resolvedRegionCodes),
    [regions, resolvedRegionCodes],
  );
  const twinSigunguAnchor = useMemo(
    () => resolveTwinAnchorSigungu(regions, resolvedRegionCodes),
    [regions, resolvedRegionCodes],
  );
  const twinV8Query = useMemo(
    () => resolveTwinV8Query(regions, resolvedRegionCodes),
    [regions, resolvedRegionCodes],
  );
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

  const openTwinModal = () => {
    setFilterError(null);
    if (resolvedRegionCodes.length === 0) {
      setFilterError("먼저 지역을 선택해 주세요.");
      return;
    }
    if (twinEupAnchor != null) {
      setTwinModalTarget({ kind: "eupmyeondong", anchor: twinEupAnchor });
      return;
    }
    if (twinSigunguAnchor != null) {
      setTwinModalTarget({ kind: "sigungu", anchor: twinSigunguAnchor });
      return;
    }
    setFilterError(
      "쌍둥이 도시: 동일 읍면동 또는 동일 시군구로 줄인 뒤 조회할 수 있습니다. 지금은 여러 시군구가 섞였거나, 카탈로그와 매칭되지 않았습니다. 시·군·구 한 곳만 선택해 보세요.",
    );
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
                    이상치 제외 (IQR)
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
                </td>
              </tr>
            </>
          )}

          <tr className="border-t border-slate-200 bg-slate-50/80">
            <td colSpan={2} className="p-3">
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
              <button
                type="button"
                onClick={openTwinModal}
                className="w-full mt-2 py-2 rounded-lg border border-slate-300 bg-white text-slate-800 text-sm font-semibold hover:bg-slate-50 shadow-sm transition-colors"
              >
                쌍둥이 도시 찾기
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <TwinCityModal
        open={twinModalTarget != null}
        onClose={() => setTwinModalTarget(null)}
        target={twinModalTarget}
        v8Query={twinV8Query}
      />
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
