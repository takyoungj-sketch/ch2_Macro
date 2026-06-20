import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  predictCommercialCohortRegression,
  predictCommercialRegression,
  runCommercialCohortRegression,
  runCommercialRegression,
} from "../api/commercialClient";
import type {
  CommercialPredictOptions,
  CommercialRegressionPredictInputs,
  CommercialRegressionPredictResponse,
  CommercialRegressionResponse,
  RegressionModelType,
} from "../types";
import { buildAnalysisPeriodParams } from "../utils/analysisPeriod";
import type { CommercialModalScope } from "./CommercialClusterDetailModal";
import { ModelComparisonCard, RegressionTable, type FloorMode } from "./BuildingRegressionPanel";
import AnalysisHelpPanel from "./AnalysisHelpPanel";

function fmt(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function fmtInt(v: number | null | undefined) {
  if (v == null) return "—";
  return Math.round(v).toLocaleString("ko-KR");
}

function midRange(min?: number | null, max?: number | null): number | undefined {
  if (min == null || max == null) return undefined;
  return Math.round(((min + max) / 2) * 10) / 10;
}

function fallbackCommercialPredictOptions(
  vars: {
    gross_area: boolean;
    land_area: boolean;
    building_age: boolean;
    floor: boolean;
    zone_type: boolean;
    building_use: boolean;
    road_width: boolean;
    road_code: boolean;
    addr4: boolean;
  },
  floorMode: FloorMode,
  isShop: boolean,
): CommercialPredictOptions {
  return {
    floor_mode: floorMode,
    gross_area: vars.gross_area ? { name: "gross_area", min: 30, max: 300 } : null,
    land_area: vars.land_area ? { name: "land_area", min: 50, max: 500 } : null,
    building_age: vars.building_age ? { name: "building_age", min: 0, max: 40 } : null,
    floor: vars.floor ? { name: "floor", min: 1, max: 10 } : null,
    road_code: !isShop && vars.road_code ? { name: "road_code", min: 4, max: 25 } : null,
  };
}
function defaultCommercialPredictInputs(
  opts: CommercialPredictOptions | null | undefined,
  vars: {
    gross_area: boolean;
    land_area: boolean;
    building_age: boolean;
    floor: boolean;
    zone_type: boolean;
    building_use: boolean;
    road_width: boolean;
    road_code: boolean;
    addr4: boolean;
  },
  isShop: boolean,
): CommercialRegressionPredictInputs {
  if (!opts) return {};
  return {
    gross_area: vars.gross_area ? midRange(opts.gross_area?.min, opts.gross_area?.max) : undefined,
    land_area: vars.land_area ? midRange(opts.land_area?.min, opts.land_area?.max) : undefined,
    building_age: vars.building_age ? midRange(opts.building_age?.min, opts.building_age?.max) : undefined,
    floor: vars.floor ? midRange(opts.floor?.min, opts.floor?.max) : undefined,
    road_code: !isShop && vars.road_code ? midRange(opts.road_code?.min, opts.road_code?.max) : undefined,
    zone_type: vars.zone_type ? opts.zone_reference ?? opts.zone_types?.[0] : undefined,
    building_use: vars.building_use ? opts.building_use_reference ?? opts.building_uses?.[0] : undefined,
    road_width: isShop && vars.road_width ? opts.road_width_reference ?? opts.road_widths?.[0] : undefined,
    addr4: vars.addr4 ? opts.addr4_reference ?? opts.addr4_list?.[0] : undefined,
    cluster_key: opts.clusters?.find((c) => c.is_reference)?.cluster_key ?? opts.clusters?.[0]?.cluster_key,
  };
}

function CommercialPredictPanel({
  opts,
  vars,
  floorMode,
  useCohort,
  isShop,
  inputs,
  setInputs,
  onPredict,
  pending,
  result,
  error,
}: {
  opts: CommercialPredictOptions;
  vars: {
    gross_area: boolean;
    land_area: boolean;
    building_age: boolean;
    floor: boolean;
    zone_type: boolean;
    building_use: boolean;
    road_width: boolean;
    road_code: boolean;
    addr4: boolean;
  };
  floorMode: FloorMode;
  useCohort: boolean;
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
      <p className="text-[11px] font-medium text-slate-700 dark:text-slate-200">예측 (변수값 입력)</p>
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
        {vars.land_area && opts.land_area && (
          <label className="space-y-0.5">
            <span className="text-slate-500 dark:text-slate-400">대지면적(㎡)</span>
            <input
              type="number"
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.land_area ?? ""}
              onChange={(e) =>
                setInputs((p) => ({ ...p, land_area: e.target.value ? Number(e.target.value) : undefined }))
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
                  {d === opts.zone_reference ? " (기준)" : ""}
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
        {isShop && vars.road_width && (opts.road_widths?.length ?? 0) > 0 && (
          <label className="space-y-0.5">
            <span className="text-slate-500 dark:text-slate-400">도로폭</span>
            <select
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.road_width ?? ""}
              onChange={(e) => setInputs((p) => ({ ...p, road_width: e.target.value || undefined }))}
            >
              {opts.road_widths!.map((d) => (
                <option key={d} value={d}>
                  {d}
                  {d === opts.road_width_reference ? " (기준)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}
        {vars.addr4 && (opts.addr4_list?.length ?? 0) > 0 && (
          <label className="space-y-0.5">
            <span className="text-slate-500 dark:text-slate-400">동(addr4)</span>
            <select
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.addr4 ?? ""}
              onChange={(e) => setInputs((p) => ({ ...p, addr4: e.target.value || undefined }))}
            >
              {opts.addr4_list!.map((d) => (
                <option key={d} value={d}>
                  {d}
                  {d === opts.addr4_reference ? " (기준)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}
        {useCohort && (opts.clusters?.length ?? 0) > 0 && (
          <label className="space-y-0.5 sm:col-span-2">
            <span className="text-slate-500 dark:text-slate-400">도로 (FE)</span>
            <select
              className="w-full border border-slate-200 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-900"
              value={inputs.cluster_key ?? ""}
              onChange={(e) => setInputs((p) => ({ ...p, cluster_key: e.target.value || undefined }))}
            >
              {opts.clusters!.map((c) => (
                <option key={c.cluster_key} value={c.cluster_key}>
                  {c.display_label}
                  {c.is_reference ? " (FE 기준)" : c.has_fe ? "" : " (FE 제외)"}
                  {" · n="}
                  {c.count}
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

function toRegressionTableData(data: CommercialRegressionResponse) {
  return {
    building_key: data.cluster_key,
    display_name: data.display_label,
    n: data.n,
    model_type: data.model_type,
    r_squared: data.r_squared,
    adj_r_squared: data.adj_r_squared,
    coefficients: data.coefficients,
    warnings: data.warnings,
  };
}

export default function CommercialRegressionPanel({
  clusterKey,
  cohortKeys,
  cohortRunId = 0,
  scope,
  periodStart,
  periodEnd,
  isShop,
  count,
}: {
  clusterKey: string;
  cohortKeys?: string[];
  cohortRunId?: number;
  scope: CommercialModalScope;
  periodStart?: string | null;
  periodEnd?: string | null;
  isShop: boolean;
  count: number;
}) {
  const [excludeOutliers, setExcludeOutliers] = useState(false);
  const [floorMode, setFloorMode] = useState<FloorMode>("relative");
  const [modelType, setModelType] = useState<RegressionModelType>("log");
  const [predictInputs, setPredictInputs] = useState<CommercialRegressionPredictInputs>({});
  const [vars, setVars] = useState({
    gross_area: true,
    land_area: !isShop,
    building_age: true,
    floor: isShop,
    zone_type: true,
    building_use: true,
    road_width: isShop,
    road_code: !isShop,
    addr4: false,
  });

  const useCohort = cohortRunId > 0 && (cohortKeys?.length ?? 0) > 1;
  const keys = useCohort ? cohortKeys! : [clusterKey];

  const regressionEligible = count >= 30;
  const gateTip =
    `회귀 분석: 선택 구간 거래 ${count}건 (최소 30건 필요)` +
    (count >= 15 ? "" : " · 최근 3년 15건 이상도 권장");

  const periodParams = buildAnalysisPeriodParams(
    scope.yearFrom === "" ? undefined : scope.yearFrom,
    scope.yearTo === "" ? undefined : scope.yearTo,
    periodStart,
    periodEnd,
  );

  const regressionBody = {
    ...regionParams(scope),
    ...periodParams,
    exclude_outliers_iqr: excludeOutliers,
    experiment: !regressionEligible,
    model_type: modelType,
    variables: { ...vars, floor_mode: floorMode },
  };

  const regM = useMutation({
    mutationFn: () =>
      useCohort
        ? runCommercialCohortRegression({
            cluster_keys: keys,
            asset_type: scope.assetType === "all" ? undefined : scope.assetType,
            exclude_outliers_iqr: excludeOutliers,
            experiment: !regressionEligible,
            model_type: modelType,
            variables: { ...vars, floor_mode: floorMode },
            ...periodParams,
          })
        : runCommercialRegression(clusterKey, regressionBody),
  });

  const predictM = useMutation({
    mutationFn: () => {
      const body = { ...regressionBody, inputs: predictInputs };
      return useCohort
        ? predictCommercialCohortRegression({
            cluster_keys: keys,
            asset_type: scope.assetType === "all" ? undefined : scope.assetType,
            ...body,
          })
        : predictCommercialRegression(clusterKey, body);
    },
  });

  useEffect(() => {
    if (!regM.data || regM.data.coefficients.length === 0) return;
    const opts =
      regM.data.predict_options ?? fallbackCommercialPredictOptions(vars, floorMode, isShop);
    setPredictInputs(defaultCommercialPredictInputs(opts, vars, isShop));
  }, [regM.data, vars, floorMode, isShop]);

  const predictOpts =
    regM.data?.predict_options ??
    (regM.data && regM.data.coefficients.length > 0
      ? fallbackCommercialPredictOptions(vars, floorMode, isShop)
      : null);
  const showPredictPanel = Boolean(regM.data && regM.data.coefficients.length > 0 && predictOpts);

  useEffect(() => {
    const rec = regM.data?.model_comparison?.recommended;
    if (rec && rec !== modelType) {
      setModelType(rec);
    }
  }, [regM.data?.model_comparison?.recommended]);

  useEffect(() => {
    if (useCohort && cohortRunId > 0) {
      regM.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- cohortRunId triggers cohort run
  }, [cohortRunId, keys.join("|")]);

  const varOptions = (
    [
      ["gross_area", "연면적"],
      ["land_area", "대지면적"],
      ["building_age", "연식"],
      ["floor", "층"],
      ["zone_type", "용도지역"],
      ["building_use", "건축물용도"],
      ...(isShop ? ([["road_width", "도로폭"]] as const) : ([["road_code", "도로폭(m)"]] as const)),
      ["addr4", "동(addr4)"],
    ] as const
  );

  if (useCohort && cohortRunId === 0) {
    return (
      <p className="text-xs text-slate-500 text-center py-6">
        코호트에 도로를 추가한 뒤 「통합분석」을 누르면 통합 회귀 결과가 표시됩니다.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-medium text-slate-700 dark:text-slate-200">회귀 분석 (탐색용)</p>
        {regM.data?.explain && <AnalysisHelpPanel explain={regM.data.explain} />}
      </div>

      {useCohort && (
        <p className="text-[10px] text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-100 dark:border-indigo-900 rounded px-2 py-1.5">
          {keys.length}개 도로 cluster 통합 · n={regM.data?.n.toLocaleString("ko-KR") ?? "—"}
        </p>
      )}

      {!useCohort && !regressionEligible && (
        <p className="text-[11px] text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 border border-amber-100 dark:border-amber-900 rounded px-2 py-1.5">
          {gateTip} — 표본이 적어도 참고용으로 실행할 수 있습니다. 아래에서 인접 도로를 추가해 「통합분석」을
          권장합니다.
        </p>
      )}

      <p className="text-[10px] text-slate-500 dark:text-slate-400">
        탐색용 OLS — 회귀 실행 후 변수값을 넣어 개별 거래 95% 예측구간(PI)을 확인할 수 있습니다.
      </p>

      <p className="text-[10px] text-slate-500 dark:text-slate-400">
        금액(만원) ~ 연면적·{isShop ? "연식·층·용도 등" : "대지면적·연식·용도 등"} · 시점(반기) 통제 · HC3 SE.
        {useCohort ? " 코호트 시 도로(cluster) FE로 수준 차를 통제합니다." : " 단일 도로(cluster) 거래만 사용합니다."}
      </p>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
        {varOptions.map(([key, label]) => (
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
          <span className="text-slate-600 dark:text-slate-300 font-medium">층 변수 형식</span>
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

      <div className="flex flex-wrap gap-3 text-xs items-center">
        <span className="text-slate-600 dark:text-slate-300 font-medium">회귀 방식</span>
        {(["log", "linear"] as const).map((mt) => (
          <label key={mt} className="flex items-center gap-1">
            <input type="radio" checked={modelType === mt} onChange={() => setModelType(mt)} />
            {mt === "log" ? "로그(권장)" : "선형"}
            {regM.data?.model_comparison?.recommended === mt && (
              <span className="text-[10px] text-emerald-600">권장</span>
            )}
          </label>
        ))}
      </div>

      <label className="flex items-center gap-2 text-xs">
        <input type="checkbox" checked={excludeOutliers} onChange={(e) => setExcludeOutliers(e.target.checked)} />
        IQR 이상치 제외
      </label>

      <button type="button" className="btn btn-primary text-xs" disabled={regM.isPending} onClick={() => regM.mutate()}>
        {regM.isPending ? "실행 중…" : useCohort ? "통합 회귀 다시 실행" : "회귀 실행"}
      </button>

      {regM.isError && (
        <p className="text-xs text-red-600">
          {(regM.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "회귀 실패"}
        </p>
      )}

      {showPredictPanel && predictOpts && (
        <CommercialPredictPanel
          opts={predictOpts}
          vars={vars}
          floorMode={floorMode}
          useCohort={useCohort}
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

      {regM.data?.model_comparison && (
        <ModelComparisonCard cmp={regM.data.model_comparison} selected={modelType} />
      )}
      {regM.data && <RegressionTable data={toRegressionTableData(regM.data)} />}
    </div>
  );
}
