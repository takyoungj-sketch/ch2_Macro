import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { predictCommercialRegression, runCommercialCohortRegression, runCommercialRegression, predictCommercialCohortRegression } from "../api/commercialClient";
import { buildCommercialRegressionContext } from "../api/aiContext";
import type {
  CommercialPredictOptions,
  CommercialRegressionPredictInputs,
  CommercialRegressionPredictResponse,
  CommercialRegressionResponse,
  RegressionModelType,
} from "../types";
import type { CommercialModalScope } from "./CommercialClusterDetailModal";
import { CollectiveRegressionResults } from "./CollectiveRegressionResults";
import type { FloorMode } from "../utils/collectiveRegressionTypes";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import AiAssistantPanel from "@ch2/ai-assistant/AiAssistantPanel";

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

function toResultsData(data: CommercialRegressionResponse) {
  return {
    warnings: data.warnings,
    model_type: data.model_type ?? ("linear" as RegressionModelType),
    n: data.n,
    r_squared: data.r_squared,
    adj_r_squared: data.adj_r_squared,
    mape: data.mape,
    f_p_value: data.f_p_value,
    significant_count: data.significant_count,
    equation: data.equation,
    coefficients: data.coefficients,
  };
}

type CommercialVars = {
  gross_area: boolean;
  building_age: boolean;
  floor: boolean;
  zone_type: boolean;
  building_use: boolean;
  road_width: boolean;
  road_code: boolean;
};

function midRange(min?: number | null, max?: number | null): number | undefined {
  if (min == null || max == null) return undefined;
  return Math.round(((min + max) / 2) * 10) / 10;
}

function defaultCommercialPredictInputs(
  opts: CommercialPredictOptions | null | undefined,
  vars: CommercialVars,
  isShop: boolean,
): CommercialRegressionPredictInputs {
  if (!opts) return {};
  return {
    road_code: !isShop && vars.road_code ? midRange(opts.road_code?.min, opts.road_code?.max) : undefined,
    zone_type: vars.zone_type ? opts.zone_type_reference ?? opts.zone_types?.[0] : undefined,
    building_use: vars.building_use ? opts.building_use_reference ?? opts.building_uses?.[0] : undefined,
    road_width_label: isShop && vars.road_width
      ? opts.road_width_reference ?? opts.road_width_labels?.[0]
      : undefined,
  };
}

function fmtInt(v: number | null | undefined) {
  if (v == null) return "—";
  return Math.round(v).toLocaleString("ko-KR");
}

function fmt(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function CommercialPredictPanel({
  opts,
  vars,
  floorMode,
  isShop,
  inputs,
  setInputs,
  onPredict,
  pending,
  result,
  error,
}: {
  opts: CommercialPredictOptions;
  vars: CommercialVars;
  floorMode: FloorMode;
  isShop: boolean;
  inputs: CommercialRegressionPredictInputs;
  setInputs: React.Dispatch<React.SetStateAction<CommercialRegressionPredictInputs>>;
  onPredict: () => void;
  pending: boolean;
  result?: CommercialRegressionPredictResponse;
  error?: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-600 bg-slate-50/50 dark:bg-slate-800/40 p-3 space-y-3">
      <p className="text-[11px] font-medium text-slate-700 dark:text-slate-200">가정 시나리오 (참고)</p>
      <p className="text-[10px] text-slate-500 dark:text-slate-400">
        아래 조건에서 모형이 가리키는 금액 수준입니다. AVM·적정가가 아닙니다.
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
        {vars.gross_area && opts.gross_area && (
          <label className="space-y-0.5">
            <span className="text-slate-500 dark:text-slate-400">연면적(㎡)</span>
            <input
              type="number"
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.gross_area ?? ""}
              onChange={(e) =>
                setInputs((p) => ({ ...p, gross_area: e.target.value ? Number(e.target.value) : undefined }))
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
        {!isShop && vars.road_code && opts.road_code && (
          <label className="space-y-0.5">
            <span className="text-slate-500 dark:text-slate-400">도로폭(m)</span>
            <input
              type="number"
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.road_code ?? ""}
              onChange={(e) =>
                setInputs((p) => ({ ...p, road_code: e.target.value ? Number(e.target.value) : undefined }))
              }
            />
          </label>
        )}
        {vars.zone_type && (opts.zone_types?.length ?? 0) > 0 && (
          <label className="space-y-0.5">
            <span className="text-slate-500 dark:text-slate-400">용도지역</span>
            <select
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.zone_type ?? ""}
              onChange={(e) => setInputs((p) => ({ ...p, zone_type: e.target.value || undefined }))}
            >
              {opts.zone_types!.map((d) => (
                <option key={d} value={d}>
                  {d}
                  {d === opts.zone_type_reference ? " (기준)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}
        {vars.building_use && (opts.building_uses?.length ?? 0) > 0 && (
          <label className="space-y-0.5">
            <span className="text-slate-500 dark:text-slate-400">건축물용도</span>
            <select
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.building_use ?? ""}
              onChange={(e) => setInputs((p) => ({ ...p, building_use: e.target.value || undefined }))}
            >
              {opts.building_uses!.map((d) => (
                <option key={d} value={d}>
                  {d}
                  {d === opts.building_use_reference ? " (기준)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}
        {isShop && vars.road_width && (opts.road_width_labels?.length ?? 0) > 0 && (
          <label className="space-y-0.5">
            <span className="text-slate-500 dark:text-slate-400">도로폭</span>
            <select
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.road_width_label ?? ""}
              onChange={(e) => setInputs((p) => ({ ...p, road_width_label: e.target.value || undefined }))}
            >
              {opts.road_width_labels!.map((d) => (
                <option key={d} value={d}>
                  {d}
                  {d === opts.road_width_reference ? " (기준)" : ""}
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

export default function CommercialRegressionPanel({
  clusterKey,
  scope,
  isShop,
  count,
  cohortKeys,
  cohortRunId = 0,
  analysisPeriod,
}: {
  clusterKey: string;
  scope: CommercialModalScope;
  isShop: boolean;
  count: number;
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
  const [excludeOutliers, setExcludeOutliers] = useState(false);
  const [floorMode, setFloorMode] = useState<FloorMode>("relative");
  const [floorAdvanced, setFloorAdvanced] = useState(false);
  const [modelType, setModelType] = useState<RegressionModelType>("linear");
  const [vars, setVars] = useState<CommercialVars>({
    gross_area: true,
    building_age: true,
    floor: true,
    zone_type: true,
    building_use: true,
    road_width: isShop,
    road_code: !isShop,
  });
  const [predictInputs, setPredictInputs] = useState<CommercialRegressionPredictInputs>({});

  const regressionEligible = count >= 30;
  const gateTip =
    `회귀 분석: 선택 구간 거래 ${count}건 (최소 30건 필요)` +
    (count >= 15 ? "" : " · 최근 3년 15건 이상도 권장");

  const regressionBody = useMemo(
    () => ({
      ...regionParams(scope),
      contract_year_from: scope.yearFrom === "" ? undefined : scope.yearFrom,
      contract_year_to: scope.yearTo === "" ? undefined : scope.yearTo,
      ...(analysisPeriod ?? {}),
      exclude_outliers_iqr: excludeOutliers,
      experiment: !regressionEligible,
      model_type: modelType,
      variables: { ...vars, floor_mode: floorMode },
    }),
    [scope, analysisPeriod, excludeOutliers, regressionEligible, modelType, vars, floorMode],
  );

  const regM = useMutation({
    mutationFn: () =>
      useCohort
        ? runCommercialCohortRegression({ cluster_keys: keys, asset_type: scope.assetType, ...regressionBody })
        : runCommercialRegression(clusterKey, regressionBody),
  });

  const predictM = useMutation({
    mutationFn: () => {
      const body = { ...regressionBody, inputs: predictInputs };
      return useCohort
        ? predictCommercialCohortRegression({ cluster_keys: keys, asset_type: scope.assetType, ...body })
        : predictCommercialRegression(clusterKey, body);
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
      setPredictInputs(defaultCommercialPredictInputs(regM.data.predict_options, vars, isShop));
    }
  }, [regM.data, vars, isShop]);

  const aiRegressionContext = useMemo(() => {
    if (!regM.data) return null;
    return buildCommercialRegressionContext(regM.data, {
      regionLabel: regM.data.display_label,
      assetType: isShop ? "collective_shop" : "collective_factory",
      cohort: useCohort,
    });
  }, [regM.data, isShop, useCohort]);

  if (useCohort && cohortRunId === 0) {
    return (
      <p className="text-xs text-slate-500 text-center py-6">
        코호트에 cluster를 추가한 뒤 「통합분석」을 누르면 통합 회귀 결과가 표시됩니다.
      </p>
    );
  }

  const varOptions = (
    [
      ["gross_area", "연면적"],
      ["building_age", "연식"],
      ["floor", "층"],
      ["zone_type", "용도지역"],
      ["building_use", "건축물용도"],
      ...(isShop ? ([["road_width", "도로폭"]] as const) : ([["road_code", "도로폭(m)"]] as const)),
    ] as const
  );

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-medium text-slate-700">회귀 분석 (탐색용)</p>
        <div className="flex items-center gap-2 shrink-0">
          {aiRegressionContext && <AiAssistantPanel context={aiRegressionContext} />}
          {regM.data?.explain && <AnalysisHelpPanel explain={regM.data.explain} />}
        </div>
      </div>

      {!regressionEligible && (
        <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-100 rounded px-2 py-1.5">
          {gateTip} — 표본이 적어도 참고용으로 실행할 수 있습니다.
        </p>
      )}

      <p className="text-[10px] text-slate-500 dark:text-slate-400">
        변수가 시세에 어떤 방향·크기로 작용하는지 탐색합니다. 기본은 선형(만원). % 해석은 로그 옵션.
        도로(cluster) 내 거래만 사용합니다.
      </p>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
        {varOptions.map(([key, label]) => (
          <label key={key} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={vars[key as keyof CommercialVars]}
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

      {vars.floor && (
        <div className="text-xs space-y-1">
          <span className="text-slate-600 dark:text-slate-400 font-medium">층 구간 · 상대 기본</span>
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
              <option value="relative">상대 층 (1·저·중·고·최상)</option>
              <option value="dummy">개별 층 더미</option>
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

      <button type="button" className="btn btn-primary text-xs" disabled={regM.isPending} onClick={() => regM.mutate()}>
        {regM.isPending ? "실행 중…" : "회귀 실행"}
      </button>

      {regM.isError && (
        <p className="text-xs text-red-600">
          {(regM.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "회귀 실패"}
        </p>
      )}
      {regM.data && (
        <CollectiveRegressionResults data={toResultsData(regM.data)} modelType={modelType} />
      )}

      {regM.data?.predict_options && (
        <CommercialPredictPanel
          opts={regM.data.predict_options}
          vars={vars}
          floorMode={floorMode}
          isShop={isShop}
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
