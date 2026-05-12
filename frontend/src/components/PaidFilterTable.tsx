import { useMemo, useState } from "react";
import {
  AREA_CATEGORIES,
  getPaidYearButtonYears,
  ROAD_CONDITIONS,
} from "../constants/paidFilters";
import { useAppStore } from "../store";

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

  const runFiltered = () => {
    setFilterError(null);
    if (tierSelection.beopjungri_codes.length === 0) {
      setFilterError("먼저 지역을 입력하고 기본 통계 보기까지 반영해 주세요.");
      return;
    }
    if ((paidRequest.years ?? []).length === 0) {
      setFilterError("분석할 연도를 하나 이상 선택해 주세요.");
      return;
    }
    void runPaidFilteredAnalysis();
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
              <IncludeToggleGrid
                options={AREA_CATEGORIES}
                excluded={paidAreaExcluded}
                onToggle={togglePaidAreaExclude}
              />
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
