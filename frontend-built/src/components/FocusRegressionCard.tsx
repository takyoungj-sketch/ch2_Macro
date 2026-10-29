import clsx from "clsx";
import AnalysisSummary from "../../../shared/regression-ui/AnalysisSummary";
import { DetailAnalysis } from "../../../shared/regression-ui/ReadingLayout";
import { formatProbability } from "../../../shared/regression-ui/format";
import { StatsGlossaryHelp } from "./StatsGlossaryHelp";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import type { AnalysisExplain } from "../../../shared/analysis-help/types";
import type { AssetType, RegressionLevelResult, ResponseScale } from "../types";
import { formatPartialNNote } from "../utils/recommendationLabels";
import { ADMIN_LABELS, formatCoefName, fmtDecimal, fmtNum, levelCardTitle } from "../utils/regressionFormat";
import { BasicRegressionCoefficients, BasicRegressionEquation } from "./BasicRegressionDetails";
import SampleFunnel from "./SampleFunnel";

type Props = {
  result: RegressionLevelResult;
  assetType: AssetType;
  responseScale: ResponseScale;
  includePartial?: boolean;
  partialTxCount?: number | null;
  partialNNote?: string | null;
};

function explain(id: string, title: string, summary: string, interpretation: string[] = [], limitations: string[] = []): AnalysisExplain {
  return { spec_id: `built.basic.${id}`, spec_version: "1", title, summary, interpretation, limitations };
}

const COEFFICIENT_HELP = explain("coefficients", "회귀계수와 유의성", "다른 조건이 같을 때 각 변수가 금액과 어떤 관계를 보이는지 확인합니다.", [
  "회귀식에는 실제로 적합된 변수 중 p<0.1인 항을 모두 표시합니다. 유의하지 않은 항은 화면에서만 숨기며, 추정금액은 전체 적합 모형으로 계산합니다.",
  "계수 표의 강조는 기존 회귀식 표시 기준인 p<0.1을 따릅니다. 유의 계수 수는 기존 집계 기준인 p<0.05이며 절편은 제외합니다.",
  "절편은 회귀식에 유지하며, 표 아래에서 절편의 상세 통계를 확인할 수 있습니다.",
], ["계수가 유의하더라도 인과관계나 모형의 정확도를 보장하지 않습니다."]);
const ZONE_HELP = explain("zone", "용도지역을 해석할 때", "여러 용도지역에 걸친 필지는 원본 자료의 제1용도지역을 대표 변수로 사용합니다.", [], [
  "제1용도지역이 면적 비율이 가장 크거나 가격에 가장 큰 영향을 미치는 지역이라는 뜻은 아닙니다.",
  "여러 용도지역에 해당하는 거래는 이 자료의 한계를 함께 고려해 해석해 주세요.",
]);

export default function FocusRegressionCard({ result, assetType, responseScale, includePartial = false, partialTxCount, partialNNote }: Props) {
  const analysis = result.analysis;
  const limited = Boolean(analysis?.provision?.identification_limited || (analysis?.design_rank != null && analysis.design_rank < analysis.coefficient_n));
  const caution = limited ? "일부 변수의 효과를 따로 구분하기 어렵습니다. 계수 해석에 주의해 주세요."
    : analysis?.provision?.tier === "caution" || result.n < 30 ? "표본에 비해 변수가 많거나 표본이 적어, 계수 해석에 주의가 필요합니다." : null;
  const validation = analysis?.metrics.find(metric => metric.role === "selection_validation")?.validation;
  const cvHelp = explain("cv", "CV-MAPE와 검증 범위", "과거 연도로 학습한 모형이 다음 연도 거래에서 보인 오차입니다.", [
    "학습 MAPE와 구분해 읽어 주세요. 모형 탐색과 평가 거래가 다르면 오차도 달라질 수 있습니다.",
    ...(validation ? [`검증 완료 ${validation.completed_folds}/${validation.requested_folds}개 연도 · 정상 예측 ${validation.evaluated_n}/${validation.eligible_n}건`, ...(validation.reason ? [validation.reason] : []), ...validation.failures.map(item => `${item.year != null ? `${item.year}년` : `${item.fold}번 분할`}: ${item.reason}`)] : []),
    ...(result.confirm_cv_mape != null ? [`마지막 연도 확인 오차: ${fmtDecimal(result.confirm_cv_mape, 2)}%`] : []),
    ...(result.confirm_cv_note ? [result.confirm_cv_note] : []),
  ], ["일부 연도만 완료한 오차는 해당 연도 기준의 결과입니다. 미래 정확도를 보장하지 않습니다."]);
  const cautionHelp = explain("limits", "모형 해석과 주의사항", caution ?? "선택한 자료와 변수에서 계산한 결과입니다.", result.warning ? [result.warning] : [], analysis?.provision?.reasons ?? []);
  const vif = result.vif ?? [];
  const highVif = vif.filter(value => value.vif != null && value.vif >= 10).length;
  const moderateVif = vif.filter(value => value.vif != null && value.vif >= 5 && value.vif < 10).length;
  const metrics = [
    { label: responseScale === "linear" ? "결정계수 R²" : "결정계수 R² (로그)", term: "r_squared", value: fmtDecimal(result.r_squared, 3) },
    { label: responseScale === "linear" ? "조정 R²" : "조정 R² (로그)", term: "adj_r_squared", value: fmtDecimal(result.adj_r_squared, 3) },
    { label: "학습 MAPE", term: "mape", value: result.mape != null ? `${fmtDecimal(result.mape, 2)}%` : "—" },
    { label: "CV-MAPE", term: "cv_mape", value: result.cv_mape != null ? `${fmtDecimal(result.cv_mape, 2)}%` : "—" },
  ];

  return <div className="card space-y-4" data-basic-regression-result>
    <header className="flex flex-wrap items-start justify-between gap-2">
      <div>
        <h3 className="text-base font-semibold">{levelCardTitle(result.scope_label, result.admin_level)}</h3>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{ADMIN_LABELS[result.admin_level] ?? result.admin_level} · 거래금액(만원)</p>
      </div>
      <div className="flex items-center gap-1 text-sm font-medium">적합 거래 {fmtNum(result.n)}건 <StatsGlossaryHelp termId="fit_n" size="xs" /></div>
    </header>
    <section className="space-y-3" aria-label="결과 요약">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold">결과 요약</h4>
        <AnalysisHelpPanel explain={cautionHelp} title="모형 해석과 주의사항" />
      </div>
      <div className="grid grid-cols-2 gap-2">
        {metrics.map(metric => <div key={metric.term} className="rounded-lg border border-slate-200 bg-slate-50/60 px-3 py-3 dark:border-slate-700 dark:bg-slate-900/40">
          <div className="flex items-center gap-1 text-xs text-slate-600 dark:text-slate-300">
            {metric.label}
            {metric.term === "cv_mape" ? <AnalysisHelpPanel explain={cvHelp} title="CV-MAPE와 검증 범위" /> : <StatsGlossaryHelp termId={metric.term} size="xs" />}
          </div>
          <p className="mt-2 text-xl font-semibold tabular-nums text-slate-900 dark:text-slate-100">{metric.value}</p>
          {metric.term === "cv_mape" && validation?.status === "partial" && <span className="text-xs text-slate-600 dark:text-slate-300">일부 연도 기준</span>}
        </div>)}
      </div>
      {caution && <p role="status" className="border-l-2 border-amber-500 pl-3 text-xs leading-relaxed text-amber-800 dark:text-amber-200">{caution}</p>}
      <BasicRegressionEquation coefficients={result.coefficients} responseScale={responseScale} assetType={assetType} equation={result.equation} predictOptions={result.predict_options} />
    </section>

    <DetailAnalysis>
      {result.coefficients.length > 0 && <section className="space-y-2" aria-label="회귀계수 상세">
        <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
          <h4 className="text-sm font-semibold">회귀계수</h4>
          <div className="flex items-center gap-3 text-xs text-slate-600 dark:text-slate-300">
            <span>유의 계수 {result.significant_count}개 <AnalysisHelpPanel explain={COEFFICIENT_HELP} title="회귀계수와 유의성" /></span>
            <span>용도지역 해석 <AnalysisHelpPanel explain={ZONE_HELP} title="용도지역을 해석할 때" /></span>
          </div>
        </div>
        <BasicRegressionCoefficients coefficients={result.coefficients} responseScale={responseScale} assetType={assetType} predictOptions={result.predict_options} />
      </section>}
      {vif.length > 0 && <section className="space-y-2" aria-label="다중공선성 분석">
        <div className="flex flex-wrap items-center gap-2 text-sm font-semibold">다중공선성 <StatsGlossaryHelp termId="vif" size="xs" /></div>
        <p className="text-xs text-slate-600 dark:text-slate-300">VIF 10 이상 {highVif}개 · 5 이상 10 미만 {moderateVif}개</p>
        <details className="text-xs">
          <summary className="cursor-pointer py-1 text-slate-600 dark:text-slate-300">변수별 VIF 보기</summary>
          <div className="flex flex-wrap gap-x-5 gap-y-2 py-2">{vif.map(value => <span key={value.name} className={clsx(value.vif != null && value.vif >= 10 && "font-semibold text-amber-800 dark:text-amber-200")}>
            {formatCoefName(value.name, assetType)} <span className="tabular-nums">{value.vif != null ? fmtDecimal(value.vif, 2) : "—"}</span>
          </span>)}</div>
        </details>
      </section>}
      <details className="text-xs">
        <summary className="cursor-pointer py-1 font-medium text-slate-600 dark:text-slate-300">분석에 사용한 자료와 표본</summary>
        <div className="mt-2 space-y-3">
          {result.sample && <SampleFunnel sample={result.sample} />}
          {(partialNNote || partialTxCount != null) && <p>{partialNNote || formatPartialNNote(includePartial, partialTxCount)}</p>}
          <AnalysisSummary analysis={analysis} />
        </div>
      </details>
      <details className="text-xs text-slate-600 dark:text-slate-300">
        <summary className="cursor-pointer py-1">추가 통계정보</summary>
        <p className="mt-2">F 검정 p값: {formatProbability(result.f_p_value)} <StatsGlossaryHelp termId="f_p_value" size="xs" /></p>
      </details>
    </DetailAnalysis>
  </div>;
}
