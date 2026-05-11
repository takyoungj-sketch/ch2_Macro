import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { runPaidAnalysis } from "../api/client";
import { useAppStore } from "../store";
import FilterPanel from "./FilterPanel";
import MatrixStatsTable from "./MatrixStatsTable";
import StatsTable from "./StatsTable";
import type { PaidAnalysisResponse } from "../types";

export default function PaidAnalysisPanel() {
  const { selectedCodes, paidRequest } = useAppStore();
  const [result, setResult] = useState<PaidAnalysisResponse | null>(null);

  const mutation = useMutation({
    mutationFn: runPaidAnalysis,
    onSuccess: (data) => setResult(data),
  });

  const handleRun = () => {
    if (selectedCodes.length === 0) return;
    mutation.mutate({ ...paidRequest, region_codes: selectedCodes });
  };

  return (
    <div className="space-y-4">
      <FilterPanel />

      <button
        onClick={handleRun}
        disabled={selectedCodes.length === 0 || mutation.isPending}
        className="w-full py-2 rounded-lg bg-blue-600 text-white text-sm font-semibold
                   hover:bg-blue-700 disabled:opacity-40 transition-colors"
      >
        {mutation.isPending ? "분석 중..." : `분석 실행 (${selectedCodes.length}개 지역)`}
      </button>

      {mutation.isError && (
        <p className="text-xs text-red-500 text-center">
          분석 중 오류가 발생했습니다.
        </p>
      )}

      {result && (
        <div className="bg-white rounded-xl shadow-sm p-5 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-slate-800">분석 결과</h2>
            <span className="text-xs text-slate-400">{result.response_ms}ms</span>
          </div>

          <StatsTable
            title="전체 통계"
            rows={[{ label: "전체", stats: result.total }]}
          />

          <MatrixStatsTable
            matrix={result.matrix}
            byZone={result.by_zone}
            byLandCategory={result.by_land_category}
          />

          {Object.keys(result.by_road_condition).length > 0 && (
            <StatsTable
              title="도로조건별"
              rows={Object.entries(result.by_road_condition).map(([k, v]) => ({
                label: k,
                stats: v,
              }))}
            />
          )}

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
    </div>
  );
}
