import { useMemo, useState } from "react";
import clsx from "clsx";
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
            <th className="text-left font-medium py-1">계수</th>
            <th className="text-right font-medium py-1">SE</th>
            <th className="text-right font-medium py-1">t</th>
            <th className="text-right font-medium py-1">p</th>
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
  if ("dong_reference" in options && options.dong_reference) {
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
        <div>R² {fmtDecimal(data.r_squared, 5)}</div>
        <div>Adj R² {fmtDecimal(data.adj_r_squared, 5)}</div>
        <div title="in-sample · 금액(만원) 원척도">
          MAPE {data.mape != null ? `${fmtDecimal(data.mape, 2)}%` : "—"}
        </div>
        <div>유의 변수 {sigCount}개</div>
        <div>F p {fmtDecimal(data.f_p_value, 5)}</div>
        <div>n={data.n.toLocaleString("ko-KR")}</div>
      </div>

      {data.model_candidates && data.model_candidates.length > 0 && (
        <details open className="rounded border border-indigo-200 bg-indigo-50/40 dark:border-indigo-800 dark:bg-indigo-950/20 p-2">
          <summary className="cursor-pointer text-xs font-semibold text-indigo-800 dark:text-indigo-200">
            모형 추천 후보 ({data.model_candidates.length}개)
          </summary>
          <div className="mt-2 space-y-1 text-[11px]">
            {data.model_candidates.map((candidate) => (
              <div key={candidate.rank} className="rounded bg-white/80 dark:bg-slate-900/60 px-2 py-1">
                #{candidate.rank} · {candidate.blocks.join(" + ")} · {candidate.model_type}
                {" · "}Adj R² {fmtDecimal(candidate.adj_r_squared, 3)}
                {" · "}CV-MAPE {candidate.cv_mape != null ? `${fmtDecimal(candidate.cv_mape, 2)}%` : "—"}
              </div>
            ))}
          </div>
        </details>
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
