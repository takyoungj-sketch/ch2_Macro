import clsx from "clsx";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import type { AssetType, PredictOptions, RegressionCoeff, ResponseScale } from "../types";
import {
  dummyReferenceRows,
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
  predictOptions,
}: {
  coefficients: RegressionCoeff[];
  responseScale: ResponseScale;
  assetType: AssetType;
  predictOptions?: PredictOptions | null;
}) {
  const sorted = sortCoefficientsByVariableOrder(coefficients);
  const refs = dummyReferenceRows(predictOptions, assetType);

  const renderRow = (c: RegressionCoeff) => {
    const sig = isEquationSignificant(c.p_value);
    return (
      <tr key={c.name} className={clsx(sig && sigRowClass)}>
        <td>{shortCoefName(c.name, assetType)}</td>
        <td>{interpretCoefficient(c, responseScale, assetType, predictOptions)}</td>
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
          {sorted.map(renderRow)}
          {refs.map((r) => (
            <tr key={r.key} className="bg-slate-50 dark:bg-slate-800/40 text-slate-600 dark:text-slate-300">
              <td>
                {r.label}
                <span className="ml-1 text-[10px] text-indigo-700 dark:text-indigo-300">기준</span>
              </td>
              <td>더미에 넣지 않습니다. 다른 {r.kind} 계수는 이 값 대비입니다.</td>
              <td className="text-right tabular-nums">—</td>
              <td className="text-right tabular-nums">—</td>
              <td className="text-right tabular-nums">—</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
