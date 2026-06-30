import type { LandRegressionResponse } from "../types";
import {
  countSignificantCoefficients,
  fmtDecimal,
} from "../utils/landRegressionFormat";
import LandRegressionEquation from "./LandRegressionEquation";
import LandRegressionEffectsTable from "./LandRegressionEffectsTable";

export default function LandRegressionResults({ data }: { data: LandRegressionResponse }) {
  const sigCount = data.significant_count ?? countSignificantCoefficients(data.coefficients);
  const modelLabel = data.model_type === "log" ? "log(단가)" : "단가(선형)";

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-3">
      {data.warnings.map((w) => (
        <p key={w} className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1">
          {w}
        </p>
      ))}

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs text-slate-700">
        <div>R² {fmtDecimal(data.r_squared, 5)}</div>
        <div>Adj R² {fmtDecimal(data.adj_r_squared, 5)}</div>
        <div>유의 변수 {sigCount}개</div>
        {data.f_p_value != null && <div>F p {fmtDecimal(data.f_p_value, 5)}</div>}
        <div>모델 {modelLabel}</div>
        <div>n={data.n.toLocaleString("ko-KR")}</div>
      </div>

      {Object.keys(data.reference_categories).length > 0 && (
        <p className="text-[10px] text-slate-500">
          기준 범주:{" "}
          {Object.entries(data.reference_categories)
            .map(([k, v]) => `${k}=${v}`)
            .join(" · ")}
        </p>
      )}

      {data.coefficients.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs font-semibold text-slate-600">회귀식</div>
          <LandRegressionEquation coefficients={data.coefficients} modelType={data.model_type} />
        </div>
      )}

      {data.coefficients.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-slate-600 font-medium">계수 상세</summary>
          <LandRegressionEffectsTable coefficients={data.coefficients} modelType={data.model_type} />
        </details>
      )}
    </div>
  );
}
