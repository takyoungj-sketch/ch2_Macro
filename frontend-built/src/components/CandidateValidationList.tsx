import clsx from "clsx";
import type { CandidateValidationSummary, PoolingEvaluation } from "../types";

function candidateLabel(id: string): string {
  if (id === "local") return "현재 지역 (Local)";
  const twinMatch = id.match(/^profile-twin-(\d+)$/);
  if (twinMatch) return `Twin 후보 ${twinMatch[1]} (Profile)`;
  return id;
}

/** "후보는 제안하고, Validation이 선택한다" — 검증 통과와 실제 사용을 명시적으로 구분한다. */
function usageSummary(
  poolingEvaluation: PoolingEvaluation | null | undefined,
  acceptedCount: number,
): string {
  if (!poolingEvaluation) return "판단 보류 (Twin 데이터 없음)";
  if (poolingEvaluation.decision === "local") {
    return "Local 모델이 더 우수하여 Pooling 미적용";
  }
  if (poolingEvaluation.decision === "insufficient_data") {
    return "지표 부족으로 Local만 사용";
  }
  const winner = poolingEvaluation.candidates.find(
    (c) => c.candidate_id === poolingEvaluation.decision,
  );
  const usedRegions = winner?.region_codes.length ?? acceptedCount + 1;
  return `${winner?.label ?? "Pooling"} 적용 (${usedRegions}개 지역 사용)`;
}

/**
 * Candidate Factory 검증 결과 — Local·Profile Twin 후보가 왜 채택/제외됐는지, 그리고
 * 검증을 통과한 후보 중 실제로 무엇이 최종 모형에 쓰였는지를 세 단계로 보여준다:
 * 후보 생성 → 검증 통과 → 실제 사용. 검증 통과는 Pooling 후보 자격일 뿐, 실제 사용
 * 여부는 evaluate_local_vs_twin_pool의 결정(poolingEvaluation)이 결정한다.
 */
export function CandidateValidationList({
  validations,
  poolingEvaluation,
}: {
  validations?: CandidateValidationSummary[];
  poolingEvaluation?: PoolingEvaluation | null;
}) {
  if (!validations || !validations.length) return null;
  const acceptedCount = validations.filter((v) => v.accepted).length;

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-600 dark:text-slate-300">
        <span className="rounded bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5">
          후보 생성 {validations.length}개
        </span>
        <span className="text-slate-400">→</span>
        <span className="rounded bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5">
          검증 통과 {acceptedCount}개
        </span>
        <span className="text-slate-400">→</span>
        <span className="rounded bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-200 px-1.5 py-0.5 font-medium">
          실제 사용: {usageSummary(poolingEvaluation, acceptedCount)}
        </span>
      </div>

      <details className="group">
        <summary className="cursor-pointer font-medium text-slate-700 dark:text-slate-200">
          후보별 검증 상세 ({acceptedCount}/{validations.length}개 통과)
        </summary>
        <ul className="mt-1 space-y-1 pl-2 border-l-2 border-slate-200 dark:border-slate-600">
          {validations.map((v) => (
            <li key={v.candidate_id}>
              <span
                className={clsx(
                  "font-medium",
                  v.accepted
                    ? "text-emerald-700 dark:text-emerald-300"
                    : "text-red-600 dark:text-red-400",
                )}
              >
                {v.accepted ? "✓" : "✕"} {candidateLabel(v.candidate_id)}
              </span>
              {(v.reasons.length > 0 || v.warnings.length > 0) && (
                <ul className="text-slate-500 dark:text-slate-400 mt-0.5 space-y-0.5">
                  {v.reasons.map((r, i) => (
                    <li key={`r-${i}`}>· {r}</li>
                  ))}
                  {v.warnings.map((w, i) => (
                    <li key={`w-${i}`} className="text-amber-600 dark:text-amber-400">
                      · ⚠ {w}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
        <p className="text-slate-400 mt-1 text-[11px]">
          검증 통과는 Pooling 후보 자격일 뿐입니다. 실제 사용 여부는 위 Local vs Twin
          Pooling 비교 결과(CV-MAPE)로 결정됩니다.
        </p>
      </details>
    </div>
  );
}
