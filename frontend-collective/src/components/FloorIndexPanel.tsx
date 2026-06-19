import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { fetchBuildingFloorIndex, runCohortFloorIndex } from "../api/client";
import type { AssetType } from "../types";
import { buildAnalysisPeriodParams } from "../utils/analysisPeriod";
import { RESIDENTIAL_FLOOR_INDEX_HELP } from "../utils/residentialAnalysisHelp";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import { type FloorMode } from "./BuildingRegressionPanel";

const FLOOR_MODE_OPTIONS: { value: FloorMode; label: string }[] = [
  { value: "relative", label: "상대 층 (1·저·중·고·최상)" },
  { value: "dummy", label: "개별 층 더미" },
  { value: "grouped", label: "절대 구간 (1–5 / 6–15 / 16+)" },
];

function fmt(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function fmtP(v: number | null | undefined) {
  if (v == null) return "—";
  if (v < 0.001) return "<0.001";
  return v.toLocaleString(undefined, { maximumFractionDigits: 3 });
}

type Dimension = "floor" | "dong" | "area" | "rights";

const DIMENSION_OPTIONS: { id: Dimension; label: string; show?: (assetType: AssetType) => boolean }[] = [
  { id: "floor", label: "층별" },
  { id: "dong", label: "동별", show: (t) => t === "apartment" || t === "rowhouse" },
  { id: "rights", label: "권리별", show: (t) => t === "presale" },
  { id: "area", label: "면적형별" },
];

const CONTROL_LABELS: Record<string, string> = {
  ln_exclusive_area: "ln(전용면적)",
  ln_gross_area: "ln(연면적)",
  building_age: "연식",
  relative_floor: "상대 층구간",
  contract_period: "거래시점(반기)",
  building_fixed_effects: "단지 고정효과",
};

function dimensionColumnLabel(dim: string) {
  if (dim === "dong") return "동";
  if (dim === "rights") return "권리";
  if (dim === "area") return "면적형";
  return "층";
}

function dimensionHelpText(dim: string, isRegression: boolean, floorMode?: FloorMode) {
  const base = isRegression
    ? "회귀(반로그)로 전용면적·연식 등을 통제한 뒤, 기준 구간=100% 상대 지수(%)를 표시합니다."
    : "";
  if (dim === "dong") {
    return `${base} 동별 상대 ㎡당가 지수입니다.`;
  }
  if (dim === "rights") {
    return `${base} 분양권·입주권 등 권리별 상대 ㎡당가 지수입니다.`;
  }
  if (dim === "area") {
    return `${base} 면적형은 전용면적 30㎡ 구간입니다.`;
  }
  const modeHint =
    floorMode === "dummy"
      ? "개별 층 더미로 산출합니다."
      : floorMode === "grouped"
        ? "절대 층 구간(1–5 / 6–15 / 16+)으로 산출합니다."
        : "단지 max층 대비 상대 구간(1층·저·중·고·최상층)입니다.";
  return `${base} ${modeHint}`;
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
  const [floorMode, setFloorMode] = useState<FloorMode>("relative");
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

  if (!useCohort && !floorIndexEligible && !experiment) {
    return (
      <p className="text-xs text-amber-700 text-center py-6">{gateTip ?? "효용지수 분석 최소 표본 미달"}</p>
    );
  }

  if (useCohort && cohortRunId === 0) {
    return (
      <p className="text-xs text-slate-500 text-center py-6">
        코호트에 아파트를 추가한 뒤 「통합분석」을 누르면 통합 효용지수가 표시됩니다.
      </p>
    );
  }

  if (q.isLoading) {
    return (
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-2">
          <p className="text-[11px] font-medium text-slate-700 dark:text-slate-200">층·동·면적 효용지수</p>
          <AnalysisHelpPanel explain={RESIDENTIAL_FLOOR_INDEX_HELP} />
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
          <p className="text-[11px] font-medium text-slate-700 dark:text-slate-200">층·동·면적 효용지수</p>
          <AnalysisHelpPanel explain={RESIDENTIAL_FLOOR_INDEX_HELP} />
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
    dimension: dim,
    method,
    reference_floor,
    controls,
    n_regression,
    r_squared,
    warnings,
    explain,
    diagnostics,
  } = q.data;

  const isRegression = method === "regression_semilog";

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-medium text-slate-700 dark:text-slate-200">층·동·면적 효용지수</p>
        <AnalysisHelpPanel explain={explain ?? RESIDENTIAL_FLOOR_INDEX_HELP} />
      </div>

      {useCohort && (
        <p className="text-[10px] text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-100 dark:border-indigo-900 rounded px-2 py-1.5">
          {keys.length}개 단지 통합 · 실시간 · n={n_total.toLocaleString("ko-KR")}
        </p>
      )}
      {!useCohort && !floorIndexEligible && (
        <p className="text-[11px] text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 border border-amber-100 dark:border-amber-900 rounded px-2 py-1.5">
          {gateTip ?? "권장 표본 기준 미달"} — 실험 모드로 조회 중입니다.
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
          {toggles.map(({ id, label }) => (
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
            단지 중앙값 <strong className="text-slate-700 dark:text-slate-200">{fmt(baseline_median)}</strong> 만원/㎡
            = 100 · n={n_total.toLocaleString("ko-KR")}
          </span>
        )}
      </div>

      {dimension === "floor" && (
        <div className="text-[11px] space-y-1">
          <span className="text-slate-500 dark:text-slate-400 font-medium">층 변수 형식</span>
          <select
            className="border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900 w-full max-w-md text-[11px]"
            value={floorMode}
            onChange={(e) => setFloorMode(e.target.value as FloorMode)}
          >
            {FLOOR_MODE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <p className="text-[10px] text-slate-500 dark:text-slate-400">
            회귀 분석 탭과 동일한 층 더미 방식입니다. 회귀 기준은 거래 최다 구간, 화면 100%는 표본이 있는
            {floorMode === "grouped" ? " 1–5층" : " 1층"}(또는 회귀 기준)입니다.
          </p>
        </div>
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
        {dimensionHelpText(dim, isRegression, dimension === "floor" ? floorMode : undefined)} 셀 n&lt;15는 참고용입니다.
      </p>

      <div className="overflow-x-auto rounded-lg border border-slate-100 dark:border-slate-700">
        <table className="w-full text-[11px] border-collapse min-w-[480px]">
          <thead>
            <tr className="bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
              <th className="border border-slate-200 dark:border-slate-600 px-2 py-1.5 text-left font-medium">
                {dimensionColumnLabel(dim)}
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
                  {!c.is_reliable && <span className="ml-1 text-[9px] text-amber-600 dark:text-amber-400">n&lt;15</span>}
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
