import type { LandRegressionResponse } from "../types";
import { MetricWithHelp, StatsGlossaryHelp } from "@ch2/stats-glossary";
import {
  countSignificantCoefficients,
  fmtDecimal,
} from "../utils/landRegressionFormat";
import LandRegressionEquation from "./LandRegressionEquation";
import LandRegressionEffectsTable from "./LandRegressionEffectsTable";
import ZoneCaution from "./ZoneCaution";

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
        <MetricWithHelp label="R²" termId="r_squared" value={fmtDecimal(data.r_squared, 5)} />
        <MetricWithHelp label="Adj R²" termId="adj_r_squared" value={fmtDecimal(data.adj_r_squared, 5)} />
        <div>유의 변수 {sigCount}개</div>
        {data.f_p_value != null && (
          <MetricWithHelp label="F p" termId="f_p_value" value={fmtDecimal(data.f_p_value, 5)} />
        )}
          <div className="flex items-center gap-1">
            모델 {modelLabel}
            <StatsGlossaryHelp termId="ols" size="xs" />
            <StatsGlossaryHelp termId="log_model" size="xs" />
          </div>
        <MetricWithHelp label="n=" termId="fit_n" value={data.n.toLocaleString("ko-KR")} />
      </div>
      {data.missing_treatment_label && (
        <p className="text-[11px] text-slate-500">{data.missing_treatment_label}</p>
      )}

      {data.coefficients.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs font-semibold text-slate-600">회귀식</div>
          <LandRegressionEquation coefficients={data.coefficients} modelType={data.model_type} />
          {data.warnings.some((w) => w.includes("참고용")) && (
            <p className="text-[11px] leading-snug text-slate-600 dark:text-slate-300">
              표본 수가 권장 기준에 미달하므로 회귀계수가 불안정할 수 있습니다. R²와 MAPE는 해당
              표본의 적합 결과이며, 새로운 거래에 대한 예측 정확도를 보장하지 않습니다.
            </p>
          )}
          {Object.keys(data.reference_categories).length > 0 && (
            <p className="text-[10px] text-slate-500 dark:text-slate-400">
              기준 범주:{" "}
              {Object.entries(data.reference_categories)
                .map(([k, v]) => `${k}=${v}`)
                .join(" · ")}
            </p>
          )}
        </div>
      )}

      {data.coefficients.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-slate-600 font-medium">계수 상세</summary>
          <LandRegressionEffectsTable coefficients={data.coefficients} modelType={data.model_type} />
        </details>
      )}
      <ZoneCaution />
    </div>
  );
}
