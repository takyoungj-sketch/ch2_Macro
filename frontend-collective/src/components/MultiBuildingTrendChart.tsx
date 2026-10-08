import { useId } from "react";
import clsx from "clsx";

const SERIES_COLORS = ["#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed", "#0891b2", "#be185d", "#4f46e5"];
const QUARTILE_COLORS = ["#f59e0b", "#a78bfa", "#fb923c", "#38bdf8", "#a3e635", "#facc15", "#2dd4bf", "#fb7185"];

export type GenericTrendPoint = {
  xLabel: string;
  xOrder: number;
  count: number;
  mean?: number | null;
  median?: number | null;
  p25?: number | null;
  p75?: number | null;
};

export type TrendSeries = {
  label: string;
  points: GenericTrendPoint[];
  color?: string;
};

export type CohortTrendMetric = "mean" | "median" | "count";

const W = 420;
const H = 280;
const PAD_L = 28;
const PAD_R = 28;
const PAD_T = 56;
const PAD_B = 52;
const LABEL_ABOVE = 16;

function formatMeanLabel(v: number): string {
  return Number(v).toLocaleString("ko-KR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function formatCountLabel(v: number): string {
  return v.toLocaleString("ko-KR");
}

function niceStep(max: number, targetTicks = 4): number {
  if (max <= 0) return 1;
  const raw = max / targetTicks;
  const pow10 = 10 ** Math.floor(Math.log10(raw));
  const n = raw / pow10;
  let step = 1;
  if (n <= 1) step = 1;
  else if (n <= 2) step = 2;
  else if (n <= 5) step = 5;
  else step = 10;
  return step * pow10;
}

function finiteNum(v: number | null | undefined): v is number {
  return v != null && Number.isFinite(v);
}

function quartileBands(
  ordered: { x: number; lo?: number | null; hi?: number | null }[],
  yOf: (v: number) => number,
): { fill: string; lo: string; hi: string }[] {
  const segs: { x: number; lo: number; hi: number }[][] = [];
  let cur: { x: number; lo: number; hi: number }[] = [];
  for (const p of ordered) {
    if (finiteNum(p.lo) && finiteNum(p.hi)) cur.push({ x: p.x, lo: p.lo, hi: p.hi });
    else if (cur.length) {
      segs.push(cur);
      cur = [];
    }
  }
  if (cur.length) segs.push(cur);
  return segs
    .filter((s) => s.length >= 2)
    .map((s) => ({
      fill: `${s.map((p) => `${p.x.toFixed(1)},${yOf(p.hi).toFixed(1)}`).join(" ")} ${[...s]
        .reverse()
        .map((p) => `${p.x.toFixed(1)},${yOf(p.lo).toFixed(1)}`)
        .join(" ")}`,
      hi: s.map((p) => `${p.x.toFixed(1)},${yOf(p.hi).toFixed(1)}`).join(" "),
      lo: s.map((p) => `${p.x.toFixed(1)},${yOf(p.lo).toFixed(1)}`).join(" "),
    }));
}

function metricValue(p: GenericTrendPoint, metric: CohortTrendMetric): number | null {
  if (metric === "count") return p.count;
  if (metric === "median") {
    if (p.median == null || !Number.isFinite(p.median)) return null;
    return p.median;
  }
  if (p.mean == null || !Number.isFinite(p.mean)) return null;
  return p.mean;
}

/** 다중 단지 추이 비교 — 평균 또는 거래 건수 (꺾은선 1종) */
export default function MultiBuildingTrendChart({
  series,
  metric = "mean",
  showQuartiles = false,
}: {
  series: TrendSeries[];
  metric?: CohortTrendMetric;
  /** 중앙값 모드에서 25%·75% 띠. 기본은 끔 */
  showQuartiles?: boolean;
}) {
  const clipId = useId().replace(/:/g, "");
  const active = series.filter((s) => s.points.some((p) => metricValue(p, metric) != null));
  if (active.length === 0) return null;

  const allXOrders = [...new Set(active.flatMap((s) => s.points.map((p) => p.xOrder)))].sort((a, b) => a - b);
  const xLabelByOrder = new Map<number, string>();
  for (const s of active) {
    for (const p of s.points) {
      if (!xLabelByOrder.has(p.xOrder)) xLabelByOrder.set(p.xOrder, p.xLabel);
    }
  }
  const n = allXOrders.length;
  const lastI = Math.max(n - 1, 1);
  const innerW = Math.max(W - PAD_L - PAD_R, Math.max(0, n - 1) * 56);
  const chartW = PAD_L + PAD_R + innerW;
  const innerH = H - PAD_T - PAD_B;

  const showBand =
    showQuartiles &&
    metric === "median" &&
    active.some((s) => s.points.some((p) => finiteNum(p.p25) && finiteNum(p.p75)));
  const vals = active.flatMap((s) =>
    s.points.flatMap((p) => {
      const out: number[] = [];
      const v = metricValue(p, metric);
      if (v != null) out.push(v);
      return out;
    }),
  );
  let vMin = Math.min(...vals);
  let vMax = Math.max(...vals);
  if (vMin === vMax) {
    vMin = metric === "count" ? 0 : vMin * 0.9;
    vMax = metric === "count" ? Math.max(vMax, 1) : vMax * 1.1;
  }
  const tick = niceStep(vMax - vMin || vMax, 4);
  const axisMin = metric === "count" ? 0 : Math.floor(vMin / tick) * tick;
  const axisMax = Math.ceil(vMax / tick) * tick;

  const xAt = (order: number) => {
    const i = allXOrders.indexOf(order);
    return PAD_L + (n <= 1 ? innerW / 2 : (i / lastI) * innerW);
  };
  const yVal = (v: number) => PAD_T + innerH - ((v - axisMin) / (axisMax - axisMin || 1)) * innerH;

  const formatLabel = metric === "count" ? formatCountLabel : formatMeanLabel;
  const metricLabel =
    metric === "count" ? "거래 건수" : metric === "median" ? "중앙값(만원/㎡)" : "평균(만원/㎡)";

  return (
    <div className="w-full overflow-x-auto" role="img" aria-label={`다중 단지 ${metricLabel} 추이`}>
      <p className="text-xs text-slate-500 dark:text-slate-400 mb-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5">
        <span className="inline-flex items-center gap-1 font-medium text-slate-600 dark:text-slate-300">
          <span
            className="inline-block w-3 h-0.5 rounded bg-slate-500"
            aria-hidden
          />
          {metricLabel}
        </span>
        {showBand && <span className="font-medium text-slate-500 dark:text-slate-400">25%·75%</span>}
        {active.map((s, idx) => {
          const color = s.color ?? SERIES_COLORS[idx % SERIES_COLORS.length];
          const quartileColor = QUARTILE_COLORS[idx % QUARTILE_COLORS.length];
          return (
            <span key={s.label} className="inline-flex items-center gap-1 font-medium" style={{ color }}>
              <span className="inline-block w-3 h-0.5 rounded" style={{ backgroundColor: color }} aria-hidden />
              {showBand && (
                <span className="inline-block w-3 h-0.5 rounded" style={{ backgroundColor: quartileColor }} aria-hidden />
              )}
              {s.label}
            </span>
          );
        })}
      </p>
      <svg
        viewBox={`0 0 ${chartW} ${H}`}
        className={`${chartW > W ? "h-auto shrink-0" : "w-full h-auto"} max-h-[310px] text-slate-500`}
        width={chartW > W ? chartW : undefined}
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <clipPath id={clipId}>
            <rect x={PAD_L} y={PAD_T} width={innerW} height={innerH} />
          </clipPath>
        </defs>
        {allXOrders.map((order) => (
          <text
            key={order}
            x={xAt(order)}
            y={H - 8}
            textAnchor="middle"
            className={clsx("fill-slate-700 dark:fill-slate-200 font-semibold", n > 6 ? "text-[12px]" : "text-[13px]")}
          >
            {xLabelByOrder.get(order) ?? String(order)}
          </text>
        ))}
        {active.map((s, idx) => {
          const color = s.color ?? SERIES_COLORS[idx % SERIES_COLORS.length];
          const quartileColor = QUARTILE_COLORS[idx % QUARTILE_COLORS.length];
          const rows = s.points.filter((p) => metricValue(p, metric) != null);
          const linePoints = rows
            .map((r) => `${xAt(r.xOrder).toFixed(1)},${yVal(Number(metricValue(r, metric))).toFixed(1)}`)
            .join(" ");
          const bands = showBand
              ? quartileBands(
                  [...s.points]
                    .sort((a, b) => a.xOrder - b.xOrder)
                    .map((p) => ({ x: xAt(p.xOrder), lo: p.p25, hi: p.p75 })),
                  yVal,
                )
              : [];
          return (
            <g key={s.label}>
              {rows.length > 1 && (
                <polyline fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" points={linePoints} />
              )}
              <g clipPath={`url(#${clipId})`}>
                {bands.map((b, bi) => (
                  <g key={`${s.label}-band-${bi}`}>
                    <polyline fill="none" stroke={quartileColor} strokeWidth={1.75} strokeLinejoin="round" points={b.hi} />
                    <polyline fill="none" stroke={quartileColor} strokeWidth={1.75} strokeLinejoin="round" points={b.lo} />
                  </g>
                ))}
              </g>
              {rows.map((r) => {
                const v = Number(metricValue(r, metric));
                return (
                  <g key={`${s.label}-${r.xOrder}`}>
                    <circle cx={xAt(r.xOrder)} cy={yVal(v)} r={3.5} fill="#fff" stroke={color} strokeWidth={2} />
                    <text
                      x={xAt(r.xOrder)}
                      y={yVal(v) - LABEL_ABOVE - (idx % 3) * 14}
                      textAnchor="middle"
                      className="fill-slate-900 dark:fill-white font-bold"
                      style={{ fontSize: n > 5 ? "14px" : "15px" }}
                    >
                      {formatLabel(v)}
                    </text>
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
