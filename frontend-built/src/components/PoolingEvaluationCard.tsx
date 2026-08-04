import { useState } from "react";
import clsx from "clsx";
import type { PoolingEvaluation, TwinGateResult } from "../types";

function stars(n: number): string {
  const clamped = Math.max(1, Math.min(5, n));
  return "★".repeat(clamped) + "☆".repeat(5 - clamped);
}

function fmtPct(v: number | null | undefined): string {
  return v != null ? `${v.toFixed(2)}%` : "—";
}

function regionLabel(codes: string[], regionNameByCode?: Record<string, string>): string {
  if (!codes.length) return "—";
  return codes.map((c) => regionNameByCode?.[c] ?? c).join(" + ");
}

function decisionTitleFor(decision: string, label?: string): string {
  if (decision === "local") return "현재 지역만 사용 (Local)";
  if (decision === "insufficient_data") return "판단 보류";
  return label ? `${label} 적용` : "Twin Pooling 적용";
}

function gateBadge(gate: TwinGateResult) {
  if (gate.accepted) {
    return (
      <span className="text-emerald-600 dark:text-emerald-400 font-medium">✓ 통과</span>
    );
  }
  return <span className="text-red-600 dark:text-red-400 font-medium">✕ 제외</span>;
}

function TwinGateList({
  gates,
  regionNameByCode,
}: {
  gates: TwinGateResult[];
  regionNameByCode?: Record<string, string>;
}) {
  const [open, setOpen] = useState(false);
  if (!gates.length) return null;
  const acceptedN = gates.filter((g) => g.accepted).length;

  return (
    <div className="border-t border-violet-200 dark:border-violet-800 pt-1.5">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="text-[11px] text-violet-700 dark:text-violet-300 hover:underline"
      >
        {open ? "▾" : "▸"} 가격수준·인접성 hard gate — Twin {acceptedN}/{gates.length}개 통과
      </button>
      {open && (
        <ul className="mt-1 space-y-1 text-[11px]">
          {gates.map((g) => (
            <li key={g.region_code} className="flex flex-wrap items-baseline gap-1.5">
              {gateBadge(g)}
              <span className="text-slate-700 dark:text-slate-300">
                #{g.rank} {regionNameByCode?.[g.region_code] ?? g.region_code}
              </span>
              {g.similarity_score != null && (
                <span className="text-slate-400 dark:text-slate-500">
                  유사도 {g.similarity_score.toFixed(2)}
                </span>
              )}
              {g.price_ratio != null && (
                <span className="text-slate-400 dark:text-slate-500">
                  가격ratio {g.price_ratio.toFixed(2)}
                </span>
              )}
              {g.reasons.length > 0 && (
                <span className="text-red-500 dark:text-red-400">{g.reasons.join(" · ")}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * Local vs Twin Pooling(복수 조합) 실측 비교 — "후보는 제안하고, Validation이 선택한다"를
 * 통계값이 아니라 결정과 이유를 앞세워 보여준다. V2: hard gate를 통과한 Twin으로
 * 만든 여러 pool 조합(상위 1개/상위 3개/전체)을 Local과 함께 경쟁시킨다.
 */
export function PoolingEvaluationCard({
  evaluation,
  regionNameByCode,
}: {
  evaluation?: PoolingEvaluation | null;
  regionNameByCode?: Record<string, string>;
}) {
  if (!evaluation || !evaluation.candidates.length) return null;

  const winner = evaluation.candidates.find((c) => c.candidate_id === evaluation.decision);
  const confidence = evaluation.decision_confidence;
  const decisionTitle = decisionTitleFor(evaluation.decision, winner?.label);

  return (
    <div className="rounded-md border border-violet-200 bg-violet-50/60 dark:bg-violet-950/20 dark:border-violet-800 p-2.5 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-violet-900 dark:text-violet-100">
          최종 추천: {decisionTitle}
        </span>
        {confidence && (
          <span className="text-amber-600 dark:text-amber-300 font-semibold tabular-nums shrink-0">
            {stars(confidence.stars)} Confidence {confidence.grade}
          </span>
        )}
      </div>

      <p className="text-slate-700 dark:text-slate-300">{evaluation.decision_reason}</p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
        {evaluation.candidates.map((c) => (
          <div
            key={c.candidate_id}
            className={clsx(
              "rounded border px-2 py-1.5 space-y-0.5",
              evaluation.decision === c.candidate_id
                ? "border-violet-400 bg-white dark:bg-slate-900"
                : "border-slate-200 dark:border-slate-700 bg-white/60 dark:bg-slate-900/40",
            )}
          >
            <p className="font-medium text-slate-800 dark:text-slate-100 flex items-center gap-1">
              {evaluation.decision === c.candidate_id && (
                <span className="text-violet-600 dark:text-violet-400">✓</span>
              )}
              {c.label}
            </p>
            <p className="text-slate-500 dark:text-slate-400">
              n={c.n} · CV-MAPE {fmtPct(c.cv_mape)} · AIC {c.aic?.toFixed(1) ?? "—"}
            </p>
            {c.candidate_id !== "local" && (
              <p
                className="text-slate-400 dark:text-slate-500 truncate"
                title={regionLabel(c.region_codes, regionNameByCode)}
              >
                Pooling 지역: {regionLabel(c.region_codes, regionNameByCode)}
              </p>
            )}
          </div>
        ))}
      </div>

      {confidence?.note && (
        <p className="text-slate-400 dark:text-slate-500 text-[11px]">{confidence.note}</p>
      )}

      <TwinGateList gates={evaluation.twin_gates} regionNameByCode={regionNameByCode} />
    </div>
  );
}
