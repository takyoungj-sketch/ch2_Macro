import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchFreeStats, fetchFreeStatsBulk, fetchRegions } from "../api/client";
import { useAppStore } from "../store";
import { parseApiError } from "../utils/apiError";
import { resolveBeopjungriCodes } from "../utils/regionTier";
import MatrixStatsTable, { MatrixStatsLegend } from "./MatrixStatsTable";
import YearlyStatsTable from "./YearlyStatsTable";

export default function FreeStatsPanel() {
  const viewMode = useAppStore((s) => s.viewMode);
  const paidResultView = useAppStore((s) => s.paidResultView);
  const paidBasicStatsKick = useAppStore((s) => s.paidBasicStatsKick);
  const setPaidBasicBaseKey = useAppStore((s) => s.setPaidBasicBaseKey);
  const { tierSelection } = useAppStore();

  const { data: regions = [], isLoading: regionsLoading } = useQuery({
    queryKey: ["regions"],
    queryFn: () => fetchRegions(),
  });

  const resolvedCodes = useMemo(
    () => resolveBeopjungriCodes(regions, tierSelection),
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
        <p className="text-[11px] text-indigo-700 font-medium leading-relaxed">
          유료 · 기본 통계
          {useBulk && (
            <span className="block text-indigo-600/90 font-normal mt-0.5">
              선택 법정동·리 거래 단가를 합친 결과입니다. 매트릭스는 원장 기준 즉시 집계입니다.
            </span>
          )}
        </p>
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
      />
    </div>
  );
}
