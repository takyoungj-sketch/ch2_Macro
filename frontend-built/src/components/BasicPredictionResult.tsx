import clsx from "clsx";
import { StatsGlossaryHelp } from "./StatsGlossaryHelp";
import type { RegressionPredictResponse } from "../types";

function amount(value?: number | null) {
  return value != null && Number.isFinite(value) ? `${Math.round(value).toLocaleString("ko-KR")}만원` : "—";
}

export default function BasicPredictionResult({ result, hidden, badge, guidance, warnings, limited }: {
  result: RegressionPredictResponse;
  hidden: boolean;
  badge: { label: string; className: string } | null;
  guidance: string[];
  warnings: string[];
  limited: boolean;
}) {
  return <div className="space-y-4 rounded-xl border border-indigo-200 bg-indigo-50/40 p-4 dark:border-indigo-500/30 dark:bg-slate-900/60" data-basic-prediction-result>
    {badge && <span className={clsx("inline-block rounded px-2 py-1 text-xs font-medium", badge.className)}>{badge.label}</span>}
    <div>
      <p className="text-sm text-slate-600 dark:text-slate-300">통계적 추정금액</p>
      {hidden ? <p className="mt-2 text-base font-medium text-slate-700 dark:text-slate-200">입력 조건이 분석 범위를 크게 벗어나 추정금액을 표시하지 않습니다.</p>
        : <p className="mt-2 break-words text-3xl font-bold leading-tight tabular-nums text-indigo-700 dark:text-indigo-200 sm:text-4xl">{amount(result.y_hat)}</p>}
    </div>
    {!hidden && <div className="rounded-lg bg-white/70 px-3 py-3 dark:bg-slate-800/70">
      <p className="flex items-center gap-1 text-sm text-slate-600 dark:text-slate-300">95% 평균 추정범위 <StatsGlossaryHelp termId="confidence_interval" size="xs" /></p>
      <p className="mt-1 text-lg font-semibold tabular-nums text-slate-900 dark:text-slate-100">{amount(result.ci_lower)} ~ {amount(result.ci_upper)}</p>
    </div>}
    {limited && <p role="status" className="text-xs leading-relaxed text-amber-800 dark:text-amber-200">일부 변수의 효과를 따로 구분하기 어려운 모형입니다. 추정값 해석에 주의해 주세요.</p>}
    {guidance.length > 0 && <div className="space-y-1 text-xs leading-relaxed text-amber-800 dark:text-amber-200">
      {guidance.map(line => <p key={line}>{line}</p>)}
    </div>}
    <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-200">이 결과는 AVM에 의한 가격평가가 아닌, 회귀모형의 통계적 참고값입니다.</p>
    <details className="border-t border-slate-200 pt-3 text-xs text-slate-600 dark:border-slate-700 dark:text-slate-300">
      <summary className="cursor-pointer font-medium">예측범위와 상세 안내{warnings.length > 0 ? ` · 주의사항 ${warnings.length}개` : ""}</summary>
      <div className="mt-3 space-y-3 leading-relaxed">
        {!hidden && <div>
          <p className="flex items-center gap-1 font-medium">95% 개별 거래 예측범위 <StatsGlossaryHelp termId="prediction_interval" size="xs" /></p>
          <p className="mt-1 tabular-nums">{amount(result.pi_lower)} ~ {amount(result.pi_upper)}</p>
          <p className="mt-1">개별 거래의 변동까지 고려한 범위여서 평균 추정범위보다 넓을 수 있습니다.</p>
        </div>}
        <p>모형에 포함되지 않은 특성과 거래 조건에 따라 실제 금액은 달라질 수 있습니다. 표시한 범위가 실제 거래금액을 보장하지는 않습니다.</p>
        {warnings.map(warning => <p key={warning}>{warning}</p>)}
      </div>
    </details>
  </div>;
}
