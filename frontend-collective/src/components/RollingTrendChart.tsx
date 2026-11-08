import { useId } from "react";
import type { RollingStatPoint } from "../types";
import type { LongTermPriceMetric } from "./LongTermMetricToggle";

const W = 420;
const H = 270;
const PAD_L = 28;
const PAD_R = 28;
const PAD_T = 56;
const PAD_B = 52;
const LABEL_MEAN_ABOVE = 16;
const LABEL_COUNT_BELOW = 18;
const COUNT_MARKER_STROKE = "#787f89";
const COUNT_DASH_LINE = "#94a3b8";
const PRICE_LINE = "#2563eb";
const QUARTILE_LINE = "#f59e0b";

function formatMeanLabel(v: number): string {
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

function finiteNum(v: number | null | undefined): v is number {
  return v != null && Number.isFinite(v);
}

function priceOf(p: RollingStatPoint, metric: LongTermPriceMetric): number | null {
  const v = metric === "median" ? p.median : p.mean;
  return finiteNum(v) ? v : null;
}

function quartileBands(
  ordered: { x: number; lo?: number | null; hi?: number | null }[],
  yOf: (v: number) => number,
): { lo: string; hi: string }[] {
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
  return segs.map((seg) => ({
    lo: seg.map((p) => `${p.x.toFixed(1)},${yOf(p.lo).toFixed(1)}`).join(" "),
    hi: seg.map((p) => `${p.x.toFixed(1)},${yOf(p.hi).toFixed(1)}`).join(" "),
  }));
}

/** 12개월 롤링 버킷 추이 — x축 YY.MM~YY.MM */
export default function RollingTrendChart({
  points,
  metric = "mean",
  showQuartiles = false,
}: {
  points: RollingStatPoint[];
  metric?: LongTermPriceMetric;
  showQuartiles?: boolean;
}) {
  const clipId = useId().replace(/:/g, "");
  const sorted = [...points].sort((a, b) => a.bucket_index - b.bucket_index);
  if (sorted.length === 0) return null;

  const innerW = Math.max(W - PAD_L - PAD_R, Math.max(0, sorted.length - 1) * 56);
  const chartW = PAD_L + PAD_R + innerW;
  const innerH = H - PAD_T - PAD_B;
  const n = sorted.length;
  const lastI = Math.max(n - 1, 1);

  const countMax = Math.max(...sorted.map((r) => r.count), 1);
  const countTick = niceStep(countMax);
  const countAxisMax = Math.ceil(countMax / countTick) * countTick;

  const showBand = showQuartiles && metric === "median" && sorted.some((r) => finiteNum(r.p25) && finiteNum(r.p75));
  const meanVals = sorted.flatMap((r) => {
    const vals: number[] = [];
    const price = priceOf(r, metric);
    if (price != null) vals.push(price);
    if (showBand && finiteNum(r.p25)) vals.push(r.p25);
    if (showBand && finiteNum(r.p75)) vals.push(r.p75);
    return vals;
  });
  const hasMean = meanVals.length > 0;
  let meanMin = hasMean ? Math.min(...meanVals) : 0;
  let meanMax = hasMean ? Math.max(...meanVals) : 1;
  if (hasMean && meanMin === meanMax) {
    meanMin *= 0.9;
    meanMax *= 1.1;
  }
  const meanTick = hasMean ? niceStep(meanMax - meanMin || meanMax, 4) : 1;
  const meanAxisMin = hasMean ? Math.floor(meanMin / meanTick) * meanTick : 0;
  const meanAxisMax = hasMean ? Math.ceil(meanMax / meanTick) * meanTick : 1;

  const xAt = (i: number) => PAD_L + (n <= 1 ? innerW / 2 : (i / lastI) * innerW);
  const yCount = (c: number) => PAD_T + innerH - (c / countAxisMax) * innerH;
  const yMean = (m: number) => PAD_T + innerH - ((m - meanAxisMin) / (meanAxisMax - meanAxisMin || 1)) * innerH;

  const countDashPoints = sorted.map((r, i) => `${xAt(i).toFixed(1)},${yCount(r.count).toFixed(1)}`).join(" ");
  const priceLabel = metric === "median" ? "중앙값" : "평균";
  const meanLineRows = sorted.filter((r) => priceOf(r, metric) != null);
  const meanPoints = meanLineRows
    .map((r) => {
      const idx = sorted.indexOf(r);
      return `${xAt(idx).toFixed(1)},${yMean(Number(priceOf(r, metric))).toFixed(1)}`;
    })
    .join(" ");

  return (
    <div className="w-full overflow-x-auto" role="img" aria-label={`롤링 구간별 ${priceLabel} 단가 및 거래 건수 추이`}>
      <p className="text-xs text-slate-500 mb-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5">
        <span className="inline-flex items-center gap-1 font-bold text-blue-600">
          <span className="inline-block w-3 h-0.5 bg-blue-600 rounded" aria-hidden />
          {priceLabel}(만원/㎡)
        </span>
        {showBand && (
          <span className="inline-flex items-center gap-1 font-medium" style={{ color: QUARTILE_LINE }}>
            <span className="inline-block w-3 h-0.5 rounded" style={{ backgroundColor: QUARTILE_LINE }} aria-hidden />
            25%·75%
          </span>
        )}
        <span className="inline-flex items-center gap-1">
          <svg width={22} height={10} viewBox="0 0 22 10" className="shrink-0 text-slate-500" aria-hidden>
            <line x1="1" y1="5" x2="14" y2="5" stroke={COUNT_DASH_LINE} strokeWidth="1.4" strokeDasharray="3 5" strokeOpacity={0.55} />
            <circle cx="17" cy="5" r="3" fill="#fff" stroke={COUNT_MARKER_STROKE} strokeWidth="1.6" />
          </svg>
          거래 건수
        </span>
      </p>
      <svg
        viewBox={`0 0 ${chartW} ${H}`}
        className={`${chartW > W ? "h-auto shrink-0" : "w-full h-auto"} max-h-[300px] text-slate-500`}
        width={chartW > W ? chartW : undefined}
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <clipPath id={clipId}>
            <rect x={PAD_L} y={PAD_T} width={innerW} height={innerH} />
          </clipPath>
        </defs>
        {sorted.map((r, i) => (
          <text
            key={r.bucket_index}
            x={xAt(i)}
            y={H - 8}
            textAnchor="middle"
            fontSize={n > 4 ? 8 : 9}
            className="fill-slate-700 dark:fill-slate-200 font-semibold"
          >
            {r.label}
          </text>
        ))}
        {n >= 2 && (
          <polyline fill="none" stroke={COUNT_DASH_LINE} strokeWidth={1.25} strokeDasharray="3 5" strokeOpacity={0.48} points={countDashPoints} />
        )}
        {sorted.map((r, i) => (
          <circle key={`c-${r.bucket_index}`} cx={xAt(i)} cy={yCount(r.count)} r={3.5} fill="#fff" stroke={COUNT_MARKER_STROKE} strokeWidth={2} />
        ))}
        {sorted.map((r, i) => (
          <text
            key={`cl-${r.bucket_index}`}
            x={xAt(i)}
            y={yCount(r.count) + LABEL_COUNT_BELOW}
            textAnchor="middle"
            className="fill-slate-700 dark:fill-slate-200 font-semibold"
            opacity={0.95}
            style={{ fontSize: n > 4 ? "14px" : "15px" }}
          >
            {r.count.toLocaleString("ko-KR")}
          </text>
        ))}
        {meanLineRows.length > 0 && (
          <>
            <polyline fill="none" stroke={PRICE_LINE} strokeWidth={2} strokeLinejoin="round" points={meanPoints} />
            {showBand && (
              <g clipPath={`url(#${clipId})`}>
                {quartileBands(
                  sorted.map((r, i) => ({ x: xAt(i), lo: r.p25, hi: r.p75 })),
                  yMean,
                ).map((b, bi) => (
                  <g key={`band-${bi}`}>
                    <polyline fill="none" stroke={QUARTILE_LINE} strokeWidth={1.75} strokeLinejoin="round" points={b.hi} />
                    <polyline fill="none" stroke={QUARTILE_LINE} strokeWidth={1.75} strokeLinejoin="round" points={b.lo} />
                  </g>
                ))}
              </g>
            )}
            {meanLineRows.map((r) => {
              const idx = sorted.indexOf(r);
              return (
                <circle
                  key={`m-${r.bucket_index}`}
                  cx={xAt(idx)}
                  cy={yMean(Number(priceOf(r, metric)))}
                  r={3.5}
                  fill="#fff"
                  stroke={PRICE_LINE}
                  strokeWidth={2}
                />
              );
            })}
            {meanLineRows.map((r) => {
              const idx = sorted.indexOf(r);
              const cy = yMean(Number(priceOf(r, metric)));
              return (
                <text
                  key={`ml-${r.bucket_index}`}
                  x={xAt(idx)}
                  y={cy - LABEL_MEAN_ABOVE}
                  textAnchor="middle"
                  className="fill-slate-900 dark:fill-white font-bold"
                  style={{ fontSize: n > 4 ? "14px" : "15px" }}
                >
                  {formatMeanLabel(Number(priceOf(r, metric)))}
                </text>
              );
            })}
          </>
        )}
      </svg>
    </div>
  );
}
