import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  predictBuildingRegression,
  predictCohortRegression,
  runBuildingRegression,
  runCohortRegression,
} from "../api/client";
import type {
  AssetType,
  CollectivePredictOptions,
  CollectiveRegressionPredictInputs,
  CollectiveRegressionPredictResponse,
  CollectiveRegressionResponse,
  ModelComparison,
  RegressionCoeff,
  RegressionModelType,
} from "../types";
import { buildAnalysisPeriodParams } from "../utils/analysisPeriod";
import { RESIDENTIAL_REGRESSION_HELP } from "../utils/residentialAnalysisHelp";
import AnalysisHelpPanel from "./AnalysisHelpPanel";

export type FloorMode = "linear" | "dummy" | "grouped" | "relative";

function fmt(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function stars(n: number) {
  return "★".repeat(Math.max(0, Math.min(5, n))) + "☆".repeat(Math.max(0, 5 - n));
}

function ModelComparisonCard({
  cmp,
  selected,
}: {
  cmp: ModelComparison;
  selected: RegressionModelType;
}) {
  const rows: { type: RegressionModelType; label: string; m: ModelComparison["log"] }[] = [
    { type: "log", label: "로그회귀", m: cmp.log },
    { type: "linear", label: "선형회귀", m: cmp.linear },
  ];
  const basis = cmp.metric_basis === "cv" ? "교차검증" : "표본내";
  return (
    <div className="rounded-md border border-slate-200 dark:border-slate-600 p-2 space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium text-slate-700 dark:text-slate-200">모델 비교 ({basis})</span>
        <span className="text-[11px] text-amber-600 dark:text-amber-400" title={cmp.confidence_label ?? ""}>
          신뢰 {stars(cmp.confidence_stars)} {cmp.confidence_label ?? ""}
        </span>
      </div>
      <table className="w-full border-collapse text-[11px]">
        <thead>
          <tr className="text-slate-500 dark:text-slate-400">
            <th className="text-left font-normal py-0.5">모델</th>
            <th className="text-right font-normal">조정 R²</th>
            <th className="text-right font-normal">MAPE</th>
            <th className="text-right font-normal">RMSE(만원)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ type, label, m }) => {
            const isRec = cmp.recommended === type;
            const isSel = selected === type;
            return (
              <tr
                key={type}
                className={isSel ? "bg-indigo-50 dark:bg-indigo-950/40 font-medium" : undefined}
              >
                <td className="py-0.5 text-slate-700 dark:text-slate-200">
                  {label}
                  {isRec && <span className="ml-1 text-[10px] text-emerald-600 dark:text-emerald-400">권장</span>}
                </td>
                <td className="text-right tabular-nums">{m?.adj_r_squared?.toFixed(3) ?? "—"}</td>
                <td className="text-right tabular-nums">{m?.mape != null ? `${m.mape}%` : "—"}</td>
                <td className="text-right tabular-nums">
                  {m?.rmse != null ? Math.round(m.rmse).toLocaleString("ko-KR") : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function fmtInt(v: number | null | undefined) {
  if (v == null) return "—";
  return Math.round(v).toLocaleString("ko-KR");
}

function midRange(min?: number | null, max?: number | null): number | undefined {
  if (min == null || max == null) return undefined;
  return Math.round(((min + max) / 2) * 10) / 10;
}

function defaultPredictInputs(
  opts: CollectivePredictOptions | null | undefined,
  vars: {
    exclusive_area: boolean;
    building_age: boolean;
    floor: boolean;
    dong: boolean;
    housing_subtype: boolean;
  },
): CollectiveRegressionPredictInputs {
  if (!opts) return {};
  return {
    exclusive_area: vars.exclusive_area ? midRange(opts.exclusive_area?.min, opts.exclusive_area?.max) : undefined,
    building_age: vars.building_age ? midRange(opts.building_age?.min, opts.building_age?.max) : undefined,
    floor: vars.floor ? midRange(opts.floor?.min, opts.floor?.max) : undefined,
    dong: vars.dong ? opts.dong_reference ?? opts.dongs?.[0] : undefined,
    housing_subtype: vars.housing_subtype
      ? opts.housing_subtype_reference ?? opts.housing_subtypes?.[0]
      : undefined,
    building_key: opts.buildings?.find((b) => b.is_reference)?.building_key ?? opts.buildings?.[0]?.building_key,
  };
}

function RegressionCoeffTable({ coefficients }: { coefficients: RegressionCoeff[] }) {
  const [feOpen, setFeOpen] = useState(false);
  const main = coefficients.filter((c) => c.name !== "const" && !c.name.startsWith("bld_"));
  const fe = coefficients.filter((c) => c.name.startsWith("bld_"));
  const intercept = coefficients.find((c) => c.name === "const");

  const renderRow = (c: RegressionCoeff) => (
    <tr key={c.name}>
      <td className="border border-slate-200 dark:border-slate-600 px-2 py-1">{c.label}</td>
      <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 text-right tabular-nums">
        {c.coef.toFixed(2)}
      </td>
      <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 text-right tabular-nums">
        {c.se?.toFixed(2) ?? "—"}
      </td>
      <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 text-right tabular-nums">
        {c.t?.toFixed(2) ?? "—"}
      </td>
      <td className="border border-slate-200 dark:border-slate-600 px-2 py-1 text-right tabular-nums">
        {c.p?.toFixed(3) ?? "—"}
      </td>
    </tr>
  );

  return (
    <table className="w-full border-collapse text-xs">
      <thead>
        <tr className="bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
          <th className="border border-slate-200 dark:border-slate-600 px-2 py-1 text-left">변수</th>
          <th className="border border-slate-200 dark:border-slate-600 px-2 py-1 text-right">계수</th>
          <th className="border border-slate-200 dark:border-slate-600 px-2 py-1 text-right">SE</th>
          <th className="border border-slate-200 dark:border-slate-600 px-2 py-1 text-right">t</th>
          <th className="border border-slate-200 dark:border-slate-600 px-2 py-1 text-right">p</th>
        </tr>
      </thead>
      <tbody className="text-slate-800 dark:text-slate-200">
        {intercept && renderRow(intercept)}
        {main.map(renderRow)}
        {fe.length > 0 && (
          <>
            <tr className="bg-slate-50/80 dark:bg-slate-800/60">
              <td colSpan={5} className="border border-slate-200 dark:border-slate-600 px-2 py-1">
                <button
                  type="button"
                  className="text-[11px] font-medium text-indigo-700 dark:text-indigo-400"
                  onClick={() => setFeOpen((v) => !v)}
                >
                  단지 고정효과 ({fe.length}개) {feOpen ? "▲" : "▼"}
                </button>
              </td>
            </tr>
            {feOpen && fe.map(renderRow)}
          </>
        )}
      </tbody>
    </table>
  );
}

export function RegressionTable({ data }: { data: CollectiveRegressionResponse }) {
  return (
    <div className="text-xs space-y-2">
      {data.warnings.map((w) => (
        <p key={w} className="text-amber-700 dark:text-amber-300">
          {w}
        </p>
      ))}
      <p className="text-slate-600 dark:text-slate-400">
        {data.model_type === "log" ? "로그회귀" : "선형회귀"} · n={data.n}, R²=
        {data.r_squared?.toFixed(3) ?? "—"}, adj R²={data.adj_r_squared?.toFixed(3) ?? "—"} (적합척도)
      </p>
      <RegressionCoeffTable coefficients={data.coefficients} />
    </div>
  );
}

function PredictPanel({
  opts,
  vars,
  floorMode,
  useCohort,
  inputs,
  setInputs,
  onPredict,
  pending,
  result,
  error,
}: {
  opts: CollectivePredictOptions;
  vars: {
    exclusive_area: boolean;
    building_age: boolean;
    floor: boolean;
    dong: boolean;
    housing_subtype: boolean;
  };
  floorMode: FloorMode;
  useCohort: boolean;
  inputs: CollectiveRegressionPredictInputs;
  setInputs: React.Dispatch<React.SetStateAction<CollectiveRegressionPredictInputs>>;
  onPredict: () => void;
  pending: boolean;
  result?: CollectiveRegressionPredictResponse;
  error?: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-600 bg-slate-50/50 dark:bg-slate-800/40 p-3 space-y-3">
      <p className="text-[11px] font-medium text-slate-700 dark:text-slate-200">예측 (변수값 입력)</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
        {vars.exclusive_area && opts.exclusive_area && (
          <label className="space-y-0.5">
            <span className="text-slate-500 dark:text-slate-400">전용면적(㎡)</span>
            <input
              type="number"
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.exclusive_area ?? ""}
              onChange={(e) =>
                setInputs((p) => ({ ...p, exclusive_area: e.target.value ? Number(e.target.value) : undefined }))
              }
            />
          </label>
        )}
        {vars.building_age && opts.building_age && (
          <label className="space-y-0.5">
            <span className="text-slate-500 dark:text-slate-400">연식(년)</span>
            <input
              type="number"
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.building_age ?? ""}
              onChange={(e) =>
                setInputs((p) => ({ ...p, building_age: e.target.value ? Number(e.target.value) : undefined }))
              }
            />
          </label>
        )}
        {vars.floor && opts.floor && (
          <label className="space-y-0.5">
            <span className="text-slate-500 dark:text-slate-400">
              층{floorMode === "relative" && opts.max_floor != null ? ` (max ${opts.max_floor}층)` : ""}
            </span>
            <input
              type="number"
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.floor ?? ""}
              onChange={(e) =>
                setInputs((p) => ({ ...p, floor: e.target.value ? Number(e.target.value) : undefined }))
              }
            />
          </label>
        )}
        {vars.dong && (opts.dongs?.length ?? 0) > 0 && (
          <label className="space-y-0.5">
            <span className="text-slate-500 dark:text-slate-400">동</span>
            <select
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.dong ?? ""}
              onChange={(e) => setInputs((p) => ({ ...p, dong: e.target.value || undefined }))}
            >
              {opts.dongs!.map((d) => (
                <option key={d} value={d}>
                  {d}
                  {d === opts.dong_reference ? " (기준)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}
        {vars.housing_subtype && (opts.housing_subtypes?.length ?? 0) > 0 && (
          <label className="space-y-0.5">
            <span className="text-slate-500 dark:text-slate-400">권리</span>
            <select
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.housing_subtype ?? ""}
              onChange={(e) => setInputs((p) => ({ ...p, housing_subtype: e.target.value || undefined }))}
            >
              {opts.housing_subtypes!.map((d) => (
                <option key={d} value={d}>
                  {d}
                  {d === opts.housing_subtype_reference ? " (기준)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}
        {useCohort && (opts.buildings?.length ?? 0) > 0 && (
          <label className="space-y-0.5 sm:col-span-2">
            <span className="text-slate-500 dark:text-slate-400">단지 (FE)</span>
            <select
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.building_key ?? ""}
              onChange={(e) => setInputs((p) => ({ ...p, building_key: e.target.value || undefined }))}
            >
              {opts.buildings!.map((b) => (
                <option key={b.building_key} value={b.building_key}>
                  {b.display_name}
                  {b.is_reference ? " (FE 기준)" : b.has_fe ? "" : " (FE 제외)"}
                  {" · n="}
                  {b.count}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      <button type="button" className="btn btn-primary text-xs" disabled={pending} onClick={onPredict}>
        {pending ? "예측 중…" : "예측 실행"}
      </button>

      {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}

      {result && (
        <div className="rounded-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-600 p-3 space-y-2">
          <div>
            <span className="text-slate-500 dark:text-slate-400 text-[10px]">
              예상 거래금액{result.model_type ? ` · ${result.model_type === "log" ? "로그회귀" : "선형회귀"}` : ""}
            </span>
            <div className="text-lg font-bold text-slate-800 dark:text-slate-100">{fmtInt(result.y_hat)}만원</div>
            {result.unit_price_hat != null && (
              <div className="text-[11px] text-slate-500 dark:text-slate-400">
                ㎡당 약 {fmt(result.unit_price_hat)} 만원/㎡
              </div>
            )}
          </div>
          <div className="text-[11px] space-y-1 text-slate-700 dark:text-slate-300">
            <div>
              <span className="font-medium">95% 예측구간 (개별 거래)</span>{" "}
              {fmtInt(result.pi_lower)} ~ {fmtInt(result.pi_upper)}만원
            </div>
            <div className="text-slate-500 dark:text-slate-400">
              95% 평균 신뢰구간 {fmtInt(result.ci_lower)} ~ {fmtInt(result.ci_upper)}만원
            </div>
          </div>
          {result.warnings.map((w) => (
            <p key={w} className="text-[10px] text-amber-700 dark:text-amber-300">
              {w}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

export default function BuildingRegressionPanel({
  buildingKey,
  cohortKeys,
  cohortRunId = 0,
  assetType,
  yearFrom,
  yearTo,
  periodStart,
  periodEnd,
  experiment = false,
  gateTip,
  regressionEligible = true,
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
  gateTip?: string;
  regressionEligible?: boolean;
}) {
  const [excludeOutliers, setExcludeOutliers] = useState(false);
  const [floorMode, setFloorMode] = useState<FloorMode>("relative");
  const [modelType, setModelType] = useState<RegressionModelType>("log");
  const [vars, setVars] = useState({
    exclusive_area: true,
    building_age: assetType !== "presale",
    floor: true,
    dong: assetType === "apartment" || assetType === "rowhouse",
    housing_subtype: assetType === "presale",
  });
  const [predictInputs, setPredictInputs] = useState<CollectiveRegressionPredictInputs>({});

  const useCohort = cohortRunId > 0 && (cohortKeys?.length ?? 0) > 1;
  const keys = useCohort ? cohortKeys! : [buildingKey];

  const periodParams = useMemo(
    () => buildAnalysisPeriodParams(yearFrom, yearTo, periodStart, periodEnd),
    [yearFrom, yearTo, periodStart, periodEnd],
  );

  const regressionBody = useMemo(
    () => ({
      asset_type: assetType,
      ...periodParams,
      exclude_outliers_iqr: excludeOutliers,
      experiment,
      model_type: modelType,
      variables: { ...vars, floor_mode: floorMode },
    }),
    [assetType, periodParams, excludeOutliers, experiment, modelType, vars, floorMode],
  );

  const runRegression = () => {
    return useCohort
      ? runCohortRegression({ building_keys: keys, ...regressionBody })
      : runBuildingRegression(buildingKey, regressionBody);
  };

  const regM = useMutation({ mutationFn: runRegression });

  const predictM = useMutation({
    mutationFn: () => {
      const body = { ...regressionBody, inputs: predictInputs };
      return useCohort
        ? predictCohortRegression({ building_keys: keys, ...body })
        : predictBuildingRegression(buildingKey, body);
    },
  });

  useEffect(() => {
    if (useCohort && cohortRunId > 0) {
      regM.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- cohortRunId triggers cohort run
  }, [cohortRunId, keys.join("|")]);

  useEffect(() => {
    if (regM.data?.predict_options) {
      setPredictInputs(defaultPredictInputs(regM.data.predict_options, vars));
    }
  }, [regM.data, vars]);

  // 회귀 실행 결과의 권장 모델을 기본 선택으로 자동 반영 (사용자는 토글로 변경 가능)
  useEffect(() => {
    const rec = regM.data?.model_comparison?.recommended;
    if (rec && rec !== modelType) {
      setModelType(rec);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 권장 모델은 run 결과에서만 반영
  }, [regM.data]);

  if (useCohort && cohortRunId === 0) {
    return (
      <p className="text-xs text-slate-500 text-center py-6">
        코호트에 아파트를 추가한 뒤 「통합분석」을 누르면 통합 회귀 결과가 표시됩니다.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-medium text-slate-700 dark:text-slate-200">회귀 분석</p>
        <AnalysisHelpPanel explain={regM.data?.explain ?? RESIDENTIAL_REGRESSION_HELP} />
      </div>

      {useCohort && (
        <p className="text-[10px] text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-100 dark:border-indigo-900 rounded px-2 py-1.5">
          {keys.length}개 단지 통합 · 실시간 · 단지 고정효과(거래 최다 단지=기준, n&lt;5 제외)
        </p>
      )}
      {!useCohort && !regressionEligible && (
        <p className="text-[11px] text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 border border-amber-100 dark:border-amber-900 rounded px-2 py-1.5">
          {gateTip ?? "권장 표본 기준 미달"} — 실험 단계에서는 아래 옵션으로 실행할 수 있습니다.
        </p>
      )}

      <p className="text-[10px] text-slate-500 dark:text-slate-400">
        {assetType === "presale"
          ? "금액 ~ 전용면적·층·권리 (OLS). 층 변수 형식은 실험용으로 선택하세요."
          : "금액 ~ 전용면적·연식·층·동 (OLS). 층 변수 형식은 실험용으로 선택하세요."}
      </p>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
        {(
          [
            ["exclusive_area", "전용면적"],
            ...(assetType !== "presale" ? ([["building_age", "연식"]] as const) : []),
            ["floor", "층"],
            ...(assetType === "apartment" || assetType === "rowhouse"
              ? ([["dong", "동"]] as const)
              : []),
            ...(assetType === "presale" ? ([["housing_subtype", "권리"]] as const) : []),
          ] as const
        ).map(([key, label]) => (
          <label key={key} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={vars[key as keyof typeof vars]}
              onChange={(e) => setVars((v) => ({ ...v, [key]: e.target.checked }))}
            />
            {label}
          </label>
        ))}
      </div>

      {vars.floor && (
        <div className="text-xs space-y-1">
          <span className="text-slate-600 dark:text-slate-400 font-medium">층 변수 형식</span>
          <select
            className="border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900 w-full max-w-md"
            value={floorMode}
            onChange={(e) => setFloorMode(e.target.value as FloorMode)}
          >
            <option value="relative">상대 층 (1·최상·저·중·고 / max층)</option>
            <option value="dummy">층별 더미 (개별 층)</option>
            <option value="grouped">절대 구간 (1–5 / 6–15 / 16+)</option>
            <option value="linear">층 선형</option>
          </select>
        </div>
      )}

      <label className="flex items-center gap-2 text-xs">
        <input type="checkbox" checked={excludeOutliers} onChange={(e) => setExcludeOutliers(e.target.checked)} />
        IQR 이상치 제외
      </label>

      <button
        type="button"
        className="btn btn-primary text-xs"
        disabled={regM.isPending}
        onClick={() => regM.mutate()}
      >
        {regM.isPending ? "실행 중…" : useCohort ? "통합 회귀 다시 실행" : "회귀 실행"}
      </button>

      {regM.isError && (
        <p className="text-xs text-red-600 dark:text-red-400">
          {(regM.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "회귀 실패"}
        </p>
      )}
      {regM.data && <RegressionTable data={regM.data} />}

      {regM.data?.model_comparison && (
        <div className="space-y-2">
          <ModelComparisonCard cmp={regM.data.model_comparison} selected={modelType} />
          <div className="flex flex-wrap items-center gap-3 text-[11px]">
            <span className="text-slate-500 dark:text-slate-400">회귀방식</span>
            {(["log", "linear"] as RegressionModelType[]).map((mt) => {
              const isRec = regM.data!.model_comparison!.recommended === mt;
              return (
                <label key={mt} className="flex items-center gap-1 cursor-pointer">
                  <input
                    type="radio"
                    name="model-type"
                    checked={modelType === mt}
                    onChange={() => setModelType(mt)}
                  />
                  {mt === "log" ? "로그회귀" : "선형회귀"}
                  {isRec && <span className="text-[10px] text-emerald-600 dark:text-emerald-400">(권장)</span>}
                </label>
              );
            })}
            <span className="text-[10px] text-slate-400">
              변경 후 「예측 실행」을 누르면 선택한 모델로 예측합니다.
            </span>
          </div>
        </div>
      )}

      {regM.data?.predict_options && (
        <PredictPanel
          opts={regM.data.predict_options}
          vars={vars}
          floorMode={floorMode}
          useCohort={useCohort}
          inputs={predictInputs}
          setInputs={setPredictInputs}
          onPredict={() => predictM.mutate()}
          pending={predictM.isPending}
          result={predictM.data}
          error={
            predictM.isError
              ? String(
                  (predictM.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
                    "예측 실패",
                )
              : undefined
          }
        />
      )}
    </div>
  );
}
