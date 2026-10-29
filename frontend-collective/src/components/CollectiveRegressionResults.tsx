import { useMemo, useState } from "react";
import AnalysisSummary, { primaryCaution } from "../../../shared/regression-ui/AnalysisSummary";
import { DetailAnalysis, SummaryHeading } from "../../../shared/regression-ui/ReadingLayout";
import ValidationStatus from "../../../shared/regression-ui/ValidationStatus";
import { formatProbability, formatStatistic } from "../../../shared/regression-ui/format";
import clsx from "clsx";
import { MetricWithHelp, StatsGlossaryHelp } from "@ch2/stats-glossary";
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
        <td className="text-right tabular-nums">{formatStatistic(c.coef, 4)}</td>
        <td>{c.effect_plain ?? "—"}</td>
        <td className="text-right tabular-nums">{formatStatistic(c.se)}</td>
        <td className="text-right tabular-nums">{formatStatistic(c.t)}</td>
        <td className="text-right tabular-nums">{formatProbability(c.p)}</td>
      </tr>
    );
  };

  return (
    <div tabIndex={0} role="region" aria-label="회귀 계수 상세 표" className="table-wrap max-h-48 mt-2 overflow-auto">
      <table className="data w-full text-xs border-collapse">
        <thead>
          <tr className="text-slate-600 dark:text-slate-300">
            <th className="text-left font-medium py-1">변수</th>
            <th className="text-right font-medium py-1">β</th>
            <th className="text-left font-medium py-1">
              <span className="inline-flex items-center gap-0.5">
                효과 해석
                <StatsGlossaryHelp termId="coefficient" size="xs" />
              </span>
            </th>
            <th className="text-right font-medium py-1">
              <span className="inline-flex items-center justify-end gap-0.5">
                SE
                <StatsGlossaryHelp termId="se" size="xs" />
              </span>
            </th>
            <th className="text-right font-medium py-1">t</th>
            <th className="text-right font-medium py-1">
              <span className="inline-flex items-center justify-end gap-0.5">
                p
                <StatsGlossaryHelp termId="p_value" size="xs" />
              </span>
            </th>
          </tr>
        </thead>
        <tbody className="text-slate-800 dark:text-slate-200">
          {intercept && renderRow(intercept)}
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
                <th className="text-right font-medium py-1">이전 계수</th>
                <th className="text-right font-medium py-1">이전 SE</th>
                <th className="text-right font-medium py-1">이후 계수</th>
                <th className="text-right font-medium py-1">이후 SE</th>
              </tr>
            </thead>
            <tbody>
              {data.slopes.map((s) => (
                <tr key={s.name}>
                  <td>{shortDisplayLabel(s.label)}</td>
                  <td className="text-right tabular-nums">{fmtShift(s.coef_before)}</td>
                  <td className="text-right tabular-nums">{fmtShift(s.se_before)}</td>
                  <td className="text-right tabular-nums">{fmtShift(s.coef_after)}</td>
                  <td className="text-right tabular-nums">{fmtShift(s.se_after)}</td>
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
  if (buildingReference) refs.push(["단지 FE", buildingReference]);
  if (refs.length === 0) return null;
  return (
    <p className="text-[10px] text-slate-500 dark:text-slate-400">
      기준 범주: {refs.map(([label, value]) => `${label}=${value}`).join(" · ")}
    </p>
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

  return (
    <div className="card space-y-3 mt-3">
      <section className="space-y-2" aria-label="결과 요약">
        <SummaryHeading />
        {data.warnings.map((w) => (
          <p key={w} className="text-xs text-amber-700 dark:text-amber-300">
            {w}
          </p>
        ))}
        {primaryCaution(data.analysis) && (
          <p className="text-[11px] leading-snug text-amber-800 dark:text-amber-300">{primaryCaution(data.analysis)}</p>
        )}

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs text-slate-700 dark:text-slate-200">
        <MetricWithHelp label={fitModel === "log" ? "R² (로그)" : "R²"} termId="r_squared" value={fmtDecimal(data.r_squared, 5)} />
        <MetricWithHelp label={fitModel === "log" ? "Adj R² (로그)" : "Adj R²"} termId="adj_r_squared" value={fmtDecimal(data.adj_r_squared, 5)} />
        <div title="학습에 사용한 거래에서 계산한 금액 원척도 오차입니다.">
          <MetricWithHelp
            label="학습 MAPE"
            termId="mape"
            value={data.in_sample_mape != null ? `${fmtDecimal(data.in_sample_mape, 2)}%` : "—"}
          />
        </div>
        <div title="금액 원척도에서 계산한 5겹 교차검증 오차입니다. 표본이 부족하거나 전체 검증을 완료하지 못하면 제공하지 않습니다.">
          <MetricWithHelp label="5겹 교차검증 MAPE" termId="cv_mape"
            value={data.cv_mape != null ? `${fmtDecimal(data.cv_mape, 2)}%` : "— · 미제공"} />
        </div>
        <div>유의 계수 {sigCount}개 (p&lt;0.1, 절편 제외)</div>
        <MetricWithHelp label="F p" termId="f_p_value" value={formatProbability(data.f_p_value)} />
        <MetricWithHelp label="n=" termId="fit_n" value={data.n.toLocaleString("ko-KR")} />
      </div>
      <ValidationStatus report={data.analysis?.metrics.find(metric => metric.role !== "training")?.validation} />
      {data.missing_treatment_label && (
        <p className="text-[11px] text-slate-500">{data.missing_treatment_label}</p>
      )}
      </section>

      <DetailAnalysis>
      <AnalysisSummary analysis={data.analysis} />
      <AugmentationCompare data={data.augmentation} />

      {(data.equation || data.coefficients.length > 0) && (
        <div className="space-y-1">
          <div className="text-xs font-semibold text-slate-600 dark:text-slate-300">회귀식과 계수</div>
          <CollectiveRegressionEquation
            coefficients={data.coefficients}
            modelType={fitModel}
            equation={data.equation}
            timeReference={data.time_reference}
          />
          {fitModel === "log" && logNote && (
            <p className="text-[11px] leading-snug text-slate-500">{logNote}</p>
          )}
          <ReferenceCategories options={data.predict_options} />
        </div>
      )}

      {data.coefficients.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-slate-600 dark:text-slate-400 font-medium">계수 상세</summary>
          <EffectsTable coefficients={data.coefficients} />
        </details>
      )}
      <ZoneCaution />
      </DetailAnalysis>
    </div>
  );
}
