import { useMemo, useState } from "react";
import clsx from "clsx";
import { formatProbability, formatStatistic } from "../../../shared/regression-ui/format";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import type { LandRegressionCoeff } from "../types";
import {
  interpretLandCoefficient,
  isEquationSignificant,
  shortDisplayLabel,
  sigRowClass,
  sortCoefficientsByVariableOrder,
} from "../utils/landRegressionFormat";

export default function LandRegressionEffectsTable({
  coefficients,
  modelType,
}: {
  coefficients: LandRegressionCoeff[];
  modelType: "log" | "linear";
}) {
  const [feOpen, setFeOpen] = useState(false);
  const intercept = coefficients.find((c) => c.name === "const");
  const main = useMemo(
    () =>
      sortCoefficientsByVariableOrder(
        coefficients.filter((c) => c.name !== "const" && !c.name.startsWith("beop_")),
      ),
    [coefficients],
  );
  const fe = useMemo(
    () => sortCoefficientsByVariableOrder(coefficients.filter((c) => c.name.startsWith("beop_"))),
    [coefficients],
  );

  const renderRow = (c: LandRegressionCoeff) => {
    const sig = isEquationSignificant(c.p);
    return (
      <tr key={c.name} className={clsx(sig && sigRowClass)}>
        <td className="border border-slate-200 dark:border-slate-700 px-2 py-1 text-left whitespace-nowrap">
          {shortDisplayLabel(c.label)}
        </td>
        <td className="border border-slate-200 dark:border-slate-700 px-2 py-1 text-center tabular-nums">{formatStatistic(c.coef, 4)}</td>
        <td className="border border-slate-200 dark:border-slate-700 px-2 py-1">{interpretLandCoefficient(c, modelType)}</td>
        <td className="border border-slate-200 dark:border-slate-700 px-2 py-1 text-center tabular-nums text-slate-600 dark:text-slate-300">
          {formatStatistic(c.se)}
        </td>
        <td className="border border-slate-200 dark:border-slate-700 px-2 py-1 text-center tabular-nums text-slate-600 dark:text-slate-300">
          {formatStatistic(c.t)}
        </td>
        <td className="border border-slate-200 dark:border-slate-700 px-2 py-1 text-center tabular-nums">
          {formatProbability(c.p)}
        </td>
      </tr>
    );
  };

  return (
    <div tabIndex={0} role="region" aria-label="회귀 계수 상세 표" className="max-h-96 mt-2 overflow-auto rounded-lg border border-slate-100">
      <table className="w-full text-sm border-collapse min-w-[520px]">
        <thead className="sticky top-0 z-10">
          <tr className="bg-slate-50 dark:bg-slate-900 text-slate-600 dark:text-slate-300">
            <th className="border border-slate-200 dark:border-slate-700 px-2 py-1.5 text-left font-medium">변수</th>
            <th className="border border-slate-200 dark:border-slate-700 px-2 py-1.5 text-center font-medium">β</th>
            <th className="border border-slate-200 dark:border-slate-700 px-2 py-1.5 text-left font-medium">
              <span className="inline-flex items-center gap-0.5">
                효과 해석
                <StatsGlossaryHelp termId="coefficient" size="xs" />
              </span>
            </th>
            <th className="border border-slate-200 dark:border-slate-700 px-2 py-1.5 text-center font-medium">
              <span className="inline-flex items-center justify-center gap-0.5">
                SE
                <StatsGlossaryHelp termId="se" size="xs" />
              </span>
            </th>
            <th className="border border-slate-200 dark:border-slate-700 px-2 py-1.5 text-center font-medium">t</th>
            <th className="border border-slate-200 dark:border-slate-700 px-2 py-1.5 text-center font-medium">
              <span className="inline-flex items-center justify-center gap-0.5">
                p
                <StatsGlossaryHelp termId="p_value" size="xs" />
              </span>
            </th>
          </tr>
        </thead>
        <tbody className="text-slate-800 dark:text-slate-100">
          {main.map(renderRow)}
          {fe.length > 0 && (
            <>
              <tr className="bg-slate-50/80 dark:bg-slate-900/60">
                <td colSpan={6} className="border border-slate-200 dark:border-slate-700 px-2 py-1">
                  <button
                    type="button"
                    className="text-[11px] font-medium text-indigo-700 dark:text-indigo-300"
                    onClick={() => setFeOpen((v) => !v)}
                  >
                    법정동 고정효과 ({fe.length}개) {feOpen ? "▲" : "▼"}
                  </button>
                </td>
              </tr>
              {feOpen && fe.map(renderRow)}
            </>
          )}
        </tbody>
      </table>
      {intercept && <details className="p-2 text-xs text-slate-600 dark:text-slate-300">
        <summary className="cursor-pointer">절편의 상세 통계</summary>
        <table className="mt-2 w-full text-sm" aria-label="절편의 상세 통계"><thead><tr><th className="text-left">변수</th><th className="text-center">β</th><th className="text-left">효과 해석</th><th className="text-center">SE</th><th className="text-center">t</th><th className="text-center">p</th></tr></thead><tbody>{renderRow(intercept)}</tbody></table>
      </details>}
    </div>
  );
}
