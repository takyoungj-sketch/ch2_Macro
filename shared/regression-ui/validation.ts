import type { RegressionValidationContext } from "./types";

export function validationCaption(report?: RegressionValidationContext | null): string {
  if (!report) return "";
  const label = report.method === "random_holdout" ? "분리 검증" : report.method === "rolling_year" ? "연도별 검증" : report.method === "last_year" ? "마지막 연도 확인" : "교차검증";
  const unit = report.observation_unit === "complex" ? "곳" : "건";
  const foldUnit = report.method === "rolling_year" || report.method === "last_year" ? "연도" : "분할";
  if (report.status === "not_run") return `${label} 미실행 · ${report.reason ?? "실행 기록이 없습니다."}`;
  const coverage = `완료 ${report.completed_folds}/${report.requested_folds}${foldUnit} · 정상 예측 ${report.evaluated_n.toLocaleString("ko-KR")}/${report.eligible_n.toLocaleString("ko-KR")}${unit}`;
  return report.status === "available" ? `${label} ${coverage}`
    : `${label} ${report.status === "partial" ? "일부 제공" : "미제공"} · ${coverage} · ${report.reason ?? "전체 평가를 완료하지 못했습니다."}`;
}
