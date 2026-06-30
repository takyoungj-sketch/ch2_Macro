import { useMemo, useState } from "react";
import clsx from "clsx";
import type { LandRegressionCoeff } from "../types";
import {
  fmtDecimal,
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
        <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
          {shortDisplayLabel(c.label)}
        </td>
        <td className="border border-slate-200 px-2 py-1">{interpretLandCoefficient(c, modelType)}</td>
        <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-slate-600">
          {c.se.toFixed(2)}
        </td>
        <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-slate-600">
          {c.t.toFixed(2)}
        </td>
        <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
          {fmtDecimal(c.p, 5)}
        </td>
      </tr>
    );
  };

  return (
    <div className="max-h-48 mt-2 overflow-auto rounded-lg border border-slate-100">
      <table className="w-full text-[11px] border-collapse min-w-[520px]">
        <thead className="sticky top-0 z-10">
          <tr className="bg-slate-50 text-slate-600">
            <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">변수</th>
            <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">계수</th>
            <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">SE</th>
            <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">t</th>
            <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">p</th>
          </tr>
        </thead>
        <tbody className="text-slate-800">
          {intercept && renderRow(intercept)}
          {main.map(renderRow)}
          {fe.length > 0 && (
            <>
              <tr className="bg-slate-50/80">
                <td colSpan={5} className="border border-slate-200 px-2 py-1">
                  <button
                    type="button"
                    className="text-[11px] font-medium text-indigo-700"
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
    </div>
  );
}
