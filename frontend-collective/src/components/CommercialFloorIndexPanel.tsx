import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import clsx from "clsx";
import { fetchCommercialFloorIndex, runCommercialCohortFloorIndex } from "../api/commercialClient";
import type { CommercialAssetType } from "../types";
import type { CommercialModalScope } from "./CommercialClusterDetailModal";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import FloorIndexMethodGuide from "./FloorIndexMethodGuide";
import { COLLECTIVE_EXPERIMENT_MODE } from "../api/client";
import { CLUSTER_FLOOR_INDEX_HELP } from "../utils/residentialAnalysisHelp";

function fmt(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function fmtP(v: number | null | undefined) {
  if (v == null) return "—";
  if (v < 0.001) return "<0.001";
  return v.toLocaleString(undefined, { maximumFractionDigits: 3 });
}

type Dimension = "floor" | "area";

const CONTROL_LABELS: Record<string, string> = {
  ln_gross_area: "ln(연면적)",
  ln_exclusive_area: "ln(연면적)",
  building_age: "연식",
  building_use: "건축물용도",
  shop_floor: "층 구간(1층 기준)",
  relative_floor: "상대 층구간",
  contract_period: "거래시점(반기)",
};

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

function dimensionHelpText(dim: string, isRegression: boolean, isFactory: boolean) {
  if (dim === "area") {
    if (isFactory) {
      return "공장 면적대는 연면적 100/300/1000㎡입니다. 기준은 표본 중앙값 칸=100.";
    }
    return "상가 면적형은 연면적 30㎡ 반올림입니다. 기준은 표본 중앙값 칸=100.";
  }
  if (isRegression) {
    return "상가·공장 층은 지하·1·2·저·중·고·초고층입니다. 1층=100. 지하를 중층부에 넣지 않습니다.";
  }
  if (isFactory) {
    return "층 정보가 적으면 지수가 비거나 참고용입니다. 면적대 탭을 우선하세요.";
  }
  return "1층=100 기준 층 구간 상대 지수입니다.";
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
            contract_year_from: scope.yearFrom === "" ? undefined : scope.yearFrom,
            contract_year_to: scope.yearTo === "" ? undefined : scope.yearTo,
            dimension,
            experiment,
          }),
    enabled: (!useCohort || cohortRunId > 0) && (floorIndexEligible || experiment),
  });

  if (!useCohort && !floorIndexEligible && !experiment) {
    return (
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-2">
          <p className="text-[11px] font-medium text-slate-700 inline-flex items-center gap-1">
            {isFactory ? "면적대·층 효용지수" : "층·면적 효용지수"}
            <StatsGlossaryHelp termId="floor_utility_index" size="xs" />
          </p>
          <AnalysisHelpPanel
            explain={CLUSTER_FLOOR_INDEX_HELP}
            buttonLabel="방법"
            title="층·면적 효용지수 산출 방법"
          />
        </div>
        <p className="text-xs text-amber-700 text-center py-6">{gateTip}</p>
      </div>
    );
  }

  if (useCohort && cohortRunId === 0) {
    return (
      <p className="text-xs text-slate-500 text-center py-6">
        코호트에 cluster를 추가한 뒤 「통합분석」을 누르면 통합 효용지수가 표시됩니다.
      </p>
    );
  }

  if (q.isLoading) {
    return (
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-2">
          <p className="text-[11px] font-medium text-slate-700 inline-flex items-center gap-1">
            {isFactory ? "면적대·층 효용지수" : "층·면적 효용지수"}
            <StatsGlossaryHelp termId="floor_utility_index" size="xs" />
          </p>
          <AnalysisHelpPanel
            explain={CLUSTER_FLOOR_INDEX_HELP}
            buttonLabel="방법"
            title="층·면적 효용지수 산출 방법"
          />
        </div>
        <p className="text-xs text-slate-400 text-center py-4">효용지수 계산 중…</p>
      </div>
    );
  }
  if (q.isError) {
    const msg =
      (q.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
      "효용지수를 불러오지 못했습니다.";
    return (
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-2">
          <p className="text-[11px] font-medium text-slate-700 inline-flex items-center gap-1">
            {isFactory ? "면적대·층 효용지수" : "층·면적 효용지수"}
            <StatsGlossaryHelp termId="floor_utility_index" size="xs" />
          </p>
          <AnalysisHelpPanel
            explain={CLUSTER_FLOOR_INDEX_HELP}
            buttonLabel="방법"
            title="층·면적 효용지수 산출 방법"
          />
        </div>
        <p className="text-xs text-amber-700 text-center py-4">{String(msg)}</p>
      </div>
    );
  }
  if (!q.data) return null;

  const {
    cells,
    baseline_median,
    n_total,
    n_regression,
    dimension: dim,
    method,
    reference_floor,
    controls,
    r_squared,
    warnings,
    explain,
  } = q.data;

  const isRegression = method === "regression_semilog";

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-medium text-slate-700 inline-flex items-center gap-1">
          {isFactory ? "면적대·층 효용지수" : "층·면적 효용지수"}
          <StatsGlossaryHelp termId="floor_utility_index" size="xs" />
        </p>
        <AnalysisHelpPanel
          explain={explain ?? CLUSTER_FLOOR_INDEX_HELP}
          buttonLabel="방법"
          title="층·면적 효용지수 산출 방법"
        />
      </div>

      <FloorIndexMethodGuide
        dimension={dimension}
        floorMode="shop"
        isCluster
        isFactory={isFactory}
        isRegression={isRegression}
        referenceLabel={reference_floor}
      />

      {!floorIndexEligible && (
        <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-100 rounded px-2 py-1.5">
          {gateTip} — 실험 모드로 조회 중입니다.
        </p>
      )}

      {warnings && warnings.length > 0 && (
        <ul className="text-[10px] text-amber-800 bg-amber-50 border border-amber-100 rounded px-2 py-1.5 space-y-0.5 list-disc list-inside">
          {warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className="text-slate-500">기준</span>
        <div className="inline-flex rounded-md border border-slate-200 bg-slate-50 p-0.5">
          {dimensionOptions.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              className={clsx(
                "px-2 py-0.5 rounded text-[11px] font-medium",
                dimension === id ? "bg-white shadow-sm text-slate-800" : "text-slate-500",
              )}
              onClick={() => setDimension(id)}
            >
              {label}
            </button>
          ))}
        </div>
        {isRegression ? (
          <span className="text-slate-500">
            {reference_floor ?? "1층"} = <strong className="text-slate-700">100</strong>
            {r_squared != null && (
              <>
                {" "}
                · R² <strong className="text-slate-700">{fmt(r_squared)}</strong>
              </>
            )}
            {n_regression != null && <> · 회귀 n={n_regression.toLocaleString("ko-KR")}</>}
            {" · "}전체 n={n_total.toLocaleString("ko-KR")}
          </span>
        ) : (
          <span className="text-slate-500">
            기준 {reference_floor ?? "구간"}만 100 · 나머지 지수 없음 · n={n_total.toLocaleString("ko-KR")}
            {baseline_median != null && <> · 중앙값 {fmt(baseline_median)} 만원/㎡</>}
          </span>
        )}
      </div>

      {isRegression && controls && controls.length > 0 && (
        <p className="text-[10px] text-slate-500">
          통제변수: {controls.map((c) => CONTROL_LABELS[c] ?? c).join(", ")}
        </p>
      )}

      <p className="text-[10px] text-slate-500">
        {dimensionHelpText(dim, isRegression, isFactory)} 셀 n&lt;15는 참고용입니다.
      </p>

      <div className="overflow-x-auto rounded-lg border border-slate-100">
        <table className="w-full text-[11px] border-collapse min-w-[480px]">
          <thead>
            <tr className="bg-slate-50 text-slate-600">
              <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">
                {dim === "area" ? (isFactory ? "면적대" : "면적형") : "층 구간"}
              </th>
              <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">건수</th>
              <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">평균(만원/㎡)</th>
              <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-indigo-700">지수</th>
              {isRegression && (
                <>
                  <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">95% CI</th>
                  <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">p</th>
                </>
              )}
            </tr>
          </thead>
          <tbody className="text-slate-800">
            {cells.length === 0 && (
              <tr>
                <td
                  colSpan={isRegression ? 6 : 4}
                  className="border border-slate-200 px-2 py-4 text-center text-slate-400"
                >
                  표시할 데이터가 없습니다.
                </td>
              </tr>
            )}
            {cells.map((c) => (
              <tr key={c.label} className={clsx(!c.is_reliable && "bg-amber-50/40")}>
                <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                  {c.label}
                  {c.is_reference && (
                    <span className="ml-1 text-[9px] text-indigo-600 font-medium">기준</span>
                  )}
                  {!c.is_reliable && <span className="ml-1 text-[9px] text-amber-600">n&lt;15</span>}
                </td>
                <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">{c.count}</td>
                <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">{fmt(c.mean_unit_price)}</td>
                <td className="border border-slate-200 px-2 py-1 text-right tabular-nums font-semibold text-indigo-600">
                  {c.index != null ? `${c.index}%` : "—"}
                </td>
                {isRegression && (
                  <>
                    <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-slate-600">
                      {c.index_lo != null && c.index_hi != null ? `${c.index_lo}–${c.index_hi}%` : "—"}
                    </td>
                    <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-slate-600">
                      {fmtP(c.p_value)}
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
