import type { HistogramBin } from "../types";

const W = 520;
const H = 270;
const PAD_L = 40;
const PAD_R = 14;
const PAD_T = 22;
const PAD_B = 38;

function shortNum(v: number): string {
  if (!Number.isFinite(v)) return "—";
  if (Math.abs(v) >= 1000) return v.toLocaleString("ko-KR", { maximumFractionDigits: 0 });
  return v.toLocaleString("ko-KR", { maximumFractionDigits: 1 });
}

/** 단가 분포 히스토그램 — 토지 MatrixCellHistogramChart 와 동일 형식 */
export default function HistogramChart({ bins }: { bins: HistogramBin[] }) {
  if (bins.length === 0) return null;

  const maxC = Math.max(...bins.map((b) => b.count), 1);
  const innerW = W - PAD_L - PAD_R;
  const innerH = H - PAD_T - PAD_B;
  const n = bins.length;
  const gap = n > 24 ? 0.5 : n > 14 ? 1 : 2;
  const barW = Math.max((innerW - gap * (n - 1)) / n, 2);
  const labelEvery = n <= 8 ? 1 : n <= 16 ? 2 : Math.ceil(n / 5);
  const tickFontPx = n > 20 ? 10 : n > 12 ? 11 : 12;

  return (
    <div className="w-full" role="img" aria-label="단가 분포 히스토그램">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto max-h-[300px] text-slate-500" preserveAspectRatio="xMidYMid meet">
        <text x={PAD_L} y={16} className="fill-slate-700 dark:fill-slate-200 text-[11px] font-semibold">
          빈도 (건)
        </text>
        {bins.map((b, i) => {
          const h = (b.count / maxC) * innerH;
          const x = PAD_L + i * (barW + gap);
          const y = PAD_T + innerH - h;
          return (
            <rect
              key={`b-${i}`}
              x={x}
              y={y}
              width={barW}
              height={Math.max(h, b.count > 0 ? 1.5 : 0)}
              fill="#93c5fd"
              stroke="#2563eb"
              strokeOpacity={0.55}
              strokeWidth={0.6}
              rx={1}
            />
          );
        })}
        {bins.map((b, i) => {
          if (i % labelEvery !== 0 && i !== n - 1) return null;
          const x = PAD_L + i * (barW + gap) + barW / 2;
          return (
            <text key={`l-${i}`} x={x} y={H - 8} textAnchor="middle" className="fill-slate-800 dark:fill-white font-semibold" style={{ fontSize: `${tickFontPx}px` }}>
              {shortNum(b.lo)}
            </text>
          );
        })}
      </svg>
    </div>
  );
}
