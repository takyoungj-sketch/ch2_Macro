export type AnalysisPhase = "idle" | "running" | "failed" | "previous" | "ready" | "unavailable";

/** 실행 실패와 이전 성공 결과의 존재는 별개다. 새 요청 중에는 완료로 표시하지 않는다. */
export function analysisPhase(input: { pending?: boolean; failed?: boolean; hasResult?: boolean;
  changed?: boolean; unavailable?: boolean }): AnalysisPhase {
  if (input.pending) return "running";
  if (input.failed) return "failed";
  if (input.unavailable) return "unavailable";
  if (input.hasResult) return input.changed ? "previous" : "ready";
  return "idle";
}

export const phaseLabels: Record<AnalysisPhase, string> = {
  idle: "미실행", running: "계산 중", failed: "실패 · 다시 실행 필요", previous: "이전 조건의 결과",
  ready: "계산 완료", unavailable: "실행 조건 미충족",
};
