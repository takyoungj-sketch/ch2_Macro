import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { fetchCommercialFloorIndex, runCommercialCohortFloorIndex } from "../api/commercialClient";
import { buildCollectiveFloorIndexContext } from "../api/aiContext";
import type { CommercialAssetType } from "../types";
import type { CommercialModalScope } from "./CommercialClusterDetailModal";
import CommercialUtilityIndexHelp from "./CommercialUtilityIndexHelp";
import UtilityIndexResults from "./UtilityIndexResults";
import { COLLECTIVE_EXPERIMENT_MODE } from "../api/client";

type Dimension = "floor" | "area";

function regionParams(scope: CommercialModalScope) {
  return scope.hasIntermediate
    ? {
        addr1: scope.addr1,
        addr2: scope.addr2,
        addr3_list: scope.guList.length ? scope.guList : undefined,
        addr4_list: scope.leafList.length ? scope.leafList : undefined,
      }
    : {
        addr1: scope.addr1,
        addr2: scope.addr2,
        addr3_list: scope.leafList.length ? scope.leafList : undefined,
      };
}

export default function CommercialFloorIndexPanel({
  clusterKey,
  scope,
  count,
  isFactory = false,
  cohortKeys,
  cohortRunId = 0,
  analysisPeriod,
}: {
  clusterKey: string;
  scope: CommercialModalScope;
  count: number;
  isFactory?: boolean;
  cohortKeys?: string[];
  cohortRunId?: number;
  analysisPeriod?: {
    contract_year_from?: number;
    contract_year_to?: number;
    contract_date_from?: string;
    contract_date_to?: string;
  };
}) {
  const useCohort = cohortRunId > 0 && (cohortKeys?.length ?? 0) > 1;
  const keys = useCohort ? cohortKeys! : [clusterKey];
  const [dimension, setDimension] = useState<Dimension>(isFactory ? "area" : "floor");
  const floorIndexEligible = count >= 50;
  const experiment = COLLECTIVE_EXPERIMENT_MODE;
  const gateTip = `${isFactory ? "면적대·층" : "층·면적"} 효용지수: 선택 구간 거래 ${count}건 (최소 50건 필요)`;

  const dimensionOptions: { id: Dimension; label: string }[] = isFactory
    ? [
        { id: "area", label: "면적대별" },
        { id: "floor", label: "층별(참고)" },
      ]
    : [
        { id: "floor", label: "층별" },
        { id: "area", label: "면적형별" },
      ];

  const q = useQuery({
    queryKey: [
      "comm-floor-index",
      useCohort ? keys.join("|") : clusterKey,
      scope,
      dimension,
      experiment,
      isFactory,
      cohortRunId,
      analysisPeriod,
    ],
    queryFn: () =>
      useCohort
        ? runCommercialCohortFloorIndex({
            cluster_keys: keys,
            asset_type:
              scope.assetType === "all" || scope.assetType.includes(",")
                ? undefined
                : (scope.assetType as CommercialAssetType),
            ...analysisPeriod,
            contract_year_from: scope.yearFrom === "" ? undefined : scope.yearFrom,
            contract_year_to: scope.yearTo === "" ? undefined : scope.yearTo,
            dimension,
            experiment,
            variables: { floor_mode: "relative" },
          })
        : fetchCommercialFloorIndex(clusterKey, {
            ...regionParams(scope),
            ...analysisPeriod,
            contract_year_from: scope.yearFrom === "" ? undefined : scope.yearFrom,
            contract_year_to: scope.yearTo === "" ? undefined : scope.yearTo,
            dimension,
            experiment,
          }),
    enabled: (!useCohort || cohortRunId > 0) && (floorIndexEligible || experiment),
  });
  const aiContext = useMemo(() => q.data ? buildCollectiveFloorIndexContext(q.data, {
    regionLabel: q.data.display_label,
    assetType: q.data.asset_type,
    cohort: useCohort,
    panel: "CommercialFloorIndexPanel",
  }) : null, [q.data, useCohort]);

  const header = <div className="flex items-center justify-between gap-2">
    <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100">{isFactory ? "면적대·층 효용지수" : "층·면적 효용지수"}</h3>
    <CommercialUtilityIndexHelp data={q.data} isFactory={isFactory} />
  </div>;
  if (!useCohort && !floorIndexEligible && !experiment) return <div className="space-y-3">{header}<p role="status" className="py-4 text-sm text-amber-700 dark:text-amber-300">{gateTip}</p></div>;
  if (useCohort && cohortRunId === 0) return <div className="space-y-3">{header}<p className="text-sm">추가 도로를 선택한 뒤 통합분석을 실행해 주세요.</p></div>;
  if (q.isLoading) return <div className="space-y-3">{header}<p role="status" className="py-4 text-sm text-slate-500 dark:text-slate-400">효용지수 계산 중…</p></div>;
  if (q.isError) {
    const msg = (q.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "효용지수를 불러오지 못했습니다.";
    return <div className="space-y-3">{header}<p role="alert" className="py-4 text-sm text-amber-700 dark:text-amber-300">{String(msg)}</p></div>;
  }
  if (!q.data) return null;
  const isArea = q.data.dimension === "area";
  const intro = isArea
    ? "분석에 포함된 다른 조건의 차이를 고려하여 면적 구간에 따른 가격 수준을 비교합니다. 기준 구간의 지수를 100으로 표시합니다."
    : "면적·연식·거래시점 등의 차이를 고려하여 층에 따른 가격 수준을 비교합니다. 기준층의 지수를 100으로 표시합니다.";
  return <UtilityIndexResults data={q.data} header={header} intro={intro} columnLabel={isArea ? isFactory ? "면적대" : "면적형" : "층 구간"} notice={<>
    {aiContext ? <PublishAiContext context={aiContext} /> : null}
    {useCohort && <p className="text-sm text-indigo-700 dark:text-indigo-300">현재 도로를 포함한 {keys.length}개 도로명 묶음의 통합 분석입니다.</p>}
    {!floorIndexEligible && <p className="text-sm text-amber-700 dark:text-amber-300">{gateTip} · 실험 모드 결과입니다.</p>}
  </>}>
    <div className="flex flex-wrap items-center gap-2"><span className="text-sm font-medium text-slate-600 dark:text-slate-300">분석 기준</span>
      <div className="inline-flex rounded-md border border-slate-200 bg-slate-50 p-0.5 dark:border-slate-600 dark:bg-slate-800" role="group" aria-label="효용지수 분석 기준">
        {dimensionOptions.map(({id,label}) => <button key={id} type="button" aria-pressed={dimension === id} className={clsx("rounded px-3 py-1.5 text-sm font-medium", dimension === id ? "bg-white text-slate-800 shadow-sm dark:bg-slate-700 dark:text-slate-100" : "text-slate-500 dark:text-slate-400")} onClick={() => setDimension(id)}>{label}</button>)}
      </div>
    </div>
  </UtilityIndexResults>;
}
