import clsx from "clsx";

const SERIES_COLORS = [
  "#2563eb",
  "#dc2626",
  "#059669",
  "#d97706",
  "#7c3aed",
  "#0891b2",
  "#be185d",
  "#4f46e5",
];

export type GenericTrendPoint = {
  xLabel: string;
  xOrder: number;
  count: number;
  value?: number | null;
};

export type TrendSeries = {
  label: string;
  points: GenericTrendPoint[];
  color?: string;
};

export type RegionTrendMetric = "mean" | "median";

const W = 420;
const H = 240;
const PAD_L = 28;
const PAD_R = 28;
const PAD_T = 44;
const PAD_B = 42;
const LABEL_ABOVE = 10;

function formatPriceLabel(v: number): string {
  return Number(v).toLocaleString("ko-KR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
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

function metricValue(p: GenericTrendPoint): number | null {
  if (p.value == null || !Number.isFinite(p.value)) return null;
  return p.value;
}

/** 다중 지역 장기 추세 — 평균 또는 중앙값 (꺾은선) */
export default function MultiRegionTrendChart({
  series,
  metricLabel,
}: {
  series: TrendSeries[];
  metricLabel: string;
}) {
  const active = series.filter((s) => s.points.some((p) => metricValue(p) != null));
  if (active.length === 0) return null;

  const allXOrders = [...new Set(active.flatMap((s) => s.points.map((p) => p.xOrder)))].sort(
    (a, b) => a - b,
  );
  const xLabelByOrder = new Map<number, string>();
  for (const s of active) {
    for (const p of s.points) {
      if (!xLabelByOrder.has(p.xOrder)) xLabelByOrder.set(p.xOrder, p.xLabel);
    }
  }
  const n = allXOrders.length;
  const lastI = Math.max(n - 1, 1);
  const innerW = W - PAD_L - PAD_R;
  const innerH = H - PAD_T - PAD_B;

  const vals = active.flatMap((s) =>
    s.points.map((p) => metricValue(p)).filter((v): v is number => v != null && Number.isFinite(v)),
  );
  let vMin = Math.min(...vals);
  let vMax = Math.max(...vals);
  if (vMin === vMax) {
    vMin = vMin * 0.9;
    vMax = vMax * 1.1;
  }
  const tick = niceStep(vMax - vMin || vMax, 4);
  const axisMin = Math.floor(vMin / tick) * tick;
  const axisMax = Math.ceil(vMax / tick) * tick;

  const xAt = (order: number) => {
    const i = allXOrders.indexOf(order);
    return PAD_L + (n <= 1 ? innerW / 2 : (i / lastI) * innerW);
  };
  const yVal = (v: number) => PAD_T + innerH - ((v - axisMin) / (axisMax - axisMin || 1)) * innerH;

  return (
    <div className="w-full" role="img" aria-label={`다중 지역 ${metricLabel} 추이`}>
      <p className="text-[10px] text-slate-500 mb-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5">
        <span className="inline-flex items-center gap-1 font-medium text-slate-600">
          <span className="inline-block w-3 h-0.5 rounded bg-slate-500" aria-hidden />
          {metricLabel}
        </span>
        {active.map((s, idx) => {
          const color = s.color ?? SERIES_COLORS[idx % SERIES_COLORS.length];
          return (
            <span key={s.label} className="inline-flex items-center gap-1 font-medium" style={{ color }}>
              <span className="inline-block w-3 h-0.5 rounded" style={{ backgroundColor: color }} aria-hidden />
              {s.label}
            </span>
          );
        })}
      </p>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto max-h-[250px] text-slate-500"
        preserveAspectRatio="xMidYMid meet"
      >
        {allXOrders.map((order) => (
          <text
            key={order}
            x={xAt(order)}
            y={H - 8}
            textAnchor="middle"
            className={clsx("fill-slate-600 font-medium", n > 6 ? "text-[7px]" : "text-[8px]")}
          >
            {xLabelByOrder.get(order) ?? String(order)}
          </text>
        ))}
        {active.map((s, idx) => {
          const color = s.color ?? SERIES_COLORS[idx % SERIES_COLORS.length];
          const rows = s.points.filter((p) => metricValue(p) != null);
          const linePoints = rows
            .map((r) => `${xAt(r.xOrder).toFixed(1)},${yVal(Number(metricValue(r))).toFixed(1)}`)
            .join(" ");
          return (
            <g key={s.label}>
              {rows.length > 1 && (
                <polyline fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" points={linePoints} />
              )}
              {rows.map((r) => {
                const v = Number(metricValue(r));
                return (
                  <g key={`${s.label}-${r.xOrder}`}>
                    <circle cx={xAt(r.xOrder)} cy={yVal(v)} r={3.5} fill="#fff" stroke={color} strokeWidth={2} />
                    <text
                      x={xAt(r.xOrder)}
                      y={yVal(v) - LABEL_ABOVE}
                      textAnchor="middle"
                      className="fill-slate-800 font-semibold"
                      style={{ fontSize: n > 5 ? "8px" : "9px" }}
                    >
                      {formatPriceLabel(v)}
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
