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
  RegressionModelType,
} from "../types";
import { ASSET_LABELS } from "../types";
import { buildAnalysisPeriodParams } from "../utils/analysisPeriod";
import { RESIDENTIAL_REGRESSION_HELP } from "../utils/residentialAnalysisHelp";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { recordAnalysisHistory } from "@ch2/ai-assistant/aiClient";
import {
  CH2_AI_ACTION_EVENT,
  notifyAiEngineReady,
  type AiScreenAction,
} from "@ch2/ai-assistant/aiActions";
import { buildCollectiveRegressionContext } from "../api/aiContext";
import { CollectiveRegressionResults } from "./CollectiveRegressionResults";
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
};

function midRange(r?: { min?: number | null; max?: number | null } | null): number | undefined {
  if (!r) return undefined;
  if (r.min != null && r.max != null) return (r.min + r.max) / 2;
  return r.min ?? r.max ?? undefined;
}

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
    households: vars.households ? midRange(opts.households) : undefined,
    parking_per_household: vars.parking ? midRange(opts.parking_per_household) : undefined,
    assessed_land_price: vars.assessed_land_price ? midRange(opts.assessed_land_price) : undefined,
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
  result,
  error,
}: {
  opts: CollectivePredictOptions;
  vars: RegressionVars;
  floorMode: FloorMode;
  useCohort: boolean;
  inputs: CollectiveRegressionPredictInputs;
  setInputs: React.Dispatch<React.SetStateAction<CollectiveRegressionPredictInputs>>;
  onPredict: () => void;
  pending: boolean;
  result?: CollectiveRegressionPredictResponse;
  error?: string;
}) {
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
      <p className="text-[11px] font-medium text-slate-700 dark:text-slate-200">가정 시나리오 (참고)</p>
      <p className="text-[10px] text-slate-500 dark:text-slate-400">
        아래 조건에서 모형이 가리키는 금액 수준입니다. AVM·적정가가 아닙니다.
      </p>
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
                <option key={b.building_key} value={b.building_key}>
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

      <button type="button" className="btn btn-primary text-xs" disabled={pending} onClick={onPredict}>
        {pending ? "계산 중…" : "시나리오 계산"}
      </button>

      {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}

      {result && (
        <div className="rounded-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-600 p-3 space-y-2">
          <div>
            <span className="text-slate-500 dark:text-slate-400 text-[10px]">
              시나리오 금액 (참고)
              {result.model_type ? ` · ${result.model_type === "log" ? "로그" : "선형"}` : ""}
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
              <span className="font-medium">95% 평균 신뢰구간</span>{" "}
              {fmtInt(result.ci_lower)} ~ {fmtInt(result.ci_upper)}만원
            </div>
            <div className="text-slate-500 dark:text-slate-400">
              95% 예측구간 (개별 거래) {fmtInt(result.pi_lower)} ~ {fmtInt(result.pi_upper)}만원
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
  const [floorAdvanced, setFloorAdvanced] = useState(false);
  const [modelType, setModelType] = useState<RegressionModelType>("linear");
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
  });
  const [predictInputs, setPredictInputs] = useState<CollectiveRegressionPredictInputs>({});

  const useCohort = cohortRunId > 0 && (cohortKeys?.length ?? 0) > 1;
  const keys = useCohort ? cohortKeys! : [buildingKey];
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

  const aiRegressionContext = useMemo(() => {
    if (!regM.data) return null;
    return buildCollectiveRegressionContext(regM.data, {
      regionLabel: regM.data.display_name,
      assetType,
      cohort: useCohort,
    });
  }, [regM.data, assetType, useCohort]);

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
      if ((cohortKeys?.length ?? 0) > 1) return;
      regM.mutate();
    };
    window.addEventListener(CH2_AI_ACTION_EVENT, on);
    return () => window.removeEventListener(CH2_AI_ACTION_EVENT, on);
  }, [cohortKeys]);

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

  if (useCohort && cohortRunId === 0) {
    return (
      <>
        <PublishAiContext context={publishedAiContext} />
        <p className="text-xs text-slate-500 text-center py-6">
          코호트에 아파트를 추가한 뒤 「통합분석」을 누르면 통합 회귀 결과가 표시됩니다.
        </p>
      </>
    );
  }

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
          {keys.length}개 단지 통합 · 실시간 ·{" "}
          {attrOn
            ? "단지 속성으로 단지 간 차이 설명 (단지 FE 생략 — 속성은 단지마다 상수라 FE와 같이 넣을 수 없음)"
            : "단지 고정효과(거래 최다 단지=기준, n<5 제외)"}
          {" · 동은 단지별로 구분"}
        </p>
      )}
      {!useCohort && !regressionEligible && (
        <p className="text-[11px] text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 border border-amber-100 dark:border-amber-900 rounded px-2 py-1.5">
          {gateTip ?? "권장 표본 기준 미달"} — 실험 단계에서는 아래 옵션으로 실행할 수 있습니다.
        </p>
      )}

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
          로그(% 해석)
        </label>
      </div>

      {useCohort && (
        <div className="space-y-1.5">
          <p className="text-[10px] text-slate-500 dark:text-slate-400">
            단지 속성 (기본 꺼짐). 켜면 단지 FE 대신 단지 간 차이를 이 변수로 설명합니다.
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
      )}

      {vars.floor && (
        <div className="text-xs space-y-1">
          <span className="text-slate-600 dark:text-slate-400 font-medium">
            층 구간 · 상대(1·저·중·고·최상) 기본
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
              <option value="relative">상대 층 (1·최상·저·중·고 / max층)</option>
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
      {regM.data && (
        <CollectiveRegressionResults data={regM.data} modelType={modelType} />
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
