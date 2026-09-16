import clsx from "clsx";
import type { MacroCorr, MacroPairRow } from "../api/insightClient";
import { LAG_LABELS } from "../copy/insight01";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";

function fmtR(r: number | null | undefined): string {
  if (r == null || Number.isNaN(r)) return "—";
  const sign = r > 0 ? "+" : "";
  return `${sign}${r.toFixed(2)}`;
}

function cell(row: MacroPairRow, key: string): MacroCorr | null {
  const v = row[key];
  if (v && typeof v === "object" && "r" in v) return v as MacroCorr;
  return null;
}

export default function CorrTable({
  title,
  lead,
  pairs,
  types,
  lags,
  keyPrefix,
}: {
  title: string;
  lead: string | string[];
  pairs: MacroPairRow[];
  types: string[];
  lags: number[];
  keyPrefix: string;
}) {
  const byType = new Map(pairs.map((p) => [p.type, p]));
  const leads = Array.isArray(lead) ? lead : [lead];
  const nSample = lags
    .map((lag) => {
      const row = byType.get("합계") || pairs[0];
      return row ? cell(row, `${keyPrefix}_lag${lag}`)?.n : undefined;
    })
    .find((n) => n != null);
  return (
    <section className="card p-4 space-y-3">
      <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 flex items-center gap-1">
        {title}
        <StatsGlossaryHelp termId="pearson_r" size="xs" />
      </h3>
      <div className="space-y-1.5 text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
        {leads.map((p) => (
          <p key={p}>{p}</p>
        ))}
      </div>
      <div className="overflow-x-auto">
        <table className="data w-full min-w-[32rem]">
          <thead>
            <tr>
              <th>유형</th>
              {lags.map((lag) => (
                <th key={lag}>{LAG_LABELS[lag] ?? `+${lag}`}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {types.map((t) => {
              const row = byType.get(t);
              const isTotal = t === "합계";
              return (
                <tr key={t} className={clsx(isTotal && "font-semibold bg-slate-50 dark:bg-slate-800/80")}>
                  <td>{t}</td>
                  {lags.map((lag) => {
                    const c = row ? cell(row, `${keyPrefix}_lag${lag}`) : null;
                    return <td key={lag}>{fmtR(c?.r)}</td>;
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-500">
        칸의 숫자는 상관계수입니다.
        {nSample != null ? ` 겹치는 달 수는 n≈${nSample}입니다.` : ""}
      </p>
    </section>
  );
}
