import clsx from "clsx";
import {
  canRunRegression,
  isRegressionRecommended,
  isRegressionRecentThin,
  regressionGateMessages,
  regressionTabTitle,
} from "../utils/analysisGates";

export default function RegressionSampleHint({
  useCohort,
  countTotal,
  countRecent,
  messages,
}: {
  useCohort: boolean;
  countTotal?: number | null;
  countRecent?: number | null;
  messages?: string[];
}) {
  if (useCohort) return null;
  const canRun = canRunRegression(countTotal);
  const recommended = isRegressionRecommended(countTotal);
  const recentThin = isRegressionRecentThin(countRecent, countTotal);
  if (canRun && recommended && !recentThin) return null;

  const fromApi = regressionGateMessages(messages);
  const body =
    fromApi.length > 0
      ? fromApi.join(" ")
      : (regressionTabTitle(countTotal, countRecent) ?? "권장 표본 기준 미달");

  return (
    <p
      className={clsx(
        "text-[11px] rounded px-2 py-1.5 border leading-snug",
        !canRun
          ? "text-red-800 dark:text-red-300 bg-red-50 dark:bg-red-950/40 border-red-100 dark:border-red-900"
          : "text-amber-800 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 border-amber-100 dark:border-amber-900",
      )}
    >
      {body}
    </p>
  );
}
