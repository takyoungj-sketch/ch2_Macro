import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { fetchCommercialFloorIndex, runCommercialCohortFloorIndex } from "../api/commercialClient";
import type { CommercialCohortFloorIndexResponse, CommercialFloorIndexResponse } from "../types";
import { buildAnalysisPeriodParams } from "../utils/analysisPeriod";
import { COMMERCIAL_FLOOR_INDEX_HELP } from "../utils/commercialAnalysisHelp";
import type { CommercialModalScope } from "./CommercialClusterDetailModal";
import AnalysisHelpPanel from "./AnalysisHelpPanel";

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
  building_age: "연식",
  building_use: "건축물용도",
  contract_period: "거래시점(반기)",
  relative_floor: "층 구간(1층 기준)",
  cluster_fixed_effects: "도로(cluster) 고정효과",
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

function dimensionColumnLabel(dim: string, isFactory: boolean) {
  if (dim === "area") return isFactory ? "면적대" : "면적형";
  return "층 구간";
}

function dimensionHelpText(dim: string, isRegression: boolean, isFactory: boolean) {
  const base = isRegression
    ? "회귀(반로그)로 연면적·연식·거래시점 등을 통제한 뒤, 기준 구간=100% 상대 지수(%)를 표시합니다."
    : "";
  if (dim === "area") {
    if (isRegression) {
      return `${base} 면적형은 ${isFactory ? "100/300/1000㎡ 구간" : "연면적 30㎡ 구간(주거와 동일)"}입니다.`;
    }
    if (isFactory) {
      return "연면적을 100/300/1000㎡ 구간으로 묶어, cluster 중앙값 대비 지수(%)를 표시합니다.";
    }
    return "연면적을 30㎡ 구간으로 묶어, 도로(cluster) 중앙값 대비 지수(%)를 표시합니다.";
  }
  if (isRegression) {
    return `${base} 1층=100% 기준, ln(연면적)·연식·건축물용도·거래시점을 통제한 층 구간 지수입니다.`;
  }
  if (isFactory) {
    return "층별 평균 ㎡당가를 cluster 중앙값 대비 지수(%)로 표시합니다. 층 정보 sparse — 참고용, 면적형 탭을 우선하세요.";
  }
  return "층별 평균 ㎡당가를 도로(cluster) 중앙값 대비 지수(%)로 표시합니다.";
}

export default function CommercialFloorIndexPanel({
  clusterKey,
  cohortKeys,
  cohortRunId = 0,
  scope,
  periodStart,
  periodEnd,
  count,
  isFactory = false,
}: {
  clusterKey: string;
  cohortKeys?: string[];
  cohortRunId?: number;
  scope: CommercialModalScope;
  periodStart?: string | null;
  periodEnd?: string | null;
  count: number;
  isFactory?: boolean;
}) {
  const [dimension, setDimension] = useState<Dimension>(isFactory ? "area" : "floor");
  const useCohort = cohortRunId > 0 && (cohortKeys?.length ?? 0) > 1;
  const keys = useCohort ? cohortKeys! : [clusterKey];
  const floorIndexEligible = count >= 50;
  const experiment = !floorIndexEligible;
  const gateTip = `${isFactory ? "면적형·층" : "층·면적"} 효용지수: 선택 구간 거래 ${count}건 (최소 50건 권장)`;

  const dimensionOptions: { id: Dimension; label: string }[] = isFactory
    ? [
        { id: "area", label: "면적형별" },
        { id: "floor", label: "층별(참고)" },
      ]
    : [
        { id: "floor", label: "층별" },
        { id: "area", label: "면적형별" },
      ];

  const periodParams = buildAnalysisPeriodParams(
    scope.yearFrom === "" ? undefined : scope.yearFrom,
    scope.yearTo === "" ? undefined : scope.yearTo,
    periodStart,
    periodEnd,
  );

  const q = useQuery<CommercialFloorIndexResponse | CommercialCohortFloorIndexResponse>({
    queryKey: [
      useCohort ? "comm-cohort-floor-index" : "comm-floor-index",
      keys.join("|"),
      scope,
      periodParams,
      dimension,
      experiment,
      isFactory,
      cohortRunId,
    ],
    queryFn: () =>
      useCohort
        ? runCommercialCohortFloorIndex({
            cluster_keys: keys,
            asset_type: scope.assetType === "all" ? undefined : scope.assetType,
            dimension,
            experiment,
            ...periodParams,
          })
        : fetchCommercialFloorIndex(clusterKey, {
            ...regionParams(scope),
            ...periodParams,
            dimension,
            experiment,
          }),
    enabled: !useCohort || cohortRunId > 0,
  });

  if (useCohort && cohortRunId === 0) {
    return (
      <p className="text-xs text-slate-500 text-center py-6">
        코호트에 도로를 추가한 뒤 「통합분석」을 누르면 통합 효용지수가 표시됩니다.
      </p>
    );
  }

  if (q.isLoading) {
    return (
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-2">
          <p className="text-[11px] font-medium text-slate-700 dark:text-slate-200">
            {isFactory ? "면적형·층 효용지수" : "층·면적 효용지수"}
          </p>
          <AnalysisHelpPanel explain={COMMERCIAL_FLOOR_INDEX_HELP} />
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
          <p className="text-[11px] font-medium text-slate-700 dark:text-slate-200">
            {isFactory ? "면적형·층 효용지수" : "층·면적 효용지수"}
          </p>
          <AnalysisHelpPanel explain={COMMERCIAL_FLOOR_INDEX_HELP} />
        </div>
        <p className="text-xs text-amber-700 dark:text-amber-300 text-center py-4">{String(msg)}</p>
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
    diagnostics,
  } = q.data;

  const isRegression = method === "regression_semilog";

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-medium text-slate-700 dark:text-slate-200">
          {isFactory ? "면적형·층 효용지수" : "층·면적 효용지수"}
        </p>
        <AnalysisHelpPanel explain={explain ?? COMMERCIAL_FLOOR_INDEX_HELP} />
      </div>

      {useCohort && (
        <p className="text-[10px] text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-100 dark:border-indigo-900 rounded px-2 py-1.5">
          {keys.length}개 도로 cluster 통합 · 실시간 · n={n_total.toLocaleString("ko-KR")}
        </p>
      )}

      {!useCohort && !floorIndexEligible && (
        <p className="text-[11px] text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 border border-amber-100 dark:border-amber-900 rounded px-2 py-1.5">
          {gateTip} — 실험 모드로 조회 중입니다.
        </p>
      )}

      {warnings && warnings.length > 0 && (
        <ul className="text-[10px] text-amber-800 dark:text-amber-200 bg-amber-50 dark:bg-amber-950/40 border border-amber-100 dark:border-amber-900 rounded px-2 py-1.5 space-y-0.5 list-disc list-inside">
          {warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className="text-slate-500 dark:text-slate-400">기준</span>
        <div className="inline-flex rounded-md border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-800 p-0.5">
          {dimensionOptions.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              className={clsx(
                "px-2 py-0.5 rounded text-[11px] font-medium",
                dimension === id
                  ? "bg-white dark:bg-slate-700 shadow-sm text-slate-800 dark:text-slate-100"
                  : "text-slate-500 dark:text-slate-400",
              )}
              onClick={() => setDimension(id)}
            >
              {label}
            </button>
          ))}
        </div>
        {isRegression ? (
          <span className="text-slate-500 dark:text-slate-400">
            {reference_floor ?? "기준"} = <strong className="text-slate-700 dark:text-slate-200">100</strong>
            {r_squared != null && (
              <>
                {" "}
                · R² <strong className="text-slate-700 dark:text-slate-200">{fmt(r_squared)}</strong>
              </>
            )}
            {n_regression != null && <> · 회귀 n={n_regression.toLocaleString("ko-KR")}</>}
            {" · "}전체 n={n_total.toLocaleString("ko-KR")}
            {baseline_median != null && (
              <>
                {" "}
                · 중앙값 {fmt(baseline_median)} 만원/㎡
              </>
            )}
          </span>
        ) : (
          <span className="text-slate-500 dark:text-slate-400">
            도로 중앙값 <strong className="text-slate-700 dark:text-slate-200">{fmt(baseline_median)}</strong> 만원/㎡
            = 100 · n={n_total.toLocaleString("ko-KR")}
          </span>
        )}
      </div>

      {dim === "floor" && isRegression && (
        <p className="text-[10px] text-slate-500 dark:text-slate-400">
          회귀 분석 탭과 동일한 상가형 층 구간 더미입니다. 화면 100%는 1층(표본이 없으면 —) 기준입니다.
        </p>
      )}

      {isRegression && controls && controls.length > 0 && (
        <p className="text-[10px] text-slate-500 dark:text-slate-400">
          통제변수: {controls.map((c) => CONTROL_LABELS[c] ?? c).join(", ")}
        </p>
      )}

      {isRegression && diagnostics && diagnostics.max_vif != null && (
        <p className="text-[10px] text-slate-500 dark:text-slate-400">
          공선성 진단: 최대 VIF{" "}
          <strong
            className={clsx(
              diagnostics.max_vif >= 10
                ? "text-rose-600 dark:text-rose-400"
                : diagnostics.max_vif >= 5
                  ? "text-amber-600 dark:text-amber-400"
                  : "text-slate-700 dark:text-slate-200",
            )}
          >
            {fmt(diagnostics.max_vif)}
          </strong>
          {diagnostics.max_vif_term && (
            <> ({CONTROL_LABELS[diagnostics.max_vif_term] ?? diagnostics.max_vif_term})</>
          )}
          {diagnostics.condition_number != null && <> · 조건수 {fmt(diagnostics.condition_number)}</>}
          {diagnostics.max_vif < 5 && <> · 양호</>}
        </p>
      )}

      <p className="text-[10px] text-slate-500 dark:text-slate-400">
        {dimensionHelpText(dim, isRegression, isFactory)} 셀 n&lt;15는 참고용입니다.
      </p>

      <div className="overflow-x-auto rounded-lg border border-slate-100 dark:border-slate-700">
        <table className="w-full text-[11px] border-collapse min-w-[480px]">
          <thead>
            <tr className="bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
              <th className="border border-slate-200 dark:border-slate-600 px-2 py-1.5 text-left font-medium">
                {dimensionColumnLabel(dim, isFactory)}
              </th>
              <th className="border border-slate-200 dark:border-slate-600 px-2 py-1.5 text-right font-medium">
                건수
              </th>
              <th className="border border-slate-200 dark:border-slate-600 px-2 py-1.5 text-right font-medium">
                평균(만원/㎡)
              </th>
              <th className="border border-slate-200 dark:border-slate-600 px-2 py-1.5 text-right font-bold text-indigo-700 dark:text-indigo-400">
                지수
              </th>
              {isRegression && (
                <>
                  <th className="border border-slate-200 dark:border-slate-600 px-2 py-1.5 text-right font-medium">
                    95% CI
                  </th>
                  <th className="border border-slate-200 dark:border-slate-600 px-2 py-1.5 text-right font-medium">
                    p
                  </th>
                </>
              )}
            </tr>
          </thead>
          <tbody className="text-slate-800 dark:text-slate-200">
            {cells.length === 0 && (
              <tr>
                <td
                  colSpan={isRegression ? 6 : 4}
                  className="border border-slate-200 dark:border-slate-600 px-2 py-4 text-center text-slate-400"
                >
                  표시할 데이터가 없습니다.
                </td>
              </tr>
            )}
            {cells.map((c) => (
              <tr key={c.label} className={clsx(!c.is_reliable && "bg-amber-50/40 dark:bg-amber-950/20")}>
                <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 whitespace-nowrap">
                  {c.label}
                  {c.is_reference && (
                    <span className="ml-1 text-[9px] text-indigo-600 dark:text-indigo-400 font-medium">기준</span>
                  )}
                  {!c.is_reliable && (
                    <span className="ml-1 text-[9px] text-amber-600 dark:text-amber-400">n&lt;15</span>
                  )}
                </td>
                <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 text-right tabular-nums">
                  {c.count}
                </td>
                <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 text-right tabular-nums">
                  {fmt(c.mean_unit_price)}
                </td>
                <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 text-right tabular-nums font-semibold text-indigo-600 dark:text-indigo-400">
                  {c.index != null ? `${c.index}%` : "—"}
                </td>
                {isRegression && (
                  <>
                    <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 text-right tabular-nums text-slate-600 dark:text-slate-400">
                      {c.index_lo != null && c.index_hi != null ? `${c.index_lo}–${c.index_hi}%` : "—"}
                    </td>
                    <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 text-right tabular-nums text-slate-600 dark:text-slate-400">
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
