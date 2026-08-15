import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchSangkwonSeries } from "../api/client";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import {
  SANGKWON_KIND_LABELS,
  SANGKWON_KINDS,
  SANGKWON_METRIC_HELP,
  SANGKWON_METRIC_LABELS,
  type SangkwonAssetKind,
} from "../types";
import DraggableModalShell from "./DraggableModalShell";

const KIND_COLOR: Record<SangkwonAssetKind, string> = {
  office: "#4f46e5",
  mid_retail: "#d97706",
  small_retail: "#059669",
  strata: "#e11d48",
  retail_all: "#64748b",
};

const MAIN_CHART_METRICS = [
  "rent",
  "rent_index",
  "noi_per_m2",
  "opex_share",
  "noi_pct",
  "vacancy",
  "income_yield",
  "capital_yield",
  "investment_yield",
  "conversion",
];

const WON_METRICS = new Set(["rent", "floor_rent", "noi_per_m2"]);
const LABEL_DY = [-12, 14, -22, 22, -30];

function fmtPoint(metric: string, v: number) {
  const digits = WON_METRICS.has(metric) ? 1 : Math.abs(v) < 20 ? 2 : 1;
  return v.toLocaleString("ko-KR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits === 0 ? 0 : 1,
  });
}

function LineChart({
  years,
  series,
  metric,
}: {
  years: number[];
  series: { kind: SangkwonAssetKind; values: (number | null)[] }[];
  metric: string;
}) {
  const w = 560;
  const h = 200;
  const pad = { l: 44, r: 18, t: 28, b: 24 };
  const nums = series.flatMap((s) => s.values.filter((v): v is number => v != null));
  const min = nums.length ? Math.min(...nums) : 0;
  const max = nums.length ? Math.max(...nums) : 1;
  const span = max - min || 1;
  const x = (i: number) =>
    pad.l + (years.length <= 1 ? 0 : (i / (years.length - 1)) * (w - pad.l - pad.r));
  const y = (v: number) => pad.t + (1 - (v - min) / span) * (h - pad.t - pad.b);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-52">
      <line x1={pad.l} y1={h - pad.b} x2={w - pad.r} y2={h - pad.b} stroke="#94a3b8" />
      <line x1={pad.l} y1={pad.t} x2={pad.l} y2={h - pad.b} stroke="#94a3b8" />
      <text x={4} y={pad.t + 8} className="fill-slate-500 dark:fill-slate-400" fontSize="10">
        {max.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}
      </text>
      <text x={4} y={h - pad.b} className="fill-slate-500 dark:fill-slate-400" fontSize="10">
        {min.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}
      </text>
      {years.map((yr, i) => (
        <text
          key={yr}
          x={x(i)}
          y={h - 4}
          textAnchor="middle"
          className="fill-slate-500 dark:fill-slate-400"
          fontSize="9"
        >
          {yr}
        </text>
      ))}
      {series.map((s, si) => {
        const pts = s.values
          .map((v, i) => (v == null ? null : `${x(i)},${y(v)}`))
          .filter(Boolean)
          .join(" ");
        if (!pts) return null;
        const color = KIND_COLOR[s.kind];
        const dy = LABEL_DY[si] ?? -12;
        return (
          <g key={s.kind}>
            <polyline fill="none" stroke={color} strokeWidth="1.8" points={pts} />
            {s.values.map((v, i) =>
              v == null ? null : (
                <g key={`${s.kind}-${years[i]}`}>
                  <circle cx={x(i)} cy={y(v)} r="2.4" fill={color} />
                  <text
                    x={x(i)}
                    y={y(v) + dy}
                    textAnchor="middle"
                    fill={color}
                    fontSize="8"
                    fontWeight="600"
                  >
                    {fmtPoint(metric, v)}
                  </text>
                </g>
              ),
            )}
          </g>
        );
      })}
    </svg>
  );
}

type Props = {
  name: string;
  onClose: () => void;
};

export default function SangkwonTrendModal({ name, onClose }: Props) {
  const q = useQuery({
    queryKey: ["sangkwon-series", name],
    queryFn: () => fetchSangkwonSeries(name, 2019),
    enabled: !!name,
  });

  const charts = useMemo(() => {
    const data = q.data;
    if (!data) return [];
    return MAIN_CHART_METRICS.map((metric) => {
      const series = SANGKWON_KINDS.map((kind) => {
        const item = data.series.find((s) => s.asset_kind === kind && s.metric === metric && !s.floor_label);
        const byYear = new Map((item?.points ?? []).map((p) => [p.year, p.value]));
        return { kind, values: data.years.map((y) => byYear.get(y) ?? null) };
      });
      return { metric, series };
    });
  }, [q.data]);

  return (
    <DraggableModalShell
      open
      onClose={onClose}
      titleId="sangkwon-trend"
      title={`${name} 상권 추세`}
      subtitle="2019년 이후 연간값 · 임대료=평균×12(만원) · NOI=분기 합(만원) · 수익률=복리"
      usePortal
      defaultWidth={720}
      defaultHeight={640}
    >
      {q.isLoading && <p className="text-sm text-slate-500">불러오는 중…</p>}
      {q.data && (
        <div className="space-y-4">
          <p className="text-[11px] text-amber-700 dark:text-amber-300">{q.data.break_note}</p>
          <div className="flex flex-wrap gap-3 text-[11px]">
            {SANGKWON_KINDS.map((k) => (
              <span key={k} className="inline-flex items-center gap-1">
                <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: KIND_COLOR[k] }} />
                {SANGKWON_KIND_LABELS[k]}
              </span>
            ))}
          </div>
          {charts.map((c) => (
            <section key={c.metric}>
              <h3 className="text-xs font-semibold text-slate-700 dark:text-slate-200 inline-flex items-center gap-1">
                {SANGKWON_METRIC_LABELS[c.metric] ?? c.metric}
                {SANGKWON_METRIC_HELP[c.metric] ? (
                  <StatsGlossaryHelp termId={SANGKWON_METRIC_HELP[c.metric]} size="xs" />
                ) : null}
              </h3>
              <LineChart years={q.data.years} series={c.series} metric={c.metric} />
            </section>
          ))}
        </div>
      )}
    </DraggableModalShell>
  );
}
