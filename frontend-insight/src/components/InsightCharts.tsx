import type { MacroPoint } from "../api/insightClient";

export function periodKey(p: MacroPoint): number | null {
  if (p.month) {
    const [y, m] = p.month.split("-").map(Number);
    if (!y || !m) return null;
    return y * 100 + m;
  }
  return p.year ?? null;
}

export function toMap(pts: MacroPoint[]): Map<number, number> {
  const out = new Map<number, number>();
  for (const p of pts) {
    const k = periodKey(p);
    if (k == null) continue;
    out.set(k, p.v);
  }
  return out;
}

export function addLag(key: number, lag: number): number {
  const y = Math.floor(key / 100);
  const m = key % 100;
  const m0 = y * 12 + (m - 1) + lag;
  const y2 = Math.floor(m0 / 12);
  const m2 = ((m0 % 12) + 12) % 12;
  const yy = m0 < 0 ? y2 - 1 : y2;
  return yy * 100 + (m2 + 1);
}

function ordinal(key: number): number {
  return Math.floor(key / 100) * 12 + (key % 100);
}

function formatTick(key: number): string {
  const m = key % 100;
  if (m !== 1) return "";
  return String(Math.floor(key / 100));
}

function niceStep(span: number, targetTicks = 5): number {
  const raw = Math.abs(span) / targetTicks || 1;
  const pow10 = 10 ** Math.floor(Math.log10(raw));
  const n = raw / pow10;
  let step = 1;
  if (n <= 1) step = 1;
  else if (n <= 2) step = 2;
  else if (n <= 5) step = 5;
  else step = 10;
  return step * pow10;
}

function axisDomain(min: number, max: number, targetTicks = 5): { ticks: number[]; lo: number; hi: number } {
  let lo = min;
  let hi = max;
  if (lo === hi) {
    const pad = Math.abs(lo) * 0.1 || 1;
    lo -= pad;
    hi += pad;
  }
  if (lo > 0 && lo / (hi - lo) < 0.2) lo = 0;
  if (hi < 0 && -hi / (hi - lo) < 0.2) hi = 0;
  const step = niceStep(hi - lo, targetTicks);
  lo = Math.floor(lo / step) * step;
  hi = Math.ceil(hi / step) * step;
  if (lo === hi) hi = lo + step;
  const ticks: number[] = [];
  const n = Math.round((hi - lo) / step);
  for (let i = 0; i <= n; i++) ticks.push(Number((lo + i * step).toFixed(10)));
  return { ticks, lo, hi };
}

export type AxisFmt = (v: number) => string;

function signedScale(v: number, divisor: number, suffix: string, digits: number): string {
  const n = v / divisor;
  const abs = Math.abs(n).toFixed(digits);
  const [i, f] = abs.split(".");
  const grouped = Number(i).toLocaleString("ko-KR");
  const body = digits > 0 ? `${grouped}.${f}` : grouped;
  return `${n < 0 ? "-" : ""}${body}${suffix}`;
}

/** 건수. 제목 단위는 (건/월). 1만 건 이상은 「만」. */
export function fmtCount(v: number): string {
  if (Math.abs(v) < 1e-12) return "0";
  const a = Math.abs(v);
  if (a >= 1e4) return signedScale(v, 1e4, "만", 0);
  return Number(v.toFixed(0)).toLocaleString("ko-KR");
}

/** 원장 거래액(만원). 1조원 = 1억 만원, 1억원 = 1만 만원. */
export function fmtManwon(v: number): string {
  if (Math.abs(v) < 1e-12) return "0";
  const a = Math.abs(v);
  if (a >= 1e8) return signedScale(v, 1e8, "조", 1);
  if (a >= 1e4) return signedScale(v, 1e4, "억", 1);
  return `${Number(v.toFixed(0)).toLocaleString("ko-KR")}만`;
}

/** BOK M2 수준. 값은 십억원. 축은 조원. */
export function fmtEokWon(v: number): string {
  if (Math.abs(v) < 1e-12) return "0";
  const a = Math.abs(v);
  if (a >= 1000) return signedScale(v, 1000, "조", a >= 100_000 ? 0 : 1);
  return `${Number(v.toFixed(0)).toLocaleString("ko-KR")}십억`;
}

export function fmtRate(v: number): string {
  if (Math.abs(v) < 1e-12) return "0";
  const digits = Math.abs(v) >= 10 ? 1 : 2;
  return Number(v.toFixed(digits)).toLocaleString("ko-KR");
}

export function fmtPct(v: number): string {
  if (Math.abs(v) < 1e-12) return "0%";
  return `${Number(v.toFixed(1)).toLocaleString("ko-KR")}%`;
}

export function fmtPp(v: number): string {
  if (Math.abs(v) < 1e-12) return "0";
  return `${Number(v.toFixed(1)).toLocaleString("ko-KR")}%p`;
}

const W = 920;
const H = 220;
const PAD = { l: 72, r: 72, t: 28, b: 40 };

export function SingleLine({
  keys,
  values,
  overlay,
  label,
  overlayLabel,
  formatY = fmtRate,
}: {
  keys: number[];
  values: Map<number, number>;
  overlay?: Map<number, number>;
  label: string;
  overlayLabel?: string;
  formatY?: AxisFmt;
}) {
  const pts = keys.map((k) => values.get(k)).filter((v): v is number => v != null);
  if (keys.length < 2 || pts.length < 2) {
    return <p className="text-sm text-slate-500">점이 부족합니다.</p>;
  }
  const ov = overlay ? keys.map((k) => overlay.get(k)).filter((v): v is number => v != null) : [];
  const all = ov.length ? [...pts, ...ov] : pts;
  const dom = axisDomain(Math.min(...all), Math.max(...all));
  const innerW = W - PAD.l - PAD.r;
  const innerH = H - PAD.t - PAD.b;
  const x0 = ordinal(keys[0]);
  const x1 = ordinal(keys[keys.length - 1]);
  const dx = x1 - x0 || 1;
  const toX = (k: number) => PAD.l + ((ordinal(k) - x0) / dx) * innerW;
  const toY = (v: number) => PAD.t + (1 - (v - dom.lo) / (dom.hi - dom.lo)) * innerH;
  const pathOf = (m: Map<number, number>) =>
    keys
      .filter((k) => m.has(k))
      .map((k, i) => `${i === 0 ? "M" : "L"} ${toX(k)} ${toY(m.get(k)!)}`)
      .join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto text-slate-400" role="img" aria-label={label}>
      <text x={PAD.l} y={16} className="fill-slate-700 dark:fill-slate-200" fontSize={12}>
        {label}
        {overlayLabel ? `  ·  ${overlayLabel}(점선)` : ""}
      </text>
      {dom.ticks.map((v) => {
        const y = toY(v);
        return (
          <g key={`t-${v}`}>
            <line
              x1={PAD.l}
              x2={W - PAD.r}
              y1={y}
              y2={y}
              className="stroke-slate-200 dark:stroke-slate-700"
              strokeWidth={1}
            />
            <text x={PAD.l - 8} y={y + 4} textAnchor="end" className="fill-slate-500 dark:fill-slate-400" fontSize={11}>
              {formatY(v)}
            </text>
          </g>
        );
      })}
      <rect
        x={PAD.l}
        y={PAD.t}
        width={innerW}
        height={innerH}
        fill="transparent"
        className="stroke-slate-300 dark:stroke-slate-600"
      />
      <path d={pathOf(values)} className="stroke-slate-800 dark:stroke-slate-100" fill="none" strokeWidth={2} />
      {overlay && ov.length >= 2 ? (
        <path
          d={pathOf(overlay)}
          className="stroke-slate-500 dark:stroke-slate-400"
          fill="none"
          strokeWidth={1.5}
          strokeDasharray="5 4"
        />
      ) : null}
      {keys.map((k) => {
        const t = formatTick(k);
        if (!t) return null;
        return (
          <text
            key={k}
            x={toX(k)}
            y={PAD.t + innerH + 18}
            textAnchor="middle"
            className="fill-slate-600 dark:fill-slate-300"
            fontSize={11}
          >
            {t}
          </text>
        );
      })}
    </svg>
  );
}

export function DualLine({
  keys,
  left,
  right,
  leftLabel,
  rightLabel,
  formatLeft = fmtPct,
  formatRight = fmtPct,
}: {
  keys: number[];
  left: Map<number, number>;
  right: Map<number, number>;
  leftLabel: string;
  rightLabel: string;
  formatLeft?: AxisFmt;
  formatRight?: AxisFmt;
}) {
  const lv = keys.map((k) => left.get(k)).filter((v): v is number => v != null);
  const rv = keys.map((k) => right.get(k)).filter((v): v is number => v != null);
  if (keys.length < 2 || lv.length < 2 || rv.length < 2) {
    return <p className="text-sm text-slate-500">겹치는 기간이 부족합니다.</p>;
  }
  const lDom = axisDomain(Math.min(...lv), Math.max(...lv));
  const rDom = axisDomain(Math.min(...rv), Math.max(...rv));
  const innerW = W - PAD.l - PAD.r;
  const innerH = H - PAD.t - PAD.b;
  const x0 = ordinal(keys[0]);
  const x1 = ordinal(keys[keys.length - 1]);
  const dx = x1 - x0 || 1;
  const toX = (k: number) => PAD.l + ((ordinal(k) - x0) / dx) * innerW;
  const toYL = (v: number) => PAD.t + (1 - (v - lDom.lo) / (lDom.hi - lDom.lo)) * innerH;
  const toYR = (v: number) => PAD.t + (1 - (v - rDom.lo) / (rDom.hi - rDom.lo)) * innerH;
  const pathOf = (m: Map<number, number>, toY: (v: number) => number) =>
    keys
      .filter((k) => m.has(k))
      .map((k, i) => `${i === 0 ? "M" : "L"} ${toX(k)} ${toY(m.get(k)!)}`)
      .join(" ");
  const zeroY = lDom.lo <= 0 && lDom.hi >= 0 ? toYL(0) : null;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto text-slate-400" role="img" aria-label={`${leftLabel} vs ${rightLabel}`}>
      <text x={PAD.l} y={16} className="fill-amber-800 dark:fill-amber-300" fontSize={12}>
        {leftLabel}
      </text>
      <text x={W - PAD.r} y={16} textAnchor="end" className="fill-slate-600 dark:fill-slate-300" fontSize={12}>
        {rightLabel}
      </text>
      {lDom.ticks.map((v) => {
        const y = toYL(v);
        return (
          <g key={`lg-${v}`}>
            <line
              x1={PAD.l}
              x2={W - PAD.r}
              y1={y}
              y2={y}
              className="stroke-slate-200 dark:stroke-slate-700"
              strokeWidth={1}
            />
            <text x={PAD.l - 8} y={y + 4} textAnchor="end" className="fill-amber-800 dark:fill-amber-300" fontSize={11}>
              {formatLeft(v)}
            </text>
          </g>
        );
      })}
      {rDom.ticks.map((v) => (
        <text
          key={`rg-${v}`}
          x={W - PAD.r + 8}
          y={toYR(v) + 4}
          className="fill-slate-600 dark:fill-slate-300"
          fontSize={11}
        >
          {formatRight(v)}
        </text>
      ))}
      {zeroY != null && (
        <line
          x1={PAD.l}
          x2={W - PAD.r}
          y1={zeroY}
          y2={zeroY}
          className="stroke-slate-400 dark:stroke-slate-500"
          strokeWidth={1.2}
          strokeDasharray="4 4"
        />
      )}
      <rect
        x={PAD.l}
        y={PAD.t}
        width={innerW}
        height={innerH}
        fill="transparent"
        className="stroke-slate-300 dark:stroke-slate-600"
      />
      <path d={pathOf(left, toYL)} className="stroke-amber-600 dark:stroke-amber-400" fill="none" strokeWidth={2} />
      <path d={pathOf(right, toYR)} className="stroke-slate-600 dark:stroke-slate-300" fill="none" strokeWidth={2} />
      {keys.map((k) => {
        const t = formatTick(k);
        if (!t) return null;
        return (
          <text
            key={k}
            x={toX(k)}
            y={PAD.t + innerH + 18}
            textAnchor="middle"
            className="fill-slate-600 dark:fill-slate-300"
            fontSize={11}
          >
            {t}
          </text>
        );
      })}
    </svg>
  );
}
