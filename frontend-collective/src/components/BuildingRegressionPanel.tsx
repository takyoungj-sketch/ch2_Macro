import { useEffect, useMemo, useState } from "react";
import { contentSignature } from "../../../shared/regression-ui/signature";
import { reconcileListedInputs } from "../../../shared/regression-ui/inputs";
import type { RegressionSampleGroup } from "../../../shared/regression-ui/types";
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
  RegressionModelType,
} from "../types";
import { ASSET_LABELS } from "../types";
import { buildAnalysisPeriodParams } from "../utils/analysisPeriod";
import {
  canRunRegression,
  isRegressionRecommended,
  regressionRunLabel,
} from "../utils/analysisGates";
import { RESIDENTIAL_REGRESSION_HELP } from "../utils/residentialAnalysisHelp";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import RegressionSampleHint from "./RegressionSampleHint";
import {
  ESTIMATE_COPY,
  StatisticalEstimateCaption,
  StatisticalEstimateDisclaimer,
  StatisticalEstimateRangeRow,
  StatsGlossaryHelp,
} from "@ch2/stats-glossary";
import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { recordAnalysisHistory } from "@ch2/ai-assistant/aiClient";
import {
  CH2_AI_ACTION_EVENT,
  notifyAiEngineReady,
  type AiScreenAction,
} from "@ch2/ai-assistant/aiActions";
import { buildCollectiveRegressionContext } from "../api/aiContext";
import { CollectiveRegressionResults } from "./CollectiveRegressionResults";
import CollectiveModelRecommend from "./CollectiveModelRecommend";
import type { FloorMode } from "../utils/collectiveRegressionTypes";

export type { FloorMode };
function fmt(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function fmtInt(v: number | null | undefined) {
  if (v == null) return "—";
  return Math.round(v).toLocaleString("ko-KR");
}

type RegressionVars = {
  exclusive_area: boolean;
  building_age: boolean;
  floor: boolean;
  dong: boolean;
  housing_subtype: boolean;
  households: boolean;
  parking: boolean;
  assessed_land_price: boolean;
  structure: boolean;
  asset_type_dummy: boolean;
  contract_period: boolean;
};

function defaultPredictInputs(
  opts: CollectivePredictOptions | null | undefined,
  vars: RegressionVars,
): CollectiveRegressionPredictInputs {
  if (!opts) return {};
  const buildingKey =
    opts.buildings?.find((b) => b.is_reference)?.building_key ?? opts.buildings?.[0]?.building_key;
  let dong: string | undefined;
  if (vars.dong) {
    if (opts.dong_options?.length) {
      const scoped = opts.dong_options.filter((o) => !o.building_key || o.building_key === buildingKey);
      dong = scoped.find((o) => o.is_reference)?.dong ?? scoped[0]?.dong;
    } else {
      dong = opts.dong_reference ?? opts.dongs?.[0];
    }
  }
  return {
    dong,
    housing_subtype: vars.housing_subtype
      ? opts.housing_subtype_reference ?? opts.housing_subtypes?.[0]
      : undefined,
    building_key: buildingKey,
    contract_period: opts.contract_period_reference ?? undefined,
    households: undefined,
    parking_per_household: undefined,
    assessed_land_price: undefined,
    structure_group: vars.structure
      ? opts.structure_reference ?? opts.structure_groups?.[0]
      : undefined,
    asset_type: vars.asset_type_dummy
      ? opts.asset_type_reference ?? opts.asset_types?.[0]
      : undefined,
  };
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
  disabled,
  result,
  error,
  groups = [],
}: {
  opts: CollectivePredictOptions;
  vars: RegressionVars;
  floorMode: FloorMode;
  useCohort: boolean;
  inputs: CollectiveRegressionPredictInputs;
  setInputs: React.Dispatch<React.SetStateAction<CollectiveRegressionPredictInputs>>;
  onPredict: () => void;
  pending: boolean;
  disabled: boolean;
  result?: CollectiveRegressionPredictResponse;
  error?: string;
  groups?: RegressionSampleGroup[];
}) {
  const selectedGroup = groups.find(group => group.key === inputs.building_key) ?? (groups.length === 1 ? groups[0] : undefined);
  const confirmed = selectedGroup?.confirmed_attributes ?? {};
  const loadable = Object.fromEntries(["households", "parking_per_household", "assessed_land_price"]
    .filter(key => opts[key as keyof CollectivePredictOptions] && Number.isFinite(confirmed[key]))
    .map(key => [key, key === "parking_per_household" ? Number(confirmed[key].toPrecision(8)) : confirmed[key]]));
  const dongChoices =
    opts.dong_options?.length
      ? opts.dong_options.filter(
          (o) => !o.building_key || o.building_key === inputs.building_key,
        )
      : (opts.dongs ?? []).map((d) => ({
          dong: d,
          label: d,
          building_key: null as string | null,
          is_reference: d === opts.dong_reference,
        }));
  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-600 bg-slate-50/50 dark:bg-slate-800/40 p-3 space-y-3">
      <p className="text-[11px] font-medium text-slate-700 dark:text-slate-200">조건별 추정 · 거래금액</p>
      <p className="text-[10px] text-slate-500 dark:text-slate-400">
        입력한 조건에서 모형이 추정한 금액입니다. 개별 물건의 적정가격을 뜻하지는 않습니다.
      </p>
      {groups.some(group => Object.keys(group.confirmed_attributes ?? {}).length > 0) && <div className="space-y-1 text-xs">
        <button type="button" className="border rounded px-2 py-1 border-slate-300 dark:border-slate-500"
          disabled={disabled || pending || Object.keys(loadable).length === 0}
          onClick={() => setInputs(current => ({ ...current, ...loadable }))}>선택 단지의 확인된 특성 불러오기</button>
        <p className="text-slate-600 dark:text-slate-300">현재 적합 거래에서 값이 모두 같고 결측이 없는 특성만 입력합니다. 연도별로 다르거나 미확보인 값은 채우지 않습니다. 면적·층·연식은 직접 입력하세요.</p>
      </div>}
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
        {useCohort && (opts.buildings?.length ?? 0) > 0 && (
          <label className="space-y-0.5 sm:col-span-2">
            <span className="text-slate-500 dark:text-slate-400">
              {opts.buildings!.some((b) => b.has_fe) ? "단지 (FE)" : "단지"}
            </span>
            <select
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.building_key ?? ""}
              onChange={(e) => {
                const buildingKey = e.target.value || undefined;
                const scoped = (opts.dong_options ?? []).filter(
                  (o) => !o.building_key || o.building_key === buildingKey,
                );
                const dong = scoped.find((o) => o.is_reference)?.dong ?? scoped[0]?.dong;
                setInputs((p) => ({ ...p, building_key: buildingKey, dong }));
              }}
            >
              {opts.buildings!.map((b) => (
                <option key={b.building_key} value={b.building_key}
                  disabled={opts.buildings!.some(x => x.has_fe) && !b.is_reference && !b.has_fe}>
                  {b.display_name}
                  {b.is_reference && b.has_fe
                    ? " (FE 기준)"
                    : b.has_fe
                      ? ""
                      : opts.buildings!.some((x) => x.has_fe)
                        ? " (FE 제외)"
                        : ""}
                  {" · n="}
                  {b.count}
                </option>
              ))}
            </select>
          </label>
        )}
        {vars.dong && dongChoices.length > 0 && (
          <label className="space-y-0.5">
            <span className="text-slate-500 dark:text-slate-400">동</span>
            <select
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.dong ?? ""}
              onChange={(e) => setInputs((p) => ({ ...p, dong: e.target.value || undefined }))}
            >
              {dongChoices.map((o) => (
                <option key={`${o.building_key ?? ""}|${o.dong}`} value={o.dong}>
                  {o.label}
                  {o.is_reference ? " (기준)" : ""}
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
        {vars.households && opts.households && (
          <label className="space-y-0.5">
            <span className="text-slate-500 dark:text-slate-400">총 세대수</span>
            <input
              type="number"
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.households ?? ""}
              onChange={(e) =>
                setInputs((p) => ({ ...p, households: e.target.value ? Number(e.target.value) : undefined }))
              }
            />
          </label>
        )}
        {vars.parking && opts.parking_per_household && (
          <label className="space-y-0.5">
            <span className="text-slate-500 dark:text-slate-400">세대당 주차</span>
            <input
              type="number"
              step="0.01"
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.parking_per_household ?? ""}
              onChange={(e) =>
                setInputs((p) => ({
                  ...p,
                  parking_per_household: e.target.value ? Number(e.target.value) : undefined,
                }))
              }
            />
          </label>
        )}
        {vars.assessed_land_price && opts.assessed_land_price && (
          <label className="space-y-0.5">
            <span className="text-slate-500 dark:text-slate-400">개별공시지가 (원/㎡)</span>
            <input
              type="number"
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.assessed_land_price ?? ""}
              onChange={(e) =>
                setInputs((p) => ({
                  ...p,
                  assessed_land_price: e.target.value ? Number(e.target.value) : undefined,
                }))
              }
            />
          </label>
        )}
        {vars.structure && (opts.structure_groups?.length ?? 0) > 0 && (
          <label className="space-y-0.5">
            <span className="text-slate-500 dark:text-slate-400">구조</span>
            <select
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.structure_group ?? ""}
              onChange={(e) => setInputs((p) => ({ ...p, structure_group: e.target.value || undefined }))}
            >
              {opts.structure_groups!.map((d) => (
                <option key={d} value={d}>
                  {d}
                  {d === opts.structure_reference ? " (기준)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}
        {vars.asset_type_dummy && (opts.asset_types?.length ?? 0) > 0 && (
          <label className="space-y-0.5">
            <span className="text-slate-500 dark:text-slate-400">유형</span>
            <select
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.asset_type ?? ""}
              onChange={(e) => setInputs((p) => ({ ...p, asset_type: e.target.value || undefined }))}
            >
              {opts.asset_types!.map((d) => (
                <option key={d} value={d}>
                  {ASSET_LABELS[d as AssetType] ?? d}
                  {d === opts.asset_type_reference ? " (기준)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {(opts.contract_periods?.length ?? 0) > 0 && <label className="block space-y-1 text-xs">
        <span className="text-slate-500 dark:text-slate-400">거래시점 (반기)</span>
        <select className="input" value={inputs.contract_period ?? opts.contract_period_reference ?? ""}
          onChange={(e) => setInputs(p => ({ ...p, contract_period: e.target.value }))}>
          {opts.contract_periods?.map(period => <option key={period} value={period}>
            {period}{period === opts.contract_period_reference ? " (기준)" : ""}
          </option>)}
        </select>
      </label>}
      <button type="button" className="btn btn-primary text-xs" disabled={pending || disabled} onClick={onPredict}>
        {pending ? "계산 중…" : "추정값 계산"}
      </button>

      {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}

      {result && (
        <div className="rounded-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-600 p-3 space-y-2">
          <div>
            <span className="text-slate-500 dark:text-slate-400 text-[10px]">
              {ESTIMATE_COPY.valueLabel}
              {result.model_type ? ` · ${result.model_type === "log" ? "로그" : "선형"}` : ""}
            </span>
            <div className="text-lg font-bold text-slate-800 dark:text-slate-100">{fmtInt(result.y_hat)}만원</div>
            <StatisticalEstimateCaption compact />
            {result.applied_contract_period && <p className="text-[11px] text-slate-500 dark:text-slate-400">적용 거래시점: {result.applied_contract_period}</p>}
            {result.unit_price_hat != null && (
              <div className="text-[11px] text-slate-500 dark:text-slate-400">
                ㎡당 약 {fmt(result.unit_price_hat)} 만원/㎡
              </div>
            )}
          </div>
          <div className="text-[11px] space-y-1.5 text-slate-700 dark:text-slate-300">
            <StatisticalEstimateRangeRow kind="mean" compact>
              {fmtInt(result.ci_lower)} ~ {fmtInt(result.ci_upper)}만원
            </StatisticalEstimateRangeRow>
            <StatisticalEstimateRangeRow kind="individual" compact>
              {fmtInt(result.pi_lower)} ~ {fmtInt(result.pi_upper)}만원
            </StatisticalEstimateRangeRow>
          </div>
          {result.warnings.map((w) => (
            <p key={w} className="text-[10px] text-amber-700 dark:text-amber-300">
              {w}
            </p>
          ))}
          <StatisticalEstimateDisclaimer compact />
        </div>
      )}
    </div>
  );
}

export default function BuildingRegressionPanel({
  buildingKey,
  cohortKeys,
  assetType,
  yearFrom,
  yearTo,
  periodStart,
  periodEnd,
  experiment = false,
  countTotal,
  countRecent,
  gateMessages,
}: {
  buildingKey: string;
  cohortKeys?: string[];
  assetType: AssetType;
  yearFrom?: number;
  yearTo?: number;
  periodStart?: string | null;
  periodEnd?: string | null;
  experiment?: boolean;
  countTotal?: number | null;
  countRecent?: number | null;
  gateMessages?: string[];
}) {
  const [excludeOutliers, setExcludeOutliers] = useState(false);
  const [floorAdvanced, setFloorAdvanced] = useState(false);
  const [modelType, setModelType] = useState<RegressionModelType>("linear");
  const [categoricalMissing, setCategoricalMissing] = useState<"keep_unknown" | "drop">("keep_unknown");
  const [vars, setVars] = useState<RegressionVars>({
    exclusive_area: true,
    building_age: assetType !== "presale",
    floor: true,
    dong: assetType === "apartment" || assetType === "rowhouse",
    housing_subtype: assetType === "presale",
    households: false,
    parking: false,
    assessed_land_price: false,
    structure: false,
    asset_type_dummy: false,
    contract_period: true,
  });
  const [floorMode, setFloorMode] = useState<FloorMode>(assetType === "rowhouse" ? "rowhouse" : "relative");
  const [predictInputs, setPredictInputs] = useState<CollectiveRegressionPredictInputs>({});

  const useCohort = (cohortKeys?.length ?? 0) > 1;
  const keys = useCohort ? cohortKeys! : [buildingKey];
  const canRun = useCohort || canRunRegression(countTotal);
  const recommended = useCohort || isRegressionRecommended(countTotal);
  const selectedBlocks = useMemo(
    () => (Object.keys(vars) as (keyof RegressionVars)[]).filter((key) => Boolean(vars[key])),
    [vars],
  );
  const attrOn =
    vars.households ||
    vars.parking ||
    vars.assessed_land_price ||
    vars.structure ||
    vars.asset_type_dummy;

  const periodParams = useMemo(
    () => buildAnalysisPeriodParams(yearFrom, yearTo, periodStart, periodEnd),
    [yearFrom, yearTo, periodStart, periodEnd],
  );

  const regressionBody = useMemo(
    () => ({
      asset_type: assetType,
      ...periodParams,
      exclude_outliers_iqr: excludeOutliers,
      categorical_missing: categoricalMissing,
      experiment,
      model_type: modelType,
      variables: { ...vars, floor_mode: floorMode },
    }),
    [assetType, periodParams, excludeOutliers, categoricalMissing, experiment, modelType, vars, floorMode],
  );

  const requestSignature = contentSignature({ body: regressionBody, keys });
  const runRegression = async () => {
    const signature = requestSignature;
    const data = await (useCohort
      ? runCohortRegression({ building_keys: keys, ...regressionBody })
      : runBuildingRegression(buildingKey, regressionBody));
    return { ...data, requestSignature: signature };
  };

  const regM = useMutation({ mutationFn: runRegression });
  const conditionsChanged = Boolean(regM.data && regM.data.requestSignature !== requestSignature);
  const predictionSignature = contentSignature({ requestSignature, inputs: predictInputs, model: regM.data?.analysis?.model_signature });

  const cohortKeySig = keys.join("|");
  useEffect(() => {
    regM.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 단지 구성이 바뀌면 이전 식은 무효
  }, [cohortKeySig]);

  const aiRegressionContext = useMemo(() => {
    if (!regM.data) return null;
    const context = buildCollectiveRegressionContext(regM.data, {
      regionLabel: regM.data.display_name,
      assetType,
      cohort: useCohort,
    });
    context.facts = { ...context.facts, conditions_changed: conditionsChanged,
      result_state: conditionsChanged ? "previous_conditions" : "current" };
    return context;
  }, [regM.data, assetType, useCohort, conditionsChanged]);

  const publishedAiContext = useMemo(
    () =>
      aiRegressionContext ?? {
        app: "collective" as const,
        panel: "BuildingRegressionPanel",
        purpose: "statistics" as const,
        scope: { asset_type: assetType },
        facts: { cohort: (cohortKeys?.length ?? 0) > 1 },
      },
    [aiRegressionContext, assetType, cohortKeys],
  );

  useEffect(() => {
    if (!aiRegressionContext) return;
    notifyAiEngineReady(recordAnalysisHistory(aiRegressionContext));
  }, [aiRegressionContext]);

  useEffect(() => {
    const on = (e: Event) => {
      const a = (e as CustomEvent<AiScreenAction>).detail;
      if (a?.kind !== "run_engine") return;
      if (!canRun) return;
      regM.mutate();
    };
    window.addEventListener(CH2_AI_ACTION_EVENT, on);
    return () => window.removeEventListener(CH2_AI_ACTION_EVENT, on);
  }, [canRun]);

  const predictM = useMutation({
    mutationFn: async () => {
      if (conditionsChanged) throw new Error("분석 조건이 바뀌었습니다. 아래 결과는 이전 조건으로 계산했습니다.");
      const signature = predictionSignature;
      const body = {
        ...regressionBody,
        expected_model_signature: regM.data?.analysis?.model_signature,
        model_type: regM.data?.model_type ?? modelType,
        inputs: predictInputs,
      };
      const data = await (useCohort
        ? predictCohortRegression({ building_keys: keys, ...body })
        : predictBuildingRegression(buildingKey, body));
      return { ...data, inputSignature: signature };
    },
  });

  // 입력·적합 모형이 바뀌면 이전 요청의 오류와 진행 상태도 무효화한다.
  const resetPrediction = predictM.reset;
  useEffect(() => { resetPrediction(); }, [predictionSignature, resetPrediction]);
  useEffect(() => {
    predictM.reset();
    if (regM.data?.predict_options) {
      const defaults = defaultPredictInputs(regM.data.predict_options, vars);
      const opts = regM.data.predict_options;
      setPredictInputs((current) => {
        const next = reconcileListedInputs(defaults, current, {
          building_key: (opts.buildings ?? []).filter(b => !(opts.buildings ?? []).some(o => o.is_reference || o.has_fe) || b.is_reference || b.has_fe).map(b => b.building_key),
          contract_period: opts.contract_periods ?? [], housing_subtype: opts.housing_subtypes ?? [],
          structure_group: opts.structure_groups ?? [], asset_type: opts.asset_types ?? [],
        });
        const options = opts.dong_options?.filter(o => !o.building_key || o.building_key === next.building_key);
        const allowed = options?.length ? options.map(o => o.dong) : opts.dongs ?? [];
        if (!allowed.includes(next.dong ?? "")) next.dong = options?.find(o => o.is_reference)?.dong ?? allowed[0];
        return next;
      });
    }
  }, [regM.data]);

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-medium text-slate-700 dark:text-slate-200">회귀 분석</p>
        <div className="flex items-center gap-2 shrink-0">
          <PublishAiContext context={publishedAiContext} />
          <AnalysisHelpPanel explain={regM.data?.explain ?? RESIDENTIAL_REGRESSION_HELP} />
        </div>
      </div>

      {useCohort && (
        <p className="text-[10px] text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-100 dark:border-indigo-900 rounded px-2 py-1.5">
          {keys.length}개 단지를 함께 분석합니다. 면적·층·시점의 계수는 공유합니다. 변수를 고른 뒤 「
          {regM.data ? "통합 회귀 다시 실행" : "통합 회귀 실행"}」을 누르세요.{" "}
          {regM.data && !conditionsChanged && regM.data.analysis
            ? regM.data.analysis.feature_names.some(name => name.startsWith("bld_"))
              ? "현재 결과는 단지별 가격 수준의 차이를 고정효과로 구분합니다."
              : "현재 결과에는 단지 고정효과 계수가 없습니다. 실제 반영 변수는 분석 기준에서 확인하세요."
            : attrOn
              ? "단지 특성을 선택했습니다. 실행 후 실제 반영 여부를 확인하세요."
              : "단지별 가격 수준의 차이를 고정효과로 구분합니다 (거래 최다 단지 기준, 거래 5건 미만 단지 제외)."}
          {" · 동은 단지별로 구분"}
        </p>
      )}
      <RegressionSampleHint
        useCohort={useCohort}
        countTotal={countTotal}
        countRecent={countRecent}
        messages={gateMessages}
      />

      <p className="text-[10px] text-slate-500 dark:text-slate-400">
        변수가 시세에 어떤 방향·크기로 작용하는지 탐색합니다. 기본은 선형(만원). % 해석은 로그 옵션.
        층·동 % 지수는 「효용지수」 탭을 참고하세요.
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
            ["contract_period", "거래시점(반기)"],
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
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={modelType === "log"}
            onChange={(e) => setModelType(e.target.checked ? "log" : "linear")}
          />
          <span className="inline-flex items-center gap-0.5">
            로그(% 해석)
            <StatsGlossaryHelp termId="log_model" size="xs" />
            <span className="text-[10px] text-slate-500">금액만 로그. 전용면적은 그대로.</span>
          </span>
        </label>
      </div>

      {useCohort && (
        <details className="rounded border border-slate-300 dark:border-slate-500 px-2.5 py-2">
          <summary className="cursor-pointer text-sm font-semibold text-slate-800 dark:text-slate-100">
            고급 분석 · 단지 특성{attrOn ? " · 켜짐" : ""}
          </summary>
          <div className="mt-2 space-y-1.5">
            <p className="text-[11px] leading-snug text-slate-600 dark:text-slate-300">
              세대수·주차·공시지가·구조·유형으로 단지 사이 가격 차이를 탐색합니다. 표본 보강과 목적이
              다릅니다. 단지 특성이 실제 모형에 포함될 때 단지 고정효과를 제외합니다. 체크해도 자료가 없거나 값이 같으면 생략됩니다. 개별공시지가는 지금 단지·유형당 스냅샷
              하나입니다.
            </p>
            {keys.length <= 3 && (
              <p className="text-[11px] leading-snug text-amber-800 dark:text-amber-200">
                단지가 {keys.length}곳이면 이 계수는 단지 사이 차이에 이름을 붙인 것입니다. 거래가
                많아도 단지 수가 적으면 그대로입니다.
              </p>
            )}
            <p className="text-[10px] text-slate-500 dark:text-slate-400">
              같은 지번 오피스텔 복사(kapt_same_pnu) 세대수·주차는 이 유형 재고가 아니라 빠집니다.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              {(
                [
                  ["households", "총 세대수"],
                  ["parking", "세대당 주차"],
                  ["assessed_land_price", "개별공시지가"],
                  ["structure", "구조"],
                  ["asset_type_dummy", "유형"],
                ] as const
              ).map(([key, label]) => (
                <label
                  key={key}
                  className="flex items-center gap-2"
                  title={
                    key === "structure"
                      ? "시군구 회귀에서는 예측 개선이 약했습니다. 코호트는 단지 간 차이가 있을 때만 식별됩니다."
                      : key === "asset_type_dummy"
                        ? "한 건물에서 층으로 유형이 갈리면(예: 저층 오피·고층 아파트) 유형 계수에 층 효과가 섞입니다."
                        : key === "assessed_land_price"
                          ? "지금 값은 단지·유형당 스냅샷 하나입니다."
                          : undefined
                  }
                >
                  <input
                    type="checkbox"
                    checked={vars[key]}
                    onChange={(e) => setVars((v) => ({ ...v, [key]: e.target.checked }))}
                  />
                  {label}
                </label>
              ))}
            </div>
            {vars.asset_type_dummy && (
              <p className="text-[10px] text-amber-700 dark:text-amber-300">
                한 건물에서 층으로 유형이 갈리면 유형 계수에 층 효과가 섞입니다. 같은 층에 두 유형이 있을 때만 순수 유형 효과로 읽으세요.
              </p>
            )}
          </div>
        </details>
      )}

      {vars.floor && (
        <div className="text-xs space-y-1">
          <span className="text-slate-600 dark:text-slate-400 font-medium">
            {assetType === "rowhouse"
              ? "층 구간 · 1층·중간·최상 기본"
              : "층 구간 · 단지별 최고층 대비 상대층 기본"}
          </span>
          {!floorAdvanced ? (
            <button
              type="button"
              className="text-[11px] text-indigo-700 dark:text-indigo-400 underline"
              onClick={() => setFloorAdvanced(true)}
            >
              고급: 층 형식 변경
            </button>
          ) : (
            <select
              className="border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900 w-full max-w-md"
              value={floorMode}
              onChange={(e) => setFloorMode(e.target.value as FloorMode)}
            >
              {assetType === "rowhouse" ? (
                <option value="rowhouse">1층·중간·최상 (그 건물 최고층)</option>
              ) : (
                <option value="relative">상대 층 (단지별 최고층 대비 1·저·중·고·최상)</option>
              )}
              <option value="dummy">층별 더미 (개별 층)</option>
              <option value="grouped">절대 구간 (1–5 / 6–15 / 16+)</option>
              <option value="linear">층 선형</option>
            </select>
          )}
        </div>
      )}

      <label className="flex items-center gap-2 text-xs">
        <input type="checkbox" checked={excludeOutliers} onChange={(e) => setExcludeOutliers(e.target.checked)} />
        IQR 이상치 제외
      </label>
      <label className="flex items-center gap-2 text-xs">
        범주 결측
        <select
          className="border border-slate-200 rounded px-1 py-0.5 dark:bg-slate-900"
          value={categoricalMissing}
          onChange={(e) => setCategoricalMissing(e.target.value as "keep_unknown" | "drop")}
        >
          <option value="keep_unknown">미상 범주 유지</option>
          <option value="drop">결측 거래 제외</option>
        </select>
      </label>

      <button
        type="button"
        className="btn btn-primary text-xs"
        disabled={regM.isPending || !canRun}
        onClick={() => regM.mutate()}
      >
        {regressionRunLabel({
          pending: regM.isPending,
          useCohort,
          hasResult: Boolean(regM.data),
          canRun,
          recommended,
        })}
      </button>

      {regM.isError && (
        <p className="text-xs text-red-600 dark:text-red-400">
          {(regM.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "회귀 실패"}
        </p>
      )}
      {regM.data && conditionsChanged && (
        <p className="text-[10px] text-amber-700 dark:text-amber-300">
          분석 조건이 바뀌었습니다. 아래 결과는 이전 조건으로 계산했습니다.
        </p>
      )}
      {regM.data && (
        <CollectiveRegressionResults
          data={regM.data}
          modelType={modelType}
          logNote="금액만 로그입니다. 전용면적은 그대로입니다."
        />
      )}

      {regM.data?.predict_options && (
        <PredictPanel
          opts={regM.data.predict_options}
          groups={regM.data.analysis?.sample_groups}
          vars={vars}
          floorMode={floorMode}
          useCohort={useCohort}
          inputs={predictInputs}
          setInputs={setPredictInputs}
          onPredict={() => predictM.mutate()}
          pending={predictM.isPending}
          disabled={conditionsChanged || regM.isPending}
          result={!conditionsChanged && !regM.isPending && predictM.data?.inputSignature === predictionSignature ? predictM.data : undefined}
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
      {regM.data && (
        <CollectiveModelRecommend
          candidates={regM.data.model_candidates}
          selectedType={modelType}
          selectedBlocks={selectedBlocks}
          selectionN={regM.data.n}
          datasetNote="지금 연 건물과 추가한 단지의 거래만 사용합니다."
          onAdopt={(pick) => {
            setModelType(pick.modelType);
            setVars((prev) => {
              const next = { ...prev };
              (Object.keys(next) as (keyof RegressionVars)[]).forEach((key) => {
                next[key] = pick.blocks.includes(key);
              });
              return next;
            });
          }}
        />
      )}
    </div>
  );
}
