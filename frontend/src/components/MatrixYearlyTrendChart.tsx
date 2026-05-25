import type { MatrixYearlyStat } from "../types";
import { formatMatrixBucketAxisLabel } from "../utils/matrixYearlyLabels";

const W = 420;
const H = 230;
const PAD_L = 28;
const PAD_R = 28;
const PAD_T = 44;
const PAD_B = 42;

const LABEL_MEAN_ABOVE = 10;
const LABEL_COUNT_BELOW = 12;

function formatMeanLabel(v: number): string {
  return Number(v).toLocaleString("ko-KR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
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

const COUNT_MARKER_STROKE = "#787f89";
const COUNT_DASH_LINE = "#94a3b8";

function rowSortKey(r: MatrixYearlyStat): number {
  if (r.bucket_index != null && Number.isFinite(r.bucket_index)) return r.bucket_index;
  if (r.year != null && Number.isFinite(r.year)) return r.year;
  return 0;
}

function rowKey(r: MatrixYearlyStat, i: number): string {
  if (r.bucket_index != null) return `b${r.bucket_index}`;
  if (r.year != null) return `y${r.year}`;
  return `i${i}`;
}

/** 연도·또는 롤링 구간별 평균 단가(꺾은선)·거래 건수(점선+점) */
export default function MatrixYearlyTrendChart({ rows }: { rows: MatrixYearlyStat[] }) {
  const sorted = [...rows].sort((a, b) => rowSortKey(a) - rowSortKey(b));
  if (sorted.length === 0) return null;

  const innerW = W - PAD_L - PAD_R;
  const innerH = H - PAD_T - PAD_B;
  const n = sorted.length;
  const lastI = Math.max(n - 1, 1);

  const countMax = Math.max(...sorted.map((r) => r.count), 1);
  const countTick = niceStep(countMax);
  const countAxisMax = Math.ceil(countMax / countTick) * countTick;

  const meanVals = sorted
    .map((r) => r.mean_unit_price_per_sqm)
    .filter((v): v is number => v != null && Number.isFinite(v));
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
  const yMean = (m: number) =>
    PAD_T +
    innerH -
    ((m - meanAxisMin) / (meanAxisMax - meanAxisMin || 1)) * innerH;

  const countDashPoints = sorted
    .map((r, i) => `${xAt(i).toFixed(1)},${yCount(r.count).toFixed(1)}`)
    .join(" ");

  const meanLineRows = sorted.filter(
    (r) => r.mean_unit_price_per_sqm != null && Number.isFinite(r.mean_unit_price_per_sqm)
  );
  const meanPoints = meanLineRows
    .map((r) => {
      const idx = sorted.indexOf(r);
      return `${xAt(idx).toFixed(1)},${yMean(Number(r.mean_unit_price_per_sqm)).toFixed(1)}`;
    })
    .join(" ");

  const countTicks: number[] = [];
  for (let v = 0; v <= countAxisMax + 1e-9; v += countTick) {
    countTicks.push(v);
  }

  const meanTicks: number[] = [];
  if (hasMean) {
    for (let v = meanAxisMin; v <= meanAxisMax + 1e-9; v += meanTick) {
      meanTicks.push(v);
    }
  }

  return (
    <div className="w-full" role="img" aria-label="구간별 평균 단가 및 거래 건수 추이 그래프">
      <p className="text-[10px] text-slate-500 mb-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5">
        <span className="inline-flex items-center gap-1 font-bold text-blue-600">
          <span className="inline-block w-3 h-0.5 bg-blue-600 rounded" aria-hidden />
          평균(만원/㎡)
        </span>
        <span className="inline-flex items-center gap-1">
          <svg width={22} height={10} viewBox="0 0 22 10" className="shrink-0 text-slate-500" aria-hidden>
            <line
              x1="1"
              y1="5"
              x2="14"
              y2="5"
              stroke={COUNT_DASH_LINE}
              strokeWidth="1.4"
              strokeDasharray="3 5"
              strokeOpacity={0.55}
              strokeLinecap="round"
            />
            <circle cx="17" cy="5" r="3" fill="#fff" stroke={COUNT_MARKER_STROKE} strokeWidth="1.6" />
          </svg>
          거래 건수
        </span>
      </p>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto max-h-[240px] text-slate-500"
        preserveAspectRatio="xMidYMid meet"
      >
        {hasMean &&
          meanTicks.map((v) => {
            const y = yMean(v);
            if (y < PAD_T - 1 || y > H - PAD_B + 1) return null;
            return (
              <line
                key={`grid-${v}`}
                x1={PAD_L}
                y1={y}
                x2={W - PAD_R}
                y2={y}
                stroke="currentColor"
                strokeOpacity={0.14}
                strokeWidth={1}
              />
            );
          })}
        {!hasMean &&
          countTicks.map((v) => {
            const y = yCount(v);
            return (
              <line
                key={`grid-c-${v}`}
                x1={PAD_L}
                y1={y}
                x2={W - PAD_R}
                y2={y}
                stroke="currentColor"
                strokeOpacity={0.14}
                strokeWidth={1}
              />
            );
          })}

        {sorted.map((r, i) => (
          <text
            key={`xl-${rowKey(r, i)}`}
            x={xAt(i)}
            y={H - 8}
            textAnchor="middle"
            className={`fill-slate-600 font-medium ${n > 6 ? "text-[7.5px]" : "text-[9px]"}`}
          >
            {formatMatrixBucketAxisLabel(r)}
          </text>
        ))}

        {n >= 2 && (
          <polyline
            fill="none"
            stroke={COUNT_DASH_LINE}
            strokeWidth={1.25}
            strokeDasharray="3 5"
            strokeOpacity={0.48}
            strokeLinejoin="round"
            strokeLinecap="round"
            points={countDashPoints}
          />
        )}
        {sorted.map((r, i) => (
          <circle
            key={`c-${rowKey(r, i)}`}
            cx={xAt(i)}
            cy={yCount(r.count)}
            r={3.5}
            fill="#fff"
            stroke={COUNT_MARKER_STROKE}
            strokeWidth={2}
          />
        ))}

        {sorted.map((r, i) => {
          const xc = xAt(i);
          const yc = yCount(r.count);
          return (
            <text
              key={`cl-${rowKey(r, i)}`}
              x={xc}
              y={yc + LABEL_COUNT_BELOW}
              textAnchor="middle"
              dominantBaseline="hanging"
              className="fill-slate-400"
              opacity={0.72}
              style={{ fontSize: "9px" }}
            >
              {r.count.toLocaleString("ko-KR")}
            </text>
          );
        })}

        {meanLineRows.length > 0 && (
          <>
            <polyline
              fill="none"
              stroke="#2563eb"
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
              points={meanPoints}
            />
            {meanLineRows.map((r) => {
              const idx = sorted.indexOf(r);
              return (
                <circle
                  key={`mpt-${rowKey(r, idx)}`}
                  cx={xAt(idx)}
                  cy={yMean(Number(r.mean_unit_price_per_sqm))}
                  r={3.5}
                  fill="#fff"
                  stroke="#2563eb"
                  strokeWidth={2}
                />
              );
            })}
            {meanLineRows.map((r) => {
              const ym = Number(r.mean_unit_price_per_sqm);
              const idx = sorted.indexOf(r);
              const cy = yMean(ym);
              return (
                <text
                  key={`ml-${rowKey(r, idx)}`}
                  x={xAt(idx)}
                  y={cy - LABEL_MEAN_ABOVE}
                  textAnchor="middle"
                  dominantBaseline="auto"
                  className="fill-slate-800 text-[10px] font-semibold tracking-tight"
                  style={{ fontSize: "10px" }}
                >
                  {formatMeanLabel(ym)}
                </text>
              );
            })}
          </>
        )}
      </svg>
    </div>
  );
}
