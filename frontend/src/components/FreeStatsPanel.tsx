import { useQuery } from "@tanstack/react-query";
import { fetchFreeStats } from "../api/client";
import { useAppStore } from "../store";
import MatrixStatsTable, { MatrixStatsLegend } from "./MatrixStatsTable";
import YearlyStatsTable from "./YearlyStatsTable";

export default function FreeStatsPanel() {
  const { selectedCode } = useAppStore();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["freeStats", selectedCode],
    queryFn: () => fetchFreeStats(selectedCode!),
    enabled: !!selectedCode,
  });

  if (!selectedCode)
    return (
      <div className="bg-white rounded-xl shadow-sm p-6 text-center text-slate-400 text-sm">
        왼쪽에서 법정동/리를 선택하세요
      </div>
    );

  if (isLoading)
    return (
      <div className="bg-white rounded-xl shadow-sm p-6 text-center text-slate-400 text-sm">
        통계 불러오는 중...
      </div>
    );

  if (isError || !data)
    return (
      <div className="bg-white rounded-xl shadow-sm p-6 text-center text-red-400 text-sm">
        데이터를 불러올 수 없습니다
      </div>
    );

  return (
    <div className="bg-white rounded-xl shadow-sm p-5 space-y-5">
      <div className="flex flex-wrap items-start gap-3 gap-y-2">
        <h2 className="text-base font-bold text-slate-800 shrink-0 leading-tight">
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
