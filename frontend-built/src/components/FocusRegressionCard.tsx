import clsx from "clsx";
import type { AssetType, RegressionLevelResult, ResponseScale } from "../types";
import {
  ADMIN_LABELS,
  formatCoefName,
  fmtDecimal,
  fmtNum,
  levelCardTitle,
} from "../utils/regressionFormat";
import RegressionEquation from "./RegressionEquation";
import RegressionEffectsTable from "./RegressionEffectsTable";

type Props = {
  result: RegressionLevelResult;
  assetType: AssetType;
  responseScale: ResponseScale;
};

export default function FocusRegressionCard({ result, assetType, responseScale }: Props) {
  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="font-semibold text-base">
            {levelCardTitle(result.scope_label, result.admin_level)}
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {ADMIN_LABELS[result.admin_level] ?? result.admin_level} · 분석 초점
          </p>
        </div>
        <span className="text-xs text-slate-500">n={fmtNum(result.n)}</span>
      </div>

      {result.warning && <p className="text-xs badge-warn">{result.warning}</p>}

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
        <div>R² {fmtDecimal(result.r_squared, 5)}</div>
        <div>Adj R² {fmtDecimal(result.adj_r_squared, 5)}</div>
        <div title="in-sample · 금액(만원) 원척도">
          MAPE {result.mape != null ? `${fmtDecimal(result.mape, 2)}%` : "—"}
        </div>
        <div>유의 변수 {result.significant_count}개</div>
        <div>F p {fmtDecimal(result.f_p_value, 5)}</div>
      </div>

      {(result.equation || result.coefficients.length > 0) && (
        <div className="space-y-1">
          <div className="text-xs font-semibold text-slate-600">회귀식</div>
          <RegressionEquation
            coefficients={result.coefficients}
            responseScale={responseScale}
            assetType={assetType}
            equation={result.equation}
            predictOptions={result.predict_options}
          />
        </div>
      )}

      {result.coefficients.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-slate-600 dark:text-slate-400 font-medium">계수 상세</summary>
          <RegressionEffectsTable
            coefficients={result.coefficients}
            responseScale={responseScale}
            assetType={assetType}
          />
        </details>
      )}

      {(result.vif?.length ?? 0) > 0 && (
        <div className="text-xs space-y-1">
          <div className="font-semibold text-slate-600">다중공선성 (VIF · 연속변수)</div>
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            {result.vif!.map((v) => (
              <span
                key={v.name}
                className={clsx(
                  v.vif != null && v.vif >= 10 && "text-red-600 font-medium",
                  v.vif != null && v.vif >= 5 && v.vif < 10 && "text-amber-700",
                )}
              >
                {formatCoefName(v.name, assetType)} {v.vif != null ? fmtDecimal(v.vif, 2) : "—"}
              </span>
            ))}
          </div>
          <p className="text-slate-400">VIF≥10 주의 · ≥5 참고</p>
        </div>
      )}
    </div>
  );
}
