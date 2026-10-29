import type { LandRegressionResponse } from "../types";
import AnalysisSummary, { primaryCaution } from "../../../shared/regression-ui/AnalysisSummary";
import { DetailAnalysis, SummaryHeading } from "../../../shared/regression-ui/ReadingLayout";
import { formatProbability } from "../../../shared/regression-ui/format";
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
  const shareGroups = (data.analysis?.sample_groups ?? []).filter((group) => group.structural_excluded_n != null);
  const shareExcluded = shareGroups.reduce((sum, group) => sum + (group.structural_excluded_n ?? 0), 0);
  const shareLinked = shareGroups.reduce((sum, group) => sum + (group.linked_n ?? 0), 0);
  const shareUnlinked = shareGroups.reduce((sum, group) => sum + (group.unlinked_n ?? 0), 0);

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-3">
      <section className="space-y-2" aria-label="결과 요약">
        <SummaryHeading />
        {data.warnings.map((w) => (
          <p key={w} className="text-xs text-amber-700 bg-amber-50 dark:text-amber-300 dark:bg-amber-950/40 rounded px-2 py-1">
            {w}
          </p>
        ))}
        {primaryCaution(data.analysis) && (
          <p className="text-[11px] leading-snug text-amber-800 dark:text-amber-300">{primaryCaution(data.analysis)}</p>
        )}

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs text-slate-700">
        <MetricWithHelp label={data.model_type === "log" ? "R² (로그)" : "R²"} termId="r_squared" value={fmtDecimal(data.r_squared, 5)} />
        <MetricWithHelp label={data.model_type === "log" ? "조정 R² (로그)" : "조정 R²"} termId="adj_r_squared" value={fmtDecimal(data.adj_r_squared, 5)} />
        <div>유의 계수 {sigCount}개 (p&lt;0.1, 절편 제외)</div>
        {data.f_p_value != null && (
          <MetricWithHelp label="F p" termId="f_p_value" value={formatProbability(data.f_p_value)} />
        )}
          <div className="flex items-center gap-1">
            모델 {modelLabel}
            <StatsGlossaryHelp termId="ols" size="xs" />
            <StatsGlossaryHelp termId="log_model" size="xs" />
          </div>
        <MetricWithHelp label="n=" termId="fit_n" value={data.n.toLocaleString("ko-KR")} />
      </div>
      {shareGroups.length > 0 && (
        <p className="text-[11px] text-slate-600">
          지분 제외 {shareExcluded.toLocaleString("ko-KR")}건 · 공시지가 연결 {shareLinked.toLocaleString("ko-KR")}건 / 미연결 {shareUnlinked.toLocaleString("ko-KR")}건
        </p>
      )}
      {data.missing_treatment_label && (
        <p className="text-[11px] text-slate-500">{data.missing_treatment_label}</p>
      )}
      </section>

      <DetailAnalysis>
      <AnalysisSummary analysis={data.analysis} />

      {data.coefficients.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs font-semibold text-slate-600">회귀식과 계수</div>
          <LandRegressionEquation coefficients={data.coefficients} modelType={data.model_type} />
          {data.model_type === "log" && data.coefficients.some((c) => c.name === "log_area") && (
            <p className="text-[11px] leading-snug text-slate-600">
              면적 계수는 면적이 1% 늘 때 단가의 % 변화입니다.
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
      </DetailAnalysis>
    </div>
  );
}
