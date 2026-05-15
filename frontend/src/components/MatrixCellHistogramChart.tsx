import type { MatrixCellHistogramResponse } from "../types";

const W = 520;
const H = 248;
const PAD_L = 40;
const PAD_R = 14;
const PAD_T = 16;
const PAD_B = 46;

function shortNum(v: number): string {
  if (!Number.isFinite(v)) return "—";
  if (Math.abs(v) >= 1000) return v.toLocaleString("ko-KR", { maximumFractionDigits: 0 });
  return v.toLocaleString("ko-KR", { maximumFractionDigits: 1 });
}

/** 서버에서 내려준 bin·count로 막대 히스토그램 (SVG) */
export default function MatrixCellHistogramChart({
  data,
}: {
  data: MatrixCellHistogramResponse;
}) {
  const bins = data.bins;
  if (bins.length === 0) return null;

  const maxC = Math.max(...bins.map((b) => b.count), 1);
  const innerW = W - PAD_L - PAD_R;
  const innerH = H - PAD_T - PAD_B;
  const n = bins.length;
  const gap = n > 24 ? 0.5 : n > 14 ? 1 : 2;
  const barW = Math.max((innerW - gap * (n - 1)) / n, 2);

  const lo = bins[0]!.bin_from;
  const hi = bins[bins.length - 1]!.bin_to;

  const labelEvery = n <= 10 ? 1 : n <= 20 ? 2 : Math.ceil(n / 6);

  return (
    <div className="w-full" role="img" aria-label="단가 분포 히스토그램">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto max-h-[260px] text-slate-500"
        preserveAspectRatio="xMidYMid meet"
      >
        <text x={PAD_L} y={12} className="fill-slate-600 text-[10px] font-medium">
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
            <text
              key={`l-${i}`}
              x={x}
              y={H - 8}
              textAnchor="middle"
              className="fill-slate-500"
              style={{ fontSize: n > 16 ? "6px" : "8px" }}
            >
              {shortNum(b.bin_from)}
            </text>
          );
        })}
        <text
          x={W / 2}
          y={H - 1}
          textAnchor="middle"
          className="fill-slate-400"
          style={{ fontSize: "9px" }}
        >
          만원/㎡ ({shortNum(lo)} ~ {shortNum(hi)})
        </text>
      </svg>
    </div>
  );
}
