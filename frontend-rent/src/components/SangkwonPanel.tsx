import clsx from "clsx";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import {
  SANGKWON_KIND_LABELS,
  SANGKWON_KINDS,
  SANGKWON_METRIC_HELP,
  SANGKWON_METRIC_LABELS,
  type SangkwonAnnualResponse,
  type SangkwonHit,
} from "../types";

const WON_METRICS = new Set(["rent", "floor_rent", "noi_per_m2"]);

function fmtCell(metric: string, v: number | null | undefined) {
  if (v == null) return "—";
  const digits =
    metric === "building_count" ? 0 : WON_METRICS.has(metric) || metric === "avg_area" ? 1 : Math.abs(v) < 20 ? 2 : 1;
  return v.toLocaleString("ko-KR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits === 0 ? 0 : 1,
  });
}

type Props = {
  hits: SangkwonHit[];
  selected: string | null;
  onSelect: (name: string) => void;
  onOpenTrend: () => void;
  annual: SangkwonAnnualResponse | undefined;
  loading: boolean;
};

export default function SangkwonPanel({
  hits,
  selected,
  onSelect,
  onOpenTrend,
  annual,
  loading,
}: Props) {
  if (!hits.length) return null;
  const year = annual?.year;
  const windowLabel = annual?.window_label || (year != null ? `${year}년 연간` : "—");
  const windowHint = annual?.window_mode === "calendar_year" ? "연간" : "1년 롤링";
  const groups: { label: string; start: number; count: number }[] = [];
  for (let i = 0; i < (annual?.rows.length ?? 0); i++) {
    const label = annual!.rows[i].group_label || "";
    const last = groups[groups.length - 1];
    if (last && last.label === label) last.count += 1;
    else groups.push({ label, start: i, count: 1 });
  }

  return (
    <div className="mb-4">
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">상권</h3>
        <div className="flex flex-wrap gap-1.5">
          {hits.map((h) => {
            const on = h.sec_nm === selected;
            return (
              <button
                key={h.sec_nm}
                type="button"
                className={clsx(
                  "rounded-md border px-2 py-1 text-xs font-semibold",
                  on
                    ? "border-teal-600 bg-teal-600 text-white"
                    : "border-slate-300 bg-white dark:border-slate-500 dark:bg-slate-800",
                )}
                onClick={() => onSelect(h.sec_nm)}
              >
                {h.sec_nm}
              </button>
            );
          })}
        </div>
        {selected && (
          <button
            type="button"
            className="ml-auto rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-semibold dark:border-slate-500 dark:bg-slate-800"
            onClick={onOpenTrend}
          >
            추세
          </button>
        )}
      </div>
      {loading && <p className="text-xs text-slate-400">상권 통계 불러오는 중…</p>}
      {annual && (
        <>
          <p className="text-[11px] text-slate-500 mb-1 inline-flex items-center gap-1">
            한국부동산원 상업용부동산 임대동향조사 · {windowLabel} {windowHint} · 상권 집계(건물 아님)
            <StatsGlossaryHelp termId="sangkwon_survey" size="xs" />
            {annual.source_file ? ` · ${annual.source_file}` : ""}
          </p>
          <div className="card overflow-x-auto p-0">
            <table className="data text-xs sangkwon-table">
              <colgroup>
                <col className="sk-group" />
                <col className="sk-metric" />
                {SANGKWON_KINDS.map((k) => (
                  <col key={k} />
                ))}
              </colgroup>
              <thead>
                <tr>
                  <th>구분</th>
                  <th>지표</th>
                  {SANGKWON_KINDS.map((k) => (
                    <th key={k}>{SANGKWON_KIND_LABELS[k]}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {annual.rows.map((row, idx) => {
                  const g = groups.find((x) => idx >= x.start && idx < x.start + x.count);
                  const showGroup = g && idx === g.start;
                  const helpId = SANGKWON_METRIC_HELP[row.metric];
                  return (
                    <tr key={row.metric}>
                      {showGroup && (
                        <td className="sk-group" rowSpan={g.count}>
                          {g.label}
                        </td>
                      )}
                      <td className="sk-metric">
                        <span className="inline-flex items-center justify-center gap-1">
                          {SANGKWON_METRIC_LABELS[row.metric] ?? row.metric}
                          {helpId ? <StatsGlossaryHelp termId={helpId} size="xs" /> : null}
                        </span>
                      </td>
                      {SANGKWON_KINDS.map((k) => (
                        <td key={k} className="num">
                          {fmtCell(row.metric, row.values[k])}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
