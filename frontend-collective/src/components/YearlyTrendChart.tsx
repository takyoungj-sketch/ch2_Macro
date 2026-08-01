import type { YearlyStatPoint } from "../types";
import type { LongTermPriceMetric } from "./LongTermMetricToggle";

const W = 420;
const H = 270;
const PAD_L = 28;
const PAD_R = 28;
const PAD_T = 52;
const PAD_B = 48;
const LABEL_PRICE_ABOVE = 13;
const LABEL_COUNT_BELOW = 15;
const COUNT_MARKER_STROKE = "#787f89";
const COUNT_DASH_LINE = "#94a3b8";

function formatPriceLabel(v: number): string {
  return Number(v).toLocaleString("ko-KR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function priceValue(p: YearlyStatPoint, metric: LongTermPriceMetric): number | null {
  const v = metric === "median" ? p.median : p.mean;
  return v != null && Number.isFinite(v) ? v : null;
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

/** 연도별 평균·중앙값 단가(꺾은선)·거래 건수(점선+점) */
export default function YearlyTrendChart({
  points,
  metric = "median",
}: {
  points: YearlyStatPoint[];
  metric?: LongTermPriceMetric;
}) {
  const sorted = [...points].sort((a, b) => a.year - b.year);
  if (sorted.length === 0) return null;

  const priceLabel = metric === "median" ? "중앙값" : "평균";
  const innerW = W - PAD_L - PAD_R;
  const innerH = H - PAD_T - PAD_B;
  const n = sorted.length;
  const lastI = Math.max(n - 1, 1);

  const countMax = Math.max(...sorted.map((r) => r.count), 1);
  const countTick = niceStep(countMax);
  const countAxisMax = Math.ceil(countMax / countTick) * countTick;

  const priceVals = sorted.map((r) => priceValue(r, metric)).filter((v): v is number => v != null);
  const hasPrice = priceVals.length > 0;
  let priceMin = hasPrice ? Math.min(...priceVals) : 0;
  let priceMax = hasPrice ? Math.max(...priceVals) : 1;
  if (hasPrice && priceMin === priceMax) {
    priceMin *= 0.9;
    priceMax *= 1.1;
  }
  const priceTick = hasPrice ? niceStep(priceMax - priceMin || priceMax, 4) : 1;
  const priceAxisMin = hasPrice ? Math.floor(priceMin / priceTick) * priceTick : 0;
  const priceAxisMax = hasPrice ? Math.ceil(priceMax / priceTick) * priceTick : 1;

  const xAt = (i: number) => PAD_L + (n <= 1 ? innerW / 2 : (i / lastI) * innerW);
  const yCount = (c: number) => PAD_T + innerH - (c / countAxisMax) * innerH;
  const yPrice = (m: number) => PAD_T + innerH - ((m - priceAxisMin) / (priceAxisMax - priceAxisMin || 1)) * innerH;

  const countDashPoints = sorted.map((r, i) => `${xAt(i).toFixed(1)},${yCount(r.count).toFixed(1)}`).join(" ");
  const priceLineRows = sorted.filter((r) => priceValue(r, metric) != null);
  const pricePoints = priceLineRows
    .map((r) => {
      const idx = sorted.indexOf(r);
      return `${xAt(idx).toFixed(1)},${yPrice(Number(priceValue(r, metric))).toFixed(1)}`;
    })
    .join(" ");

  return (
    <div className="w-full" role="img" aria-label={`연도별 ${priceLabel} 단가 및 거래 건수 추이`}>
      <p className="text-[10px] text-slate-500 mb-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5">
        <span className="inline-flex items-center gap-1 font-bold text-blue-600">
          <span className="inline-block w-3 h-0.5 bg-blue-600 rounded" aria-hidden />
          {priceLabel}(만원/㎡)
        </span>
        <span className="inline-flex items-center gap-1">
          <svg width={22} height={10} viewBox="0 0 22 10" className="shrink-0 text-slate-500" aria-hidden>
            <line x1="1" y1="5" x2="14" y2="5" stroke={COUNT_DASH_LINE} strokeWidth="1.4" strokeDasharray="3 5" strokeOpacity={0.55} />
            <circle cx="17" cy="5" r="3" fill="#fff" stroke={COUNT_MARKER_STROKE} strokeWidth="1.6" />
          </svg>
          거래 건수
        </span>
      </p>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto max-h-[300px] text-slate-500" preserveAspectRatio="xMidYMid meet">
        {sorted.map((r, i) => (
          <text key={r.year} x={xAt(i)} y={H - 8} textAnchor="middle" className={`fill-slate-700 dark:fill-slate-200 font-semibold ${n > 6 ? "text-[9px]" : "text-[10px]"}`}>
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
          <text key={`cl-${r.year}`} x={xAt(i)} y={yCount(r.count) + LABEL_COUNT_BELOW} textAnchor="middle" className="fill-slate-700 dark:fill-slate-200 font-semibold" opacity={0.95} style={{ fontSize: "11px" }}>
            {r.count.toLocaleString("ko-KR")}
          </text>
        ))}
        {priceLineRows.length > 0 && (
          <>
            <polyline fill="none" stroke="#2563eb" strokeWidth={2} strokeLinejoin="round" points={pricePoints} />
            {priceLineRows.map((r) => {
              const idx = sorted.indexOf(r);
              const pv = Number(priceValue(r, metric));
              return (
                <circle key={`m-${r.year}`} cx={xAt(idx)} cy={yPrice(pv)} r={3.5} fill="#fff" stroke="#2563eb" strokeWidth={2} />
              );
            })}
            {priceLineRows.map((r) => {
              const idx = sorted.indexOf(r);
              const cy = yPrice(Number(priceValue(r, metric)));
              return (
                <text key={`ml-${r.year}`} x={xAt(idx)} y={cy - LABEL_PRICE_ABOVE} textAnchor="middle" className="fill-slate-900 dark:fill-white font-bold" style={{ fontSize: "12px" }}>
                  {formatPriceLabel(Number(priceValue(r, metric)))}
                </text>
              );
            })}
          </>
        )}
      </svg>
    </div>
  );
}

export function yearlyPointPrice(p: YearlyStatPoint, metric: LongTermPriceMetric): number | null {
  return priceValue(p, metric);
}
