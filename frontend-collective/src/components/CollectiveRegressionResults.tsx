import { useMemo, useState } from "react";
import AnalysisSummary, { primaryCaution } from "../../../shared/regression-ui/AnalysisSummary";
import { DetailAnalysis } from "../../../shared/regression-ui/ReadingLayout";
import ValidationStatus from "../../../shared/regression-ui/ValidationStatus";
import { formatProbability, formatStatistic } from "../../../shared/regression-ui/format";
import clsx from "clsx";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import type {
  CollectivePredictOptions,
  CollectiveRegressionResponse,
  CommercialPredictOptions,
  RegressionCoeff,
  RegressionModelType,
} from "../types";
import {
  countSignificantCoefficients,
  fmtDecimal,
  isEquationSignificant,
  shortDisplayLabel,
  sigRowClass,
  sortCoefficientsByVariableOrder,
} from "../utils/collectiveRegressionFormat";
import CollectiveRegressionEquation from "./CollectiveRegressionEquation";
import ZoneCaution from "./ZoneCaution";
import AnalysisHelpPanel from "./AnalysisHelpPanel";

function EffectsTable({ coefficients }: { coefficients: RegressionCoeff[] }) {
  const [feOpen, setFeOpen] = useState(false);
  const intercept = coefficients.find((c) => c.name === "const");
  const main = useMemo(
    () =>
      sortCoefficientsByVariableOrder(
        coefficients.filter((c) => c.name !== "const" && !c.name.startsWith("bld_")),
      ),
    [coefficients],
  );
  const fe = useMemo(
    () => sortCoefficientsByVariableOrder(coefficients.filter((c) => c.name.startsWith("bld_"))),
    [coefficients],
  );

  const renderRow = (c: RegressionCoeff) => {
    const sig = isEquationSignificant(c.p);
    return (
      <tr key={c.name} className={clsx(sig && sigRowClass)}>
        <td>{shortDisplayLabel(c.label)}</td>
        <td className="text-center tabular-nums">{formatStatistic(c.coef, 4)}</td>
        <td>{c.effect_plain ?? "—"}</td>
        <td className="text-center tabular-nums">{formatStatistic(c.se)}</td>
        <td className="text-center tabular-nums">{formatStatistic(c.t)}</td>
        <td className="text-center tabular-nums">{formatProbability(c.p)}</td>
      </tr>
    );
  };

  return (
    <div tabIndex={0} role="region" aria-label="회귀 계수 상세 표" className="table-wrap mt-2 overflow-auto">
      <table className="data w-full text-sm border-collapse">
        <thead>
          <tr className="text-slate-600 dark:text-slate-300">
            <th className="text-left font-medium py-1">변수</th>
            <th className="text-center font-medium py-1">β</th>
            <th className="text-left font-medium py-1">
              <span className="inline-flex items-center gap-0.5">
                효과 해석
                <StatsGlossaryHelp termId="coefficient" size="xs" />
              </span>
            </th>
            <th className="text-center font-medium py-1">
              <span className="inline-flex items-center justify-center gap-0.5">
                SE
                <StatsGlossaryHelp termId="se" size="xs" />
              </span>
            </th>
            <th className="text-center font-medium py-1">t</th>
            <th className="text-center font-medium py-1">
              <span className="inline-flex items-center justify-center gap-0.5">
                p
                <StatsGlossaryHelp termId="p_value" size="xs" />
              </span>
            </th>
          </tr>
        </thead>
        <tbody className="text-slate-800 dark:text-slate-200">

          {main.map(renderRow)}
          {fe.length > 0 && (
            <>
              <tr className="bg-slate-50/80 dark:bg-slate-800/60">
                <td colSpan={6} className="py-1">
                  <button
                    type="button"
                    className="text-[11px] font-medium text-indigo-700 dark:text-indigo-400"
                    onClick={() => setFeOpen((v) => !v)}
                  >
                    단지 차이의 비교 기준 ({fe.length}개) {feOpen ? "▲" : "▼"}
                  </button>
                </td>
              </tr>
              {feOpen && fe.map(renderRow)}
            </>
          )}
        </tbody>
      </table>
      {intercept && <details className="mt-3 text-xs">
        <summary className="cursor-pointer py-1">절편의 상세 통계</summary>
        <p className="py-2">계수 {formatStatistic(intercept.coef, 4)} · 표준오차 {formatStatistic(intercept.se)} · t {formatStatistic(intercept.t)} · p {formatProbability(intercept.p)}</p>
      </details>}
    </div>
  );
}

type RegressionResultData = Pick<
  CollectiveRegressionResponse,
  | "analysis"
  | "warnings"
  | "model_type"
  | "n"
  | "r_squared"
  | "adj_r_squared"
  | "mape"
  | "in_sample_mape"
  | "cv_mape"
  | "metric_basis"
  | "f_p_value"
  | "significant_count"
  | "equation"
  | "coefficients"
  | "predict_options"
  | "time_reference"
  | "missing_treatment_label"
  | "augmentation"
>;

function fmtShift(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  const abs = Math.abs(v);
  const body = abs >= 100 ? Math.round(v).toLocaleString("ko-KR") : abs >= 1 ? v.toFixed(1) : v.toFixed(2);
  return body;
}

function AugmentationCompare({ data }: { data: RegressionResultData["augmentation"] }) {
  if (!data) return null;
  const mapeLabel = data.metric_basis === "cv" ? "검증 MAPE" : "학습 MAPE";
  return (
    <div className="rounded border border-indigo-300 dark:border-indigo-400/60 bg-indigo-50/80 dark:bg-indigo-950/40 px-2.5 py-2 space-y-1.5">
      <p className="text-xs font-semibold text-indigo-950 dark:text-indigo-100">인근 단지 추가 전후</p>
      <p className="text-[11px] leading-snug text-slate-700 dark:text-slate-200">
        기준 단지 {data.subject_n.toLocaleString("ko-KR")}건 · 더한 거래{" "}
        {data.added_n.toLocaleString("ko-KR")}건. {mapeLabel}는 기준 단지 거래만 사용합니다.
      </p>
      <p className="text-[11px] text-slate-800 dark:text-slate-100">
        {mapeLabel} {data.mape_before != null ? `${fmtDecimal(data.mape_before, 1)}%` : "—"} →{" "}
        {data.mape_after != null ? `${fmtDecimal(data.mape_after, 1)}%` : "—"}
      </p>
      {data.slopes.length > 0 && (
        <div className="table-wrap overflow-auto">
          <table className="data w-full text-[11px] border-collapse">
            <thead>
              <tr className="text-slate-600 dark:text-slate-300">
                <th className="text-left font-medium py-1">변수</th>
                <th className="text-center font-medium py-1">이전 계수</th>
                <th className="text-center font-medium py-1">이전 SE</th>
                <th className="text-center font-medium py-1">이후 계수</th>
                <th className="text-center font-medium py-1">이후 SE</th>
              </tr>
            </thead>
            <tbody>
              {data.slopes.map((s) => (
                <tr key={s.name}>
                  <td>{shortDisplayLabel(s.label)}</td>
                  <td className="text-center tabular-nums">{fmtShift(s.coef_before)}</td>
                  <td className="text-center tabular-nums">{fmtShift(s.se_before)}</td>
                  <td className="text-center tabular-nums">{fmtShift(s.coef_after)}</td>
                  <td className="text-center tabular-nums">{fmtShift(s.se_after)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data.note && <p className="text-[10px] leading-snug text-slate-500 dark:text-slate-400">{data.note}</p>}
    </div>
  );
}

function ReferenceCategories({
  options,
}: {
  options?: CollectivePredictOptions | CommercialPredictOptions | null;
}) {
  if (!options) return null;
  const refs: Array<[string, string]> = [];
  const dongOpts = "dong_options" in options ? options.dong_options : undefined;
  if (dongOpts && dongOpts.length > 0) {
    const dongRefs = dongOpts.filter((o) => o.is_reference).map((o) => o.label);
    if (dongRefs.length) refs.push(["동", dongRefs.join(", ")]);
  } else if ("dong_reference" in options && options.dong_reference) {
    refs.push(["동", options.dong_reference]);
  }
  if ("housing_subtype_reference" in options && options.housing_subtype_reference) {
    refs.push(["권리/주택유형", options.housing_subtype_reference]);
  }
  if ("structure_reference" in options && options.structure_reference) {
    refs.push(["구조", options.structure_reference]);
  }
  if ("asset_type_reference" in options && options.asset_type_reference) {
    refs.push(["유형", options.asset_type_reference]);
  }
  if ("zone_type_reference" in options && options.zone_type_reference) {
    refs.push(["용도지역", options.zone_type_reference]);
  }
  if ("building_use_reference" in options && options.building_use_reference) {
    refs.push(["건축물용도", options.building_use_reference]);
  }
  if ("road_width_reference" in options && options.road_width_reference) {
    refs.push(["도로조건", options.road_width_reference]);
  }
  const buildingReference =
    "buildings" in options
      ? options.buildings?.find((b) => b.is_reference)?.display_name
      : undefined;
  if (buildingReference) refs.push(["단지", buildingReference]);
  const floorReference = "floor_reference_label" in options ? options.floor_reference_label : undefined;
  if (floorReference) refs.push(["층", floorReference]);
  if (refs.length === 0) return null;
  return (
    <div className="space-y-0.5">
      <p className="text-xs leading-relaxed text-slate-500 dark:text-slate-400">
        기준 범주: {refs.map(([label, value]) => `${label}=${value}`).join(" · ")}
      </p>
      {floorReference && (
        <p className="text-xs leading-relaxed text-slate-500 dark:text-slate-400">
          층 계수는 {floorReference} 대비입니다. 효용지수 100과는 다른 기준입니다.
        </p>
      )}
    </div>
  );
}

export function CollectiveRegressionResults({
  data,
  modelType,
  logNote,
}: {
  data: RegressionResultData;
  modelType: RegressionModelType;
  logNote?: string;
}) {
  const fitModel = data.model_type ?? modelType;
  const sigCount = data.significant_count ?? countSignificantCoefficients(data.coefficients);

  const metrics = [
    { label: fitModel === "log" ? "결정계수 R² (로그)" : "결정계수 R²", term: "r_squared", value: fmtDecimal(data.r_squared, 3) },
    { label: fitModel === "log" ? "조정 R² (로그)" : "조정 R²", term: "adj_r_squared", value: fmtDecimal(data.adj_r_squared, 3) },
    { label: "학습 MAPE", term: "mape", value: data.in_sample_mape != null ? `${fmtDecimal(data.in_sample_mape, 2)}%` : "—" },
    { label: "CV-MAPE", term: "cv_mape", value: data.cv_mape != null ? `${fmtDecimal(data.cv_mape, 2)}%` : "—" },
  ];
  const coefficientHelp = {
    spec_id: "collective.regression.coefficients", spec_version: "1", title: "회귀계수와 해석",
    summary: "다른 조건이 같을 때 각 변수가 거래금액과 어떤 관계를 보이는지 확인합니다.",
    interpretation: ["회귀식은 절편과 p<0.1인 항을 표시합니다. 전체보기를 누르면 유의하지 않은 항도 확인할 수 있습니다. 추정금액은 전체 적합 모형으로 계산합니다.", "범주형 변수는 회귀식 아래의 기준 범주와 비교합니다. 거래시점과 단지 차이에 관한 항은 기존 분석 방식대로 유지합니다.", ...(fitModel === "log" && logNote ? [logNote] : [])],
    limitations: ["통계적 관계는 인과관계나 개별 물건의 적정가격을 의미하지 않습니다."],
  };
  const cvHelp = {
    spec_id: "collective.regression.cv", spec_version: "1", title: "CV-MAPE와 검증 범위",
    summary: "거래자료를 나누어 학습과 평가를 반복한 교차검증 오차입니다.",
    interpretation: ["금액의 원래 단위에서 계산한 5겹 교차검증 오차입니다. 학습 MAPE와 구분해 읽어 주세요."],
    limitations: ["표본이 부족하거나 전체 검증을 완료하지 못하면 값을 제공하지 않습니다. 산출되지 않은 값은 —로 표시합니다."],
  };
  const caution = primaryCaution(data.analysis);
  const warnings = [...new Set(data.warnings)].filter(w => w !== caution);
  return (
    <div className="card space-y-4 mt-3" data-collective-regression-result>
      <section className="space-y-3" aria-label="결과 요약">
        <div className="flex flex-wrap justify-between items-center gap-2">
          <h3 className="text-sm font-semibold">결과 요약</h3>
          <div className="flex items-center gap-1 text-sm font-medium">적합 거래 {data.n.toLocaleString("ko-KR")}건 <StatsGlossaryHelp termId="fit_n" size="xs" /></div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {metrics.map(metric => <div key={metric.term} className="rounded-lg border border-slate-200 bg-slate-50/60 px-3 py-3 dark:border-slate-700 dark:bg-slate-900/40">
            <div className="flex items-center gap-1 text-xs text-slate-600 dark:text-slate-300">
              {metric.label}
              {metric.term === "cv_mape" ? <AnalysisHelpPanel explain={cvHelp} /> : <StatsGlossaryHelp termId={metric.term} size="xs" />}
            </div>
            <p className="mt-2 text-xl font-semibold tabular-nums text-slate-900 dark:text-slate-100">{metric.value}</p>
          </div>)}
        </div>
        <ValidationStatus report={data.analysis?.metrics.find(metric => metric.role !== "training")?.validation} />
        {(caution || warnings.length > 0) && <div role="status" className="border-l-2 border-amber-500 pl-3 space-y-1 text-xs leading-relaxed text-amber-800 dark:text-amber-200">
          {caution && <p>{caution}</p>}{warnings.map(w => <p key={w}>{w}</p>)}
        </div>}
        {(data.equation || data.coefficients.length > 0) && <section className="space-y-2" aria-label="회귀식" >
          <div className="flex items-center gap-2 text-sm font-semibold">회귀식 <AnalysisHelpPanel explain={coefficientHelp} /></div>
          <CollectiveRegressionEquation coefficients={data.coefficients} modelType={fitModel} equation={data.equation} timeReference={data.time_reference} prominent />
          <ReferenceCategories options={data.predict_options} />
        </section>}
      </section>
      <DetailAnalysis>
        {data.coefficients.length > 0 && <section className="space-y-2" aria-label="회귀계수 상세">
          <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
            <h4 className="text-sm font-semibold">회귀계수</h4>
            <span className="flex items-center gap-1 text-xs text-slate-600 dark:text-slate-300">유의 계수 {sigCount}개 <AnalysisHelpPanel explain={coefficientHelp} /></span>
          </div>
          <EffectsTable coefficients={data.coefficients} />
        </section>}
        <details className="text-xs">
          <summary className="cursor-pointer py-1 font-medium text-slate-600 dark:text-slate-300">분석에 사용한 자료와 표본</summary>
          <div className="mt-2 space-y-3">
            {data.missing_treatment_label && <p>{data.missing_treatment_label}</p>}
            <AnalysisSummary analysis={data.analysis} />
          </div>
        </details>
        {data.augmentation && <details className="text-xs">
          <summary className="cursor-pointer py-1 font-medium">인근 단지 추가 전후</summary>
          <div className="mt-2"><AugmentationCompare data={data.augmentation} /></div>
        </details>}
        <details className="text-xs text-slate-600 dark:text-slate-300">
          <summary className="cursor-pointer py-1">추가 통계정보와 해석</summary>
          <p className="my-2">F 검정 p값: {formatProbability(data.f_p_value)} <StatsGlossaryHelp termId="f_p_value" size="xs" /></p>
          <ZoneCaution />
        </details>
      </DetailAnalysis>
    </div>
  );
}
