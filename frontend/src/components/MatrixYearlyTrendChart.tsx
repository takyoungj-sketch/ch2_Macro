import type { MatrixYearlyStat } from "../types";

const W = 420;
const H = 230;
const PAD_L = 28;
const PAD_R = 28;
const PAD_T = 44;
const PAD_B = 36;

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

const COUNT_LINE = "#94a3b8";
const COUNT_MARKER_STROKE = "#787f89";

/** 연도별 평균 단가·거래 건수 꺾은선 (SVG, 이중 Y축 좌 평균 · 우 건수; 축 숫자는 표시 안 함) */
export default function MatrixYearlyTrendChart({ rows }: { rows: MatrixYearlyStat[] }) {
  const sorted = [...rows].sort((a, b) => a.year - b.year);
  if (sorted.length === 0) return null;

  const innerW = W - PAD_L - PAD_R;
  const innerH = H - PAD_T - PAD_B;

  const yearMin = sorted[0]!.year;
  const yearMax = sorted[sorted.length - 1]!.year;
  const yearSpan = Math.max(yearMax - yearMin, 1);

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

  const xAt = (y: number) => PAD_L + ((y - yearMin) / yearSpan) * innerW;
  const yCount = (c: number) =>
    PAD_T + innerH - (c / countAxisMax) * innerH;
  const yMean = (m: number) =>
    PAD_T +
    innerH -
    ((m - meanAxisMin) / (meanAxisMax - meanAxisMin || 1)) * innerH;

  const countPoints = sorted
    .map((r) => `${xAt(r.year).toFixed(1)},${yCount(r.count).toFixed(1)}`)
    .join(" ");

  const meanLineRows = sorted.filter(
    (r) => r.mean_unit_price_per_sqm != null && Number.isFinite(r.mean_unit_price_per_sqm)
  );
  const meanPoints = meanLineRows
    .map(
      (r) =>
        `${xAt(r.year).toFixed(1)},${yMean(Number(r.mean_unit_price_per_sqm)).toFixed(1)}`
    )
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
    <div className="w-full" role="img" aria-label="연도별 평균 단가 및 거래 건수 추이 그래프">
      <p className="text-[10px] text-slate-500 mb-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5">
        <span className="inline-flex items-center gap-1 font-bold text-blue-600">
          <span className="inline-block w-3 h-0.5 bg-blue-600 rounded" aria-hidden />
          평균(만원/㎡)
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-3 h-0.5 rounded bg-slate-400" aria-hidden />
          거래 건수
        </span>
      </p>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto max-h-[240px] text-slate-500"
        preserveAspectRatio="xMidYMid meet"
      >
        {/* 수평 격자: 평균(좌) 눈금 기준 */}
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

        {sorted.map((r) => (
          <text
            key={`xl-${r.year}`}
            x={xAt(r.year)}
            y={H - 10}
            textAnchor="middle"
            className="fill-slate-600 text-[10px] font-medium"
          >
            {r.year}
          </text>
        ))}

        {/* 꺾은선: 건수 (회색) */}
        <polyline
          fill="none"
          stroke={COUNT_LINE}
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
          points={countPoints}
        />
        {sorted.map((r) => (
          <circle
            key={`c-${r.year}`}
            cx={xAt(r.year)}
            cy={yCount(r.count)}
            r={3.5}
            fill="#fff"
            stroke={COUNT_MARKER_STROKE}
            strokeWidth={2}
          />
        ))}

        {sorted.map((r) => {
          const xc = xAt(r.year);
          const yc = yCount(r.count);
          return (
            <text
              key={`cl-${r.year}`}
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

        {/* 꺾은선: 평균 (파랑) */}
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
            {meanLineRows.map((r) => (
              <circle
                key={`mpt-${r.year}`}
                cx={xAt(r.year)}
                cy={yMean(Number(r.mean_unit_price_per_sqm))}
                r={3.5}
                fill="#fff"
                stroke="#2563eb"
                strokeWidth={2}
              />
            ))}
            {meanLineRows.map((r) => {
              const ym = Number(r.mean_unit_price_per_sqm);
              const cy = yMean(ym);
              return (
                <text
                  key={`ml-${r.year}`}
                  x={xAt(r.year)}
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
