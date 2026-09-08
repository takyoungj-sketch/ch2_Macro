// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
import type { ReactNode } from "react";
import { ESTIMATE_COPY, individualRangeHint, individualRangeLabel, type EstimateRangeSubject } from "./statisticalEstimateCopy";

type DisclaimerProps = {
  compact?: boolean;
  showRangesNote?: boolean;
};

export function StatisticalEstimateDisclaimer({
  compact = false,
  showRangesNote = true,
}: DisclaimerProps) {
  const size = compact ? "text-[10px]" : "text-[11px]";
  return (
    <div
      className={`${size} text-slate-500 dark:text-slate-400 leading-relaxed space-y-1.5 pt-1 border-t border-slate-200 dark:border-slate-700`}
    >
      <p>{ESTIMATE_COPY.avmOnce}</p>
      <p>{ESTIMATE_COPY.howToUse}</p>
      {showRangesNote && <p>{ESTIMATE_COPY.rangeFootnote}</p>}
    </div>
  );
}

type RangeRowProps = {
  kind: "mean" | "individual";
  subject?: EstimateRangeSubject;
  children: ReactNode;
  compact?: boolean;
};

export function StatisticalEstimateRangeRow({
  kind,
  subject = "거래",
  children,
  compact = false,
}: RangeRowProps) {
  const label = kind === "mean" ? ESTIMATE_COPY.meanRangeLabel : individualRangeLabel(subject);
  const hint = kind === "mean" ? ESTIMATE_COPY.meanRangeHint : individualRangeHint(subject);
  return (
    <div className={kind === "individual" ? "text-slate-500 dark:text-slate-400" : undefined}>
      <div>
        <span className="font-medium">{label}</span> {children}
      </div>
      <p className={compact ? "text-[10px] text-slate-400 mt-0.5" : "text-[10px] text-slate-400 mt-0.5"}>
        {hint}
      </p>
    </div>
  );
}

export function StatisticalEstimateCaption({ compact = false }: { compact?: boolean }) {
  return (
    <p className={compact ? "text-[10px] text-slate-400 mt-0.5" : "text-[11px] text-slate-500 mt-0.5"}>
      {ESTIMATE_COPY.valueCaption}
    </p>
  );
}
