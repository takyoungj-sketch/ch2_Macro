import type { MatrixCellHistogramResponse } from "../types";

const W = 520;
const H = 320;
const PAD_L = 40;
const PAD_R = 14;
const PAD_T = 72
const PAD_B = 44;
const BOX_TOP = 22;
const BOX_H = 16;

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
  const innerH = H - PAD_T - PAD_B;
  const n = bins.length;
  const innerW = Math.max(W - PAD_L - PAD_R, Math.max(0, n - 1) * 44);
  const chartW = PAD_L + PAD_R + innerW;
  const gap = n > 24 ? 0.5 : n > 14 ? 1 : 2;
  const barW = Math.max((innerW - gap * (n - 1)) / n, 2);

  const labelEvery = n <= 8 ? 1 : n <= 16 ? 2 : Math.ceil(n / 5);
  const tickFontPx = n > 20 ? 12 : n > 12 ? 13 : 14;
  const countFontPx = n > 16 ? 11 : 13;
  const plotW = n * barW + Math.max(0, n - 1) * gap;
  const xMin = bins[0].bin_from;
  const xMax = bins[n - 1].bin_to;
  const xPrice = (v: number) => {
    if (!(xMax > xMin)) return PAD_L + plotW / 2;
    const t = Math.min(1, Math.max(0, (v - xMin) / (xMax - xMin)));
    return PAD_L + t * plotW;
  };
  const xLo = xPrice(data.min_unit_price_per_sqm);
  const xQ1 = xPrice(data.p25_unit_price_per_sqm);
  const xMed = xPrice(data.median_unit_price_per_sqm);
  const xQ3 = xPrice(data.p75_unit_price_per_sqm);
  const xHi = xPrice(data.max_unit_price_per_sqm);
  const boxW = Math.max(xQ3 - xQ1, 1.5);
  const boxX = xQ3 - xQ1 < 1.5 ? xMed - boxW / 2 : xQ1;
  const whiskerY = BOX_TOP + BOX_H / 2;

  return (
    <div className="w-full overflow-x-auto" role="img" aria-label="단가 분포 히스토그램과 박스플롯">
      <svg
        viewBox={`0 0 ${chartW} ${H}`}
        className={`${chartW > W ? "h-auto shrink-0" : "w-full h-auto"} max-h-[340px] text-slate-500`}
        width={chartW > W ? chartW : undefined}
        preserveAspectRatio="xMidYMid meet"
      >
        <text x={PAD_L} y={14} className="fill-slate-700 dark:fill-slate-200 text-[13px] font-semibold">
          빈도 (건)
        </text>
        <line x1={xLo} y1={whiskerY} x2={xHi} y2={whiskerY} stroke="#f59e0b" strokeWidth={1.5} />
        <line x1={xLo} y1={BOX_TOP + 3} x2={xLo} y2={BOX_TOP + BOX_H - 3} stroke="#f59e0b" strokeWidth={1.5} />
        <line x1={xHi} y1={BOX_TOP + 3} x2={xHi} y2={BOX_TOP + BOX_H - 3} stroke="#f59e0b" strokeWidth={1.5} />
        <rect
          x={boxX}
          y={BOX_TOP}
          width={boxW}
          height={BOX_H}
          fill="#f59e0b"
          fillOpacity={0.28}
          stroke="#f59e0b"
          strokeWidth={1.25}
          rx={2}
        />
        <line x1={xMed} y1={BOX_TOP} x2={xMed} y2={BOX_TOP + BOX_H} stroke="#2563eb" strokeWidth={2} />
        {bins.map((b, i) => {
          const h = (b.count / maxC) * innerH;
          const x = PAD_L + i * (barW + gap);
          const y = PAD_T + innerH - h;
          return (
            <g key={`b-${i}`}>
              <rect
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
              {b.count > 0 && (
                <text
                  x={x + barW / 2}
                  y={y - 4}
                  textAnchor="middle"
                  className="fill-slate-800 dark:fill-white font-semibold"
                  style={{ fontSize: `${countFontPx}px` }}
                >
                  {b.count.toLocaleString("ko-KR")}
                </text>
              )}
            </g>
          );
        })}
        {bins.map((b, i) => {
          if (i % labelEvery !== 0 && i !== n - 1) return null;
          const x = PAD_L + i * (barW + gap) + barW / 2;
          return (
            <text
              key={`l-${i}`}
              x={x}
              y={H - 6}
              textAnchor="middle"
              className="fill-slate-800 dark:fill-white font-semibold"
              style={{ fontSize: `${tickFontPx}px` }}
            >
              {shortNum(b.bin_from)}
            </text>
          );
        })}
      </svg>
    </div>
  );
}
