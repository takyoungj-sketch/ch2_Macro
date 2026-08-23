import clsx from "clsx";
import type { FunnelStep, SampleBreakdown } from "../types";

export default function SampleFunnel({ sample }: { sample: SampleBreakdown }) {
  const steps = sample.funnel ?? [];
  if (!steps.length) {
    return (
      <p className="text-[11px] text-slate-500">
        조회 {sample.n_pool.toLocaleString("ko-KR")} · 적합 {sample.n_fit.toLocaleString("ko-KR")}
      </p>
    );
  }

  return (
    <div className="rounded-md border border-slate-200 dark:border-slate-600 overflow-hidden">
      <p className="px-2.5 py-1 text-[10px] font-medium text-slate-500 dark:text-slate-400">
        조회 → 적합 표본
      </p>
      <ul className="list-none divide-y divide-slate-100 dark:divide-slate-700">
        {steps.map((step) => (
          <FunnelRow key={step.code} step={step} />
        ))}
      </ul>
    </div>
  );
}

function FunnelRow({ step }: { step: FunnelStep }) {
  const count = step.n.toLocaleString("ko-KR");
  const reasons = step.reasons ?? [];
  const muted = step.kind === "drop" && step.n === 0;
  const rowClass = clsx(
    "flex items-center justify-between gap-3 px-2.5 py-1.5 text-[11px]",
    muted && "text-slate-400",
  );

  if (step.kind === "drop" && step.n > 0 && reasons.length > 0) {
    return (
      <li>
        <details>
          <summary
            className={clsx(
              rowClass,
              "cursor-pointer list-none [&::-webkit-details-marker]:hidden",
            )}
          >
            <span>
              {step.label}
              <span className="ml-1 font-normal text-[10px] text-slate-400">펼치기</span>
            </span>
            <span className="tabular-nums">{count}</span>
          </summary>
          <div className="px-2.5 pb-2 pt-0.5 space-y-1 bg-slate-50 dark:bg-slate-800/50">
            {step.note && <p className="text-[10px] text-slate-500">{step.note}</p>}
            <ul className="list-none space-y-0.5">
              {reasons.map((r) => (
                <li
                  key={r.code}
                  className="flex justify-between gap-3 text-[11px] text-slate-700 dark:text-slate-200"
                >
                  <span>{r.label}</span>
                  <span className="tabular-nums">{r.n.toLocaleString("ko-KR")}</span>
                </li>
              ))}
            </ul>
          </div>
        </details>
      </li>
    );
  }

  return (
    <li className={rowClass}>
      <span className={clsx(step.kind === "remain" && "font-medium")}>{step.label}</span>
      <span className="tabular-nums">{count}</span>
    </li>
  );
}
