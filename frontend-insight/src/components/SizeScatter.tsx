import type { Insight02ScatterPoint } from "../api/insightClient";

function olsLine(xs: number[], ys: number[]): { a: number; b: number } | null {
  const n = xs.length;
  if (n < 2 || n !== ys.length) return null;
  const mx = xs.reduce((s, v) => s + v, 0) / n;
  const my = ys.reduce((s, v) => s + v, 0) / n;
  let num = 0;
  let dx = 0;
  for (let i = 0; i < n; i++) {
    const vx = xs[i] - mx;
    num += vx * (ys[i] - my);
    dx += vx * vx;
  }
  if (dx <= 0) return null;
  const b = num / dx;
  return { a: my - b * mx, b };
}

export default function SizeScatter({
  points,
  a,
  b,
  xLabel,
  yLabel,
}: {
  points: Insight02ScatterPoint[];
  a: string;
  b: string;
  xLabel: string;
  yLabel: string;
}) {
  const w = 520;
  const h = 340;
  const pad = { l: 48, r: 12, t: 12, b: 36 };
  if (points.length < 2) {
    return <p className="text-sm text-slate-500">점이 부족합니다.</p>;
  }
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const dx = maxX - minX || 1;
  const dy = maxY - minY || 1;
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const toX = (v: number) => pad.l + ((v - minX) / dx) * innerW;
  const toY = (v: number) => pad.t + (1 - (v - minY) / dy) * innerH;
  const fit = olsLine(xs, ys);
  const x0 = minX;
  const x1 = maxX;
  const y0 = fit ? fit.a + fit.b * x0 : 0;
  const y1 = fit ? fit.a + fit.b * x1 : 0;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full max-w-[34rem] h-auto text-slate-400">
      <rect
        x={pad.l}
        y={pad.t}
        width={innerW}
        height={innerH}
        fill="transparent"
        className="stroke-slate-200 dark:stroke-slate-700"
      />
      {fit && (
        <line
          x1={toX(x0)}
          y1={toY(y0)}
          x2={toX(x1)}
          y2={toY(y1)}
          className="stroke-amber-600 dark:stroke-amber-400"
          strokeWidth={1.5}
        />
      )}
      {points.map((p) => (
        <circle
          key={p.code}
          cx={toX(p.x)}
          cy={toY(p.y)}
          r={2.2}
          className="fill-slate-500/55 dark:fill-slate-300/50"
        >
          <title>
            {p.name} · {a} {p.x_raw.toLocaleString("ko-KR")} · {b} {p.y_raw.toLocaleString("ko-KR")}
          </title>
        </circle>
      ))}
      <text x={w / 2} y={h - 8} textAnchor="middle" className="fill-current text-[10px]">
        {a} ({xLabel})
      </text>
      <text
        x={14}
        y={h / 2}
        textAnchor="middle"
        transform={`rotate(-90 14 ${h / 2})`}
        className="fill-current text-[10px]"
      >
        {b} ({yLabel})
      </text>
    </svg>
  );
}
