import type { LandRegressionResponse } from "../types";
import AnalysisSummary, { primaryCaution } from "../../../shared/regression-ui/AnalysisSummary";
import { DetailAnalysis } from "../../../shared/regression-ui/ReadingLayout";
import { formatProbability } from "../../../shared/regression-ui/format";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import { countSignificantCoefficients, fmtDecimal } from "../utils/landRegressionFormat";
import LandRegressionEquation from "./LandRegressionEquation";
import LandRegressionEffectsTable from "./LandRegressionEffectsTable";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import { LAND_REGRESSION_RESULT_HELP } from "../constants/landStatsExplain";

export default function LandRegressionResults({ data }: { data: LandRegressionResponse }) {
  const sigCount = data.significant_count ?? countSignificantCoefficients(data.coefficients);
  const shareGroups = (data.analysis?.sample_groups ?? []).filter(group => group.structural_excluded_n != null);
  const shareExcluded = shareGroups.reduce((sum, group) => sum + (group.structural_excluded_n ?? 0), 0);
  const shareLinked = shareGroups.reduce((sum, group) => sum + (group.linked_n ?? 0), 0);
  const shareUnlinked = shareGroups.reduce((sum, group) => sum + (group.unlinked_n ?? 0), 0);
  const caution = primaryCaution(data.analysis);
  const warnings = [...new Set(data.warnings)].filter(w => w !== caution);
  const metrics = [
    { label: data.model_type === "log" ? "결정계수 R² (로그)" : "결정계수 R²", term: "r_squared", value: data.r_squared },
    { label: data.model_type === "log" ? "조정 R² (로그)" : "조정 R²", term: "adj_r_squared", value: data.adj_r_squared },
  ];
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-4 dark:border-slate-700 dark:bg-slate-800/50">
      <section className="space-y-3" aria-label="결과 요약">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">결과 요약</h3>
          <div className="flex items-center gap-1 text-sm font-medium text-slate-700 dark:text-slate-200">적합 거래 {data.n.toLocaleString("ko-KR")}건 <StatsGlossaryHelp termId="fit_n" size="xs" /></div>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400">토지 단가(만원/㎡) · {data.model_type === "log" ? "로그회귀" : "선형회귀"}</p>
        <div className="grid grid-cols-2 gap-2">
          {metrics.map(metric => <div key={metric.term} className="rounded-lg border border-slate-200 bg-slate-50/60 px-3 py-3 dark:border-slate-700 dark:bg-slate-900/40">
            <div className="flex items-center gap-1 text-xs text-slate-600 dark:text-slate-300">{metric.label}<StatsGlossaryHelp termId={metric.term} size="xs" /></div>
            <p className="mt-2 text-xl font-semibold tabular-nums text-slate-900 dark:text-slate-100">{fmtDecimal(metric.value, 3)}</p>
          </div>)}
        </div>
        <p className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">학습·검증 MAPE는 이 결과에서 제공하지 않습니다.<AnalysisHelpPanel explain={LAND_REGRESSION_RESULT_HELP} /></p>
        {data.coefficients.length > 0 && <section className="space-y-2" aria-label="회귀식">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100">회귀식 <AnalysisHelpPanel explain={LAND_REGRESSION_RESULT_HELP} /></div>
          <LandRegressionEquation coefficients={data.coefficients} modelType={data.model_type} />
          {Object.keys(data.reference_categories).length > 0 && <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-300">기준 범주: {Object.entries(data.reference_categories).map(([k, v]) => `${k} ${v}`).join(" · ")}</p>}
        </section>}
        {(caution || warnings.length > 0) && <div role="status" className="border-l-2 border-amber-500 pl-3 space-y-1 text-xs leading-relaxed text-amber-800 dark:text-amber-200">
          {caution && <p>{caution}</p>}{warnings.map(w => <p key={w}>{w}</p>)}
        </div>}
      </section>
      <DetailAnalysis>
        {data.coefficients.length > 0 && <section className="space-y-2" aria-label="회귀계수 상세">
          <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
            <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-100">회귀계수</h4>
            <span className="flex items-center gap-1 text-xs text-slate-600 dark:text-slate-300">유의 계수 {sigCount}개 <AnalysisHelpPanel explain={LAND_REGRESSION_RESULT_HELP} /></span>
          </div>
          <LandRegressionEffectsTable coefficients={data.coefficients} modelType={data.model_type} />
        </section>}
        <details className="text-xs text-slate-700 dark:text-slate-200">
          <summary className="cursor-pointer py-1 font-medium">분석에 사용한 자료와 표본</summary>
          <div className="mt-2 space-y-3">
            {shareGroups.length > 0 && <p>조회 자료의 공시지가 연결 현황: 지분 제외 {shareExcluded.toLocaleString("ko-KR")}건 · 연결 {shareLinked.toLocaleString("ko-KR")}건 / 미연결 {shareUnlinked.toLocaleString("ko-KR")}건</p>}
            {data.missing_treatment_label && <p>{data.missing_treatment_label}</p>}
            <AnalysisSummary analysis={data.analysis} />
          </div>
        </details>
        <details className="text-xs text-slate-600 dark:text-slate-300">
          <summary className="cursor-pointer py-1 font-medium">추가 통계정보와 해석</summary>
          <p className="my-2">F 검정 p값: {formatProbability(data.f_p_value)} <StatsGlossaryHelp termId="f_p_value" size="xs" /></p>
          <AnalysisHelpPanel explain={LAND_REGRESSION_RESULT_HELP} />
        </details>
      </DetailAnalysis>
    </div>
  );
}
