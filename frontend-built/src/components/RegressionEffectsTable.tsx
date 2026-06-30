import clsx from "clsx";
import type { AssetType, RegressionCoeff, ResponseScale } from "../types";
import {
  fmtDecimal,
  interpretCoefficient,
  isEquationSignificant,
  shortCoefName,
  sigRowClass,
  sortCoefficientsByVariableOrder,
} from "../utils/regressionFormat";

export default function RegressionEffectsTable({
  coefficients,
  responseScale,
  assetType,
}: {
  coefficients: RegressionCoeff[];
  responseScale: ResponseScale;
  assetType: AssetType;
}) {
  const sorted = sortCoefficientsByVariableOrder(coefficients);

  const renderRow = (c: RegressionCoeff) => {
    const sig = isEquationSignificant(c.p_value);
    return (
      <tr key={c.name} className={clsx(sig && sigRowClass)}>
        <td>{shortCoefName(c.name, assetType)}</td>
        <td>{interpretCoefficient(c, responseScale, assetType)}</td>
        <td className="text-right tabular-nums">{c.std_err?.toFixed(2) ?? "—"}</td>
        <td className="text-right tabular-nums">{c.t_value?.toFixed(2) ?? "—"}</td>
        <td className="text-right tabular-nums">{fmtDecimal(c.p_value, 5)}</td>
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
        <tbody className="text-slate-800 dark:text-slate-200">{sorted.map(renderRow)}</tbody>
      </table>
    </div>
  );
}
