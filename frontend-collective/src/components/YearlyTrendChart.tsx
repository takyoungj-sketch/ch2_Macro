import type { YearlyStatPoint } from "../types";

const W = 420;
const H = 230;
const PAD_L = 28;
const PAD_R = 28;
const PAD_T = 44;
const PAD_B = 42;
const LABEL_MEAN_ABOVE = 10;
const LABEL_COUNT_BELOW = 12;
const COUNT_MARKER_STROKE = "#787f89";
const COUNT_DASH_LINE = "#94a3b8";

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

/** 연도별 평균 단가(꺾은선)·거래 건수(점선+점) — 토지 MatrixYearlyTrendChart 와 동일 형식 */
export default function YearlyTrendChart({ points }: { points: YearlyStatPoint[] }) {
  const sorted = [...points].sort((a, b) => a.year - b.year);
  if (sorted.length === 0) return null;

  const innerW = W - PAD_L - PAD_R;
  const innerH = H - PAD_T - PAD_B;
  const n = sorted.length;
  const lastI = Math.max(n - 1, 1);

  const countMax = Math.max(...sorted.map((r) => r.count), 1);
  const countTick = niceStep(countMax);
  const countAxisMax = Math.ceil(countMax / countTick) * countTick;

  const meanVals = sorted.map((r) => r.mean).filter((v): v is number => v != null && Number.isFinite(v));
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
  const meanLineRows = sorted.filter((r) => r.mean != null && Number.isFinite(r.mean));
  const meanPoints = meanLineRows
    .map((r) => {
      const idx = sorted.indexOf(r);
      return `${xAt(idx).toFixed(1)},${yMean(Number(r.mean)).toFixed(1)}`;
    })
    .join(" ");

  return (
    <div className="w-full" role="img" aria-label="연도별 평균 단가 및 거래 건수 추이">
      <p className="text-[10px] text-slate-500 mb-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5">
        <span className="inline-flex items-center gap-1 font-bold text-blue-600">
          <span className="inline-block w-3 h-0.5 bg-blue-600 rounded" aria-hidden />
          평균(만원/㎡)
        </span>
        <span className="inline-flex items-center gap-1">
          <svg width={22} height={10} viewBox="0 0 22 10" className="shrink-0 text-slate-500" aria-hidden>
            <line x1="1" y1="5" x2="14" y2="5" stroke={COUNT_DASH_LINE} strokeWidth="1.4" strokeDasharray="3 5" strokeOpacity={0.55} />
            <circle cx="17" cy="5" r="3" fill="#fff" stroke={COUNT_MARKER_STROKE} strokeWidth="1.6" />
          </svg>
          거래 건수
        </span>
      </p>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto max-h-[240px] text-slate-500" preserveAspectRatio="xMidYMid meet">
        {sorted.map((r, i) => (
          <text key={r.year} x={xAt(i)} y={H - 8} textAnchor="middle" className={`fill-slate-600 font-medium ${n > 6 ? "text-[7.5px]" : "text-[9px]"}`}>
            {r.year}
          </text>
        ))}
        {n >= 2 && (
          <polyline fill="none" stroke={COUNT_DASH_LINE} strokeWidth={1.25} strokeDasharray="3 5" strokeOpacity={0.48} points={countDashPoints} />
        )}
        {sorted.map((r, i) => (
          <circle key={`c-${r.year}`} cx={xAt(i)} cy={yCount(r.count)} r={3.5} fill="#fff" stroke={COUNT_MARKER_STROKE} strokeWidth={2} />
        ))}
        {sorted.map((r, i) => (
          <text key={`cl-${r.year}`} x={xAt(i)} y={yCount(r.count) + LABEL_COUNT_BELOW} textAnchor="middle" className="fill-slate-400" opacity={0.72} style={{ fontSize: "9px" }}>
            {r.count.toLocaleString("ko-KR")}
          </text>
        ))}
        {meanLineRows.length > 0 && (
          <>
            <polyline fill="none" stroke="#2563eb" strokeWidth={2} strokeLinejoin="round" points={meanPoints} />
            {meanLineRows.map((r) => {
              const idx = sorted.indexOf(r);
              return (
                <circle key={`m-${r.year}`} cx={xAt(idx)} cy={yMean(Number(r.mean))} r={3.5} fill="#fff" stroke="#2563eb" strokeWidth={2} />
              );
            })}
            {meanLineRows.map((r) => {
              const idx = sorted.indexOf(r);
              const cy = yMean(Number(r.mean));
              return (
                <text key={`ml-${r.year}`} x={xAt(idx)} y={cy - LABEL_MEAN_ABOVE} textAnchor="middle" className="fill-slate-800 font-semibold" style={{ fontSize: "10px" }}>
                  {formatMeanLabel(Number(r.mean))}
                </text>
              );
            })}
          </>
        )}
      </svg>
    </div>
  );
}
