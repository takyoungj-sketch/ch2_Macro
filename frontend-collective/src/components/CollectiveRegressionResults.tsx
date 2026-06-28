import { useMemo, useState } from "react";
import clsx from "clsx";
import type { CollectiveRegressionResponse, RegressionCoeff, RegressionModelType } from "../types";
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
>;

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

      {(data.equation || data.coefficients.length > 0) && (
        <div className="space-y-1">
          <div className="text-xs font-semibold text-slate-600 dark:text-slate-300">회귀식</div>
          <CollectiveRegressionEquation
            coefficients={data.coefficients}
            modelType={fitModel}
            equation={data.equation}
          />
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
