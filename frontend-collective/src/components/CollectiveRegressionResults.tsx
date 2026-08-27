import { useMemo, useState } from "react";
import clsx from "clsx";
import { MetricWithHelp, StatsGlossaryHelp } from "@ch2/stats-glossary";
import { ModelRecommendSection } from "@ch2/model-recommend";
import type {
  CollectiveModelCandidate,
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
        <td>{c.effect_plain ?? "—"}</td>
        <td className="text-right tabular-nums">{c.se?.toFixed(2) ?? "—"}</td>
        <td className="text-right tabular-nums">{c.t?.toFixed(2) ?? "—"}</td>
        <td className="text-right tabular-nums">{fmtDecimal(c.p, 5)}</td>
      </tr>
    );
  };

  return (
    <div className="table-wrap max-h-48 mt-2 overflow-auto">
      <table className="data w-full text-xs border-collapse">
        <thead>
          <tr className="text-slate-600 dark:text-slate-300">
            <th className="text-left font-medium py-1">변수</th>
            <th className="text-left font-medium py-1">
              <span className="inline-flex items-center gap-0.5">
                계수
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
                <td colSpan={5} className="py-1">
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
    </div>
  );
}

type RegressionResultData = Pick<
  CollectiveRegressionResponse,
  | "warnings"
  | "model_type"
  | "n"
  | "r_squared"
  | "adj_r_squared"
  | "mape"
  | "f_p_value"
  | "significant_count"
  | "equation"
  | "coefficients"
  | "predict_options"
  | "model_candidates"
>;

function ReferenceCategories({
  options,
}: {
  options?: CollectivePredictOptions | CommercialPredictOptions | null;
}) {
  if (!options) return null;
  const refs: Array<[string, string]> = [];
  if ("dong_options" in options && (options.dong_options?.length ?? 0) > 0) {
    const dongRefs = options.dong_options.filter((o) => o.is_reference).map((o) => o.label);
    if (dongRefs.length) refs.push(["동", dongRefs.join(", ")]);
  } else if ("dong_reference" in options && options.dong_reference) {
    refs.push(["동", options.dong_reference]);
  }
  if ("housing_subtype_reference" in options && options.housing_subtype_reference) {
    refs.push(["권리/주택유형", options.housing_subtype_reference]);
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

function CollectiveModelRecommend({
  candidates,
  selectionN,
}: {
  candidates: CollectiveModelCandidate[];
  selectionN: number;
}) {
  const byAdj = [...candidates].sort(
    (a, b) => (b.adj_r_squared ?? -Infinity) - (a.adj_r_squared ?? -Infinity),
  );
  const byCv = [...candidates].sort((a, b) => {
    const av = a.cv_mape;
    const bv = b.cv_mape;
    if (av == null && bv == null) return a.rank - b.rank;
    if (av == null) return 1;
    if (bv == null) return -1;
    return av - bv;
  });

  const toRow = (c: CollectiveModelCandidate, prefix: string) => ({
    key: `${prefix}-${c.rank}-${c.blocks.join("+")}-${c.model_type}`,
    primary: `#${c.rank} · ${c.blocks.join(" + ")} · ${c.model_type}`,
    metrics: [
      `Adj R² ${fmtDecimal(c.adj_r_squared, 3)}`,
      c.cv_mape != null ? `CV-MAPE ${fmtDecimal(c.cv_mape, 2)}%` : "CV-MAPE —",
      c.mape != null ? `MAPE ${fmtDecimal(c.mape, 2)}%` : null,
      `n=${c.n.toLocaleString("ko-KR")}`,
    ]
      .filter(Boolean)
      .join(" · "),
  });

  return (
    <ModelRecommendSection
      depth="standard_plus"
      selectionN={selectionN}
      limitations="후보 비교(표준+) · Twin Validation 폐쇄 루프는 복합만 · 정답 식 아님 · 소표본 시 불안정"
      headerExtra={<StatsGlossaryHelp termId="adj_r_squared" size="xs" />}
      defaultTabId="explanatory"
      tabs={[
        {
          id: "explanatory",
          label: "설명형 (Adj R²)",
          optimizeSentence:
            "이 추천은 Adj R²를 기준으로 정렬한 설명형 후보입니다. 정답 식이 아닙니다.",
          rows: byAdj.map((c) => toRow(c, "adj")),
        },
        {
          id: "predictive",
          label: "예측형 (CV-MAPE)",
          optimizeSentence:
            "이 추천은 CV-MAPE(낮을수록 좋음) 기준 예측형 후보입니다. Twin pool 검증은 복합과 깊이가 다릅니다.",
          rows: byCv.map((c) => toRow(c, "cv")),
        },
      ]}
    />
  );
}

export function CollectiveRegressionResults({
  data,
  modelType,
}: {
  data: RegressionResultData;
  modelType: RegressionModelType;
}) {
  const fitModel = data.model_type ?? modelType;
  const sigCount = data.significant_count ?? countSignificantCoefficients(data.coefficients);

  return (
    <div className="card space-y-3 mt-3">
      {data.warnings.map((w) => (
        <p key={w} className="text-xs text-amber-700 dark:text-amber-300">
          {w}
        </p>
      ))}

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs text-slate-700 dark:text-slate-200">
        <MetricWithHelp label="R²" termId="r_squared" value={fmtDecimal(data.r_squared, 5)} />
        <MetricWithHelp label="Adj R²" termId="adj_r_squared" value={fmtDecimal(data.adj_r_squared, 5)} />
        <MetricWithHelp
          label="MAPE"
          termId="mape"
          value={data.mape != null ? `${fmtDecimal(data.mape, 2)}%` : "—"}
          title="in-sample · 금액(만원) 원척도"
        />
        <div>유의 변수 {sigCount}개</div>
        <MetricWithHelp label="F p" termId="f_p_value" value={fmtDecimal(data.f_p_value, 5)} />
        <MetricWithHelp label="n=" termId="fit_n" value={data.n.toLocaleString("ko-KR")} />
      </div>

      {data.model_candidates && data.model_candidates.length > 0 && (
        <CollectiveModelRecommend candidates={data.model_candidates} selectionN={data.n} />
      )}

      {(data.equation || data.coefficients.length > 0) && (
        <div className="space-y-1">
          <div className="text-xs font-semibold text-slate-600 dark:text-slate-300">회귀식</div>
          <CollectiveRegressionEquation
            coefficients={data.coefficients}
            modelType={fitModel}
            equation={data.equation}
          />
          <ReferenceCategories options={data.predict_options} />
        </div>
      )}

      {data.coefficients.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-slate-600 dark:text-slate-400 font-medium">계수 상세</summary>
          <EffectsTable coefficients={data.coefficients} />
        </details>
      )}
    </div>
  );
}
