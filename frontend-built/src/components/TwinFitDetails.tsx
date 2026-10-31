import type { AssetType, RegressionLevelResult, ResponseScale } from "../types";
import { BasicRegressionCoefficients, BasicRegressionEquation } from "./BasicRegressionDetails";

export default function TwinFitDetails({ result, scale, assetType }: { result: RegressionLevelResult; scale: ResponseScale; assetType: AssetType }) {
  return <section className="space-y-3 text-sm">
    <BasicRegressionEquation coefficients={result.coefficients} responseScale={scale} assetType={assetType} predictOptions={result.predict_options} equation={result.equation} />
    <details className="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
      <summary className="cursor-pointer font-semibold">회귀계수 상세</summary>
      <div className="mt-3">
        <BasicRegressionCoefficients coefficients={result.coefficients} responseScale={scale} assetType={assetType} predictOptions={result.predict_options} />
      </div>
    </details>
  </section>;
}
