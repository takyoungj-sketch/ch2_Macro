import { useEffect, useMemo, useRef, useState } from "react";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import { formatAmountCompact, formatAmountPerCapita, formatInt, formatPopMan } from "../utils/format";
import { formatCorr, pearson } from "../utils/corr";

export type ScatterTab = "amount" | "count" | "per_capita";

export interface ScatterRow {
  code: string;
  name: string;
  population: number | null;
  amount_3y: number;
  count_3y: number;
}

type ScatterPt = { code: string; name: string; x: number; y: number; px: number; py: number };

const PAD = { l: 48, r: 8, t: 8, b: 26 };

function useIsDark() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  useEffect(() => {
    const el = document.documentElement;
    const obs = new MutationObserver(() => setDark(el.classList.contains("dark")));
    obs.observe(el, { attributes: true, attributeFilter: ["class"] });
    return () => obs.disconnect();
  }, []);
  return dark;
}

function logPad(vals: number[]): { min: number; max: number } {
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const a = Math.log10(lo);
  const b = Math.log10(hi);
  const p = (b - a) * 0.08 || 0.25;
  return { min: 10 ** (a - p), max: 10 ** (b + p) };
}

function logTicks(min: number, max: number): number[] {
  const t0 = Math.floor(Math.log10(min));
  const t1 = Math.ceil(Math.log10(max));
  const ticks: number[] = [];
  for (let e = t0; e <= t1; e++) {
    const v = 10 ** e;
    if (v >= min * 0.92 && v <= max * 1.08) ticks.push(v);
  }
  return ticks.length ? ticks : [min, max];
}

function yOf(row: ScatterRow, tab: ScatterTab): number | null {
  if (tab === "amount") return row.amount_3y > 0 ? row.amount_3y : null;
  if (tab === "count") return row.count_3y > 0 ? row.count_3y : null;
  if (row.population == null || row.population <= 0) return null;
  const v = row.amount_3y / row.population;
  return v > 0 && Number.isFinite(v) ? v : null;
}

function fmtY(v: number, tab: ScatterTab): string {
  if (tab === "amount") return formatAmountCompact(v);
  if (tab === "count") return `${formatInt(v)}건`;
  return formatAmountPerCapita(v, 1);
}

interface Props {
  rows: ScatterRow[];
  tab: ScatterTab;
  focusCode: string;
  onPick: (code: string) => void;
}

export default function NationalScatter({ rows, tab, focusCode, onPick }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [cssW, setCssW] = useState(300);
  const cssH = 168;
  const dark = useIsDark();
  const [hover, setHover] = useState<ScatterPt | null>(null);

  const raw = useMemo(() => {
    const out: Omit<ScatterPt, "px" | "py">[] = [];
    for (const r of rows) {
      if (r.population == null || r.population <= 0) continue;
      const y = yOf(r, tab);
      if (y == null) continue;
      out.push({ code: r.code, name: r.name, x: r.population, y });
    }
    return out;
  }, [rows, tab]);

  const layout = useMemo(() => {
    if (!raw.length) return { pts: [] as ScatterPt[], xMin: 1, xMax: 1, yMin: 1, yMax: 1 };
    const xr = logPad(raw.map((p) => p.x));
    const yr = logPad(raw.map((p) => p.y));
    const iw = Math.max(40, cssW - PAD.l - PAD.r);
    const ih = Math.max(40, cssH - PAD.t - PAD.b);
    const sx = (x: number) => PAD.l + ((Math.log10(x) - Math.log10(xr.min)) / (Math.log10(xr.max) - Math.log10(xr.min) || 1)) * iw;
    const sy = (y: number) => PAD.t + ih - ((Math.log10(y) - Math.log10(yr.min)) / (Math.log10(yr.max) - Math.log10(yr.min) || 1)) * ih;
    const pts = raw.map((p) => ({ ...p, px: sx(p.x), py: sy(p.y) }));
    return { pts, xMin: xr.min, xMax: xr.max, yMin: yr.min, yMax: yr.max };
  }, [raw, cssW]);

  useEffect(() => {
    setHover(null);
  }, [tab, focusCode]);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setCssW(el.clientWidth));
    ro.observe(el);
    setCssW(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = Math.round(cssW * dpr);
    c.height = Math.round(cssH * dpr);
    c.style.width = `${cssW}px`;
    c.style.height = `${cssH}px`;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);

    const ink = dark ? "#94a3b8" : "#64748b";
    const faint = dark ? "rgba(148,163,184,0.22)" : "rgba(100,116,139,0.28)";
    ctx.font = "10px ui-sans-serif, system-ui, sans-serif";
    ctx.fillStyle = ink;
    ctx.strokeStyle = dark ? "rgba(148,163,184,0.25)" : "rgba(148,163,184,0.45)";
    ctx.lineWidth = 1;

    const { pts, xMin, xMax, yMin, yMax } = layout;
    if (!pts.length) {
      ctx.fillStyle = dark ? "#94a3b8" : "#94a3b8";
      ctx.font = "11px ui-sans-serif, system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("그릴 점이 없습니다", cssW / 2, cssH / 2);
      return;
    }
    const plotL = PAD.l;
    const plotR = cssW - PAD.r;
    const plotT = PAD.t;
    const plotB = cssH - PAD.b;

    ctx.beginPath();
    ctx.moveTo(plotL, plotT);
    ctx.lineTo(plotL, plotB);
    ctx.lineTo(plotR, plotB);
    ctx.stroke();

    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (const t of logTicks(xMin, xMax)) {
      const x = PAD.l + ((Math.log10(t) - Math.log10(xMin)) / (Math.log10(xMax) - Math.log10(xMin) || 1)) * (plotR - plotL);
      if (x < plotL - 1 || x > plotR + 1) continue;
      ctx.beginPath();
      ctx.moveTo(x, plotB);
      ctx.lineTo(x, plotB + 3);
      ctx.stroke();
      ctx.fillText(formatPopMan(t), x, plotB + 5);
    }
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (const t of logTicks(yMin, yMax)) {
      const y = plotT + (plotB - plotT) - ((Math.log10(t) - Math.log10(yMin)) / (Math.log10(yMax) - Math.log10(yMin) || 1)) * (plotB - plotT);
      if (y < plotT - 1 || y > plotB + 1) continue;
      ctx.beginPath();
      ctx.moveTo(plotL - 3, y);
      ctx.lineTo(plotL, y);
      ctx.stroke();
      ctx.fillText(fmtY(t, tab), plotL - 5, y);
    }

    ctx.fillStyle = faint;
    ctx.save();
    ctx.beginPath();
    ctx.rect(plotL, plotT, plotR - plotL, plotB - plotT);
    ctx.clip();
    for (const p of pts) {
      if (p.code === focusCode) continue;
      ctx.fillRect(p.px - 1, p.py - 1, 2.2, 2.2);
    }

    const focus = pts.find((p) => p.code === focusCode);
    if (focus) {
      ctx.beginPath();
      ctx.arc(focus.px, focus.py, 4.5, 0, Math.PI * 2);
      ctx.fillStyle = dark ? "#fbbf24" : "#d97706";
      ctx.fill();
      ctx.strokeStyle = dark ? "#fde68a" : "#fff";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    if (hover && hover.code !== focusCode) {
      ctx.beginPath();
      ctx.arc(hover.px, hover.py, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = dark ? "#e2e8f0" : "#0f172a";
      ctx.fill();
    }
    ctx.restore();
  }, [cssW, dark, focusCode, hover, layout, tab]);

  function nearest(mx: number, my: number): ScatterPt | null {
    let best: ScatterPt | null = null;
    let bestD = 10 * 10;
    for (const p of layout.pts) {
      const dx = p.px - mx;
      const dy = p.py - my;
      const d = dx * dx + dy * dy;
      if (d < bestD) {
        bestD = d;
        best = p;
      }
    }
    return best;
  }

  const yHead = tab === "amount" ? "3년 거래액" : tab === "count" ? "3년 건수" : "인구당 거래액";
  const focusOnPlot = layout.pts.some((p) => p.code === focusCode);
  const corr = useMemo(() => {
    if (raw.length < 10) return null;
    const xs = raw.map((p) => Math.log10(p.x));
    const ys = raw.map((p) => Math.log10(p.y));
    return pearson(xs, ys);
  }, [raw]);

  return (
    <div className="mt-2">
      <div className="flex items-center gap-1">
        <h3 className="text-[11px] font-medium text-slate-600 dark:text-slate-300">전국 분포</h3>
        <StatsGlossaryHelp termId="national_scatter" size="xs" />
        <StatsGlossaryHelp termId="pop_trade_corr" size="xs" />
      </div>
      <p className="text-[10px] leading-snug text-slate-400">
        가로 인구 · 세로 {yHead} · 로그 · {raw.length.toLocaleString("ko-KR")}점
        {corr != null ? ` · 동조 r ${formatCorr(corr, raw.length)}` : ""}
        {!focusOnPlot && focusCode ? " · 현재 지역은 인구 없어 점 없음" : ""}
      </p>
      <div ref={wrapRef} className="relative mt-1">
        <canvas
          ref={canvasRef}
          className="block w-full cursor-crosshair"
          onMouseMove={(e) => {
            const r = e.currentTarget.getBoundingClientRect();
            setHover(nearest(e.clientX - r.left, e.clientY - r.top));
          }}
          onMouseLeave={() => setHover(null)}
          onClick={() => {
            if (hover) onPick(hover.code);
          }}
        />
        {hover && (
          <div
            className="pointer-events-none absolute z-10 max-w-[11rem] rounded border border-slate-200 bg-white px-1.5 py-1 text-[10px] shadow-sm dark:border-slate-600 dark:bg-slate-800"
            style={{
              left: Math.min(hover.px + 8, cssW - 140),
              top: Math.max(4, hover.py - 36),
            }}
          >
            <div className="truncate font-medium">{hover.name}</div>
            <div className="tabular-nums text-slate-500">
              {formatPopMan(hover.x)} · {fmtY(hover.y, tab)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
