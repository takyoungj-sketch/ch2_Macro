import clsx from "clsx";
import { MetricWithHelp, StatsGlossaryHelp } from "@ch2/stats-glossary";
import type { AssetType, RegressionLevelResult, ResponseScale } from "../types";
import { formatPartialNNote } from "../utils/recommendationLabels";
import {
  ADMIN_LABELS,
  formatCoefName,
  fmtDecimal,
  fmtNum,
  levelCardTitle,
} from "../utils/regressionFormat";
import RegressionEquation from "./RegressionEquation";
import ZoneCaution from "./ZoneCaution";
import RegressionEffectsTable from "./RegressionEffectsTable";
import SampleFunnel from "./SampleFunnel";

type Props = {
  result: RegressionLevelResult;
  assetType: AssetType;
  responseScale: ResponseScale;
  includePartial?: boolean;
  partialTxCount?: number | null;
  partialNNote?: string | null;
};

export default function FocusRegressionCard({
  result,
  assetType,
  responseScale,
  includePartial = false,
  partialTxCount,
  partialNNote,
}: Props) {
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
        <MetricWithHelp
          label="적합 n="
          termId="fit_n"
          value={fmtNum(result.n)}
          title="선택 변수 complete-case 표본 (fit_n)"
        />
      </div>
      {(partialNNote || partialTxCount != null) && (
        <p className="text-[11px] text-slate-500">
          {partialNNote || formatPartialNNote(includePartial, partialTxCount)}
        </p>
      )}

      {result.sample && <SampleFunnel sample={result.sample} />}

      {result.warning && <p className="text-xs badge-warn">{result.warning}</p>}

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
        <MetricWithHelp label="R²" termId="r_squared" value={fmtDecimal(result.r_squared, 5)} />
        <MetricWithHelp label="Adj R²" termId="adj_r_squared" value={fmtDecimal(result.adj_r_squared, 5)} />
        <div className="flex flex-wrap items-center gap-1.5" title="학습 표본에서 계산한 오차. 같은 행으로 맞추고 같은 행으로 채점합니다.">
          <MetricWithHelp
            label="학습 MAPE"
            termId="mape"
            value={result.mape != null ? `${fmtDecimal(result.mape, 2)}%` : "—"}
          />
        </div>
        {(result.cv_mape != null || result.confirm_cv_note) && (
          <div className="flex flex-wrap items-center gap-1.5" title="과거 연도로 학습하고 다음 연도를 맞춘 오차. 모형 추천의 CV-MAPE와 같은 계산입니다.">
            <MetricWithHelp
              label="CV-MAPE"
              termId="cv_mape"
              value={result.cv_mape != null ? `${fmtDecimal(result.cv_mape, 2)}%` : "—"}
            />
          </div>
        )}
        <div>유의 변수 {result.significant_count}개</div>
        {result.missing_treatment_label && (
          <div className="col-span-2 sm:col-span-3 text-slate-500">{result.missing_treatment_label}</div>
        )}
        <MetricWithHelp label="F p" termId="f_p_value" value={fmtDecimal(result.f_p_value, 5)} />
      </div>
      {(result.cv_mape != null || result.confirm_cv_note) && (
        <p className="text-[11px] leading-snug text-slate-500">
          {result.cv_mape != null
            ? "CV-MAPE는 이 식의 행으로 다음 연도를 맞춘 오차입니다. 모형 추천과 같은 계산이고, 행이 다르면 숫자가 달라집니다."
            : result.confirm_cv_note}
          {result.cv_mape != null && result.confirm_cv_mape != null && (
            <>
              {" "}
              마지막 연도 확인 {fmtDecimal(result.confirm_cv_mape, 2)}%.
            </>
          )}
          {result.cv_mape != null && result.confirm_cv_note && result.confirm_cv_mape == null && (
            <> {result.confirm_cv_note}</>
          )}
        </p>
      )}

      {(result.equation || result.coefficients.length > 0) && (
        <div className="space-y-1">
          <div className="flex items-center gap-1 text-xs font-semibold text-slate-600">
            회귀식
            <StatsGlossaryHelp termId="coefficient" size="xs" />
          </div>
          <RegressionEquation
            coefficients={result.coefficients}
            responseScale={responseScale}
            assetType={assetType}
            equation={result.equation}
            predictOptions={result.predict_options}
          />
          {result.warning?.includes("참고용") && (
            <p className="text-[11px] leading-snug text-slate-600 dark:text-slate-300">
              표본 수가 권장 기준에 미달하므로 회귀계수가 불안정할 수 있습니다. R²와 MAPE는 해당
              표본의 적합 결과이며, 새로운 거래에 대한 예측 정확도를 보장하지 않습니다.
            </p>
          )}
        </div>
      )}

      {result.coefficients.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-slate-600 dark:text-slate-400 font-medium">계수 상세</summary>
          <RegressionEffectsTable
            coefficients={result.coefficients}
            responseScale={responseScale}
            assetType={assetType}
            predictOptions={result.predict_options}
          />
        </details>
      )}
      <ZoneCaution />

      {(result.vif?.length ?? 0) > 0 && (
        <div className="text-xs space-y-1">
          <div className="flex items-center gap-1 font-semibold text-slate-600">
            다중공선성 (VIF · 연속변수)
            <StatsGlossaryHelp termId="vif" size="xs" />
          </div>
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
