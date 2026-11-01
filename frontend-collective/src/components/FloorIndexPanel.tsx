import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { fetchBuildingFloorIndex, runCohortFloorIndex } from "../api/client";
import type { AssetType } from "../types";
import { buildAnalysisPeriodParams } from "../utils/analysisPeriod";
import ResidentialUtilityIndexHelp from "./ResidentialUtilityIndexHelp";
import UtilityIndexResults from "./UtilityIndexResults";
import { type FloorMode } from "./BuildingRegressionPanel";

const FLOOR_MODE_OPTIONS: { value: FloorMode; label: string }[] = [
  { value: "relative", label: "상대층" },
  { value: "dummy", label: "층별" },
  { value: "grouped", label: "층 구간 (1~5 / 6~15 / 16층 이상)" },
];

type Dimension = "floor" | "dong" | "area" | "rights";

const DIMENSION_OPTIONS: { id: Dimension; label: string; show?: (assetType: AssetType) => boolean }[] = [
  { id: "floor", label: "층별" },
  { id: "dong", label: "동별", show: (t) => t === "apartment" || t === "rowhouse" },
  { id: "rights", label: "권리별", show: (t) => t === "presale" },
  { id: "area", label: "면적형별" },
];

function dimensionColumnLabel(dim: string) {
  if (dim === "dong") return "동";
  if (dim === "rights") return "권리";
  if (dim === "area") return "면적형";
  return "층";
}

export default function FloorIndexPanel({
  buildingKey,
  cohortKeys,
  cohortRunId = 0,
  assetType,
  yearFrom,
  yearTo,
  periodStart,
  periodEnd,
  experiment = false,
  floorIndexEligible = true,
  gateTip,
}: {
  buildingKey: string;
  cohortKeys?: string[];
  cohortRunId?: number;
  assetType: AssetType;
  yearFrom?: number;
  yearTo?: number;
  periodStart?: string | null;
  periodEnd?: string | null;
  experiment?: boolean;
  floorIndexEligible?: boolean;
  gateTip?: string;
}) {
  const [dimension, setDimension] = useState<Dimension>("floor");
  const [floorMode, setFloorMode] = useState<FloorMode>(assetType === "rowhouse" ? "rowhouse" : "relative");
  const floorModeOptions: { value: FloorMode; label: string }[] =
    assetType === "rowhouse"
      ? [
          { value: "rowhouse", label: "1층·중간·최상" },
          { value: "dummy", label: "층별" },
          { value: "grouped", label: "층 구간 (1~5 / 6~15 / 16층 이상)" },
        ]
      : FLOOR_MODE_OPTIONS;
  const toggles = DIMENSION_OPTIONS.filter((o) => !o.show || o.show(assetType));

  const useCohort = cohortRunId > 0 && (cohortKeys?.length ?? 0) > 1;
  const keys = useCohort ? cohortKeys! : [buildingKey];
  const periodParams = buildAnalysisPeriodParams(yearFrom, yearTo, periodStart, periodEnd);

  const singleQ = useQuery({
    queryKey: ["b-floor-index", buildingKey, dimension, floorMode, periodParams, experiment],
    queryFn: () =>
      fetchBuildingFloorIndex(buildingKey, {
        dimension,
        floor_mode: dimension === "floor" ? floorMode : undefined,
        ...periodParams,
        experiment,
      }),
    enabled: !useCohort,
  });

  const cohortQ = useQuery({
    queryKey: ["cohort-floor-index", keys.join("|"), dimension, floorMode, periodParams, experiment, cohortRunId],
    queryFn: () =>
      runCohortFloorIndex({
        building_keys: keys,
        asset_type: assetType,
        dimension,
        variables: { floor_mode: floorMode },
        ...periodParams,
        experiment,
      }),
    enabled: useCohort && cohortRunId > 0,
  });

  const q = useCohort ? cohortQ : singleQ;

  const header = <div className="flex items-center justify-between gap-2">
    <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100">{assetType === "presale" ? "층·권리·면적 효용지수" : "층·동·면적 효용지수"}</h3>
    <ResidentialUtilityIndexHelp data={q.data} assetType={assetType} />
  </div>;
  if (!useCohort && !floorIndexEligible && !experiment) return <div className="space-y-3">{header}<p role="status" className="text-sm text-amber-700 dark:text-amber-300">{gateTip ?? "효용지수 분석에 필요한 거래가 부족합니다."}</p></div>;
  if (q.isLoading) return <div className="space-y-3">{header}<p role="status" className="py-4 text-sm text-slate-500 dark:text-slate-400">효용지수 계산 중…</p></div>;
  if (q.isError) {
    const msg = (q.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "효용지수를 불러오지 못했습니다.";
    return <div className="space-y-3">{header}<p role="alert" className="py-4 text-sm text-amber-700 dark:text-amber-300">{String(msg)}</p></div>;
  }
  if (!q.data) return null;
  const dim = q.data.dimension;
  const intro = dim === "floor"
    ? "면적·연식·거래시점 등의 차이를 고려하여 층에 따른 가격 수준을 비교합니다. 기준층의 지수를 100으로 표시합니다."
    : `분석에 포함된 다른 조건의 차이를 고려하여 ${dim === "dong" ? "동" : dim === "rights" ? "권리" : "면적형"}에 따른 가격 수준을 비교합니다. 기준 구간의 지수를 100으로 표시합니다.`;
  return <UtilityIndexResults data={q.data} header={header} intro={intro} columnLabel={dimensionColumnLabel(dim)} notice={<>
    {useCohort && <p className="text-sm text-indigo-700 dark:text-indigo-300">현재 단지를 포함한 {keys.length}개 단지 통합 분석입니다.</p>}
    {!useCohort && !floorIndexEligible && <p className="text-sm text-amber-700 dark:text-amber-300">{gateTip ?? "권장 표본 기준 미달"} · 실험 모드 결과입니다.</p>}
  </>}>
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm font-medium text-slate-600 dark:text-slate-300">분석 기준</span>
      <div className="inline-flex rounded-md border border-slate-200 bg-slate-50 p-0.5 dark:border-slate-600 dark:bg-slate-800" role="group" aria-label="효용지수 분석 기준">
        {toggles.map(({id,label}) => <button key={id} type="button" aria-pressed={dimension === id} className={clsx("rounded px-3 py-1.5 text-sm font-medium", dimension === id ? "bg-white text-slate-800 shadow-sm dark:bg-slate-700 dark:text-slate-100" : "text-slate-500 dark:text-slate-400")} onClick={() => setDimension(id)}>{label}</button>)}
      </div>
      {dimension === "floor" && <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">층 구분<select aria-label="층 구분" className="rounded border border-slate-200 bg-white px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-900" value={floorMode} onChange={e => setFloorMode(e.target.value as FloorMode)}>{floorModeOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>}
    </div>
  </UtilityIndexResults>;
}
