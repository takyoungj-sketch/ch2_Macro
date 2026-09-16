import { useMemo, useState, Fragment } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { fetchMacroTs, type MacroCorr, type MacroGrain, type MacroPoint } from "../api/macroTsClient";

function fmtR(r: number | null | undefined): string {
  if (r == null || Number.isNaN(r)) return "—";
  const sign = r > 0 ? "+" : "";
  return `${sign}${r.toFixed(2)}`;
}

function periodKey(p: MacroPoint): number | null {
  if (p.month) {
    const [y, m] = p.month.split("-").map(Number);
    if (!y || !m) return null;
    return y * 100 + m;
  }
  return p.year ?? null;
}

function toMap(pts: MacroPoint[]): Map<number, number> {
  const out = new Map<number, number>();
  for (const p of pts) {
    const k = periodKey(p);
    if (k == null) continue;
    out.set(k, p.v);
  }
  return out;
}

function addLag(key: number, lag: number, grain: MacroGrain): number {
  if (grain === "calendar_year") return key + lag;
  const y = Math.floor(key / 100);
  const m = key % 100;
  const m0 = y * 12 + (m - 1) + lag;
  const y2 = Math.floor(m0 / 12);
  const m2 = ((m0 % 12) + 12) % 12;
  const yy = m0 < 0 ? y2 - 1 : y2;
  return yy * 100 + (m2 + 1);
}

function ordinal(key: number, grain: MacroGrain): number {
  if (grain === "calendar_year") return key;
  return Math.floor(key / 100) * 12 + (key % 100);
}

function formatTick(key: number, grain: MacroGrain): string {
  if (grain === "calendar_year") return String(key);
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

function fmtTick(v: number): string {
  if (Math.abs(v) < 1e-12) return "0";
  const a = Math.abs(v);
  const digits = a >= 100 ? 0 : a >= 10 ? 1 : 2;
  return Number(v.toFixed(digits)).toLocaleString("ko-KR");
}

function DualLines({
  keys,
  grain,
  left,
  right,
  leftLabel,
  rightLabel,
}: {
  keys: number[];
  grain: MacroGrain;
  left: Map<number, number>;
  right: Map<number, number>;
  leftLabel: string;
  rightLabel: string;
}) {
  const w = 980;
  const h = 440;
  const pad = { l: 72, r: 72, t: 36, b: 56 };
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  if (keys.length < 2) {
    return <p className="text-sm text-slate-500">점이 부족합니다.</p>;
  }
  const lv = keys.map((y) => left.get(y)).filter((v): v is number => v != null);
  const rv = keys.map((y) => right.get(y)).filter((v): v is number => v != null);
  if (lv.length < 2 || rv.length < 2) {
    return <p className="text-sm text-slate-500">겹치는 기간이 부족합니다.</p>;
  }
  const lDom = axisDomain(Math.min(...lv), Math.max(...lv));
  const rDom = axisDomain(Math.min(...rv), Math.max(...rv));
  const x0 = ordinal(keys[0], grain);
  const x1 = ordinal(keys[keys.length - 1], grain);
  const dx = x1 - x0 || 1;
  const toX = (y: number) => pad.l + ((ordinal(y, grain) - x0) / dx) * innerW;
  const toYL = (v: number) => pad.t + (1 - (v - lDom.lo) / (lDom.hi - lDom.lo)) * innerH;
  const toYR = (v: number) => pad.t + (1 - (v - rDom.lo) / (rDom.hi - rDom.lo)) * innerH;
  const pathOf = (m: Map<number, number>, toY: (v: number) => number) =>
    keys
      .filter((y) => m.has(y))
      .map((y, i) => `${i === 0 ? "M" : "L"} ${toX(y)} ${toY(m.get(y)!)}`)
      .join(" ");
  const zeroY = lDom.lo <= 0 && lDom.hi >= 0 ? toYL(0) : null;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-auto text-slate-400" role="img" aria-label="이중 축 시계열">
      <text x={pad.l} y={16} className="fill-amber-700 dark:fill-amber-400" fontSize={12}>
        {leftLabel}
      </text>
      <text x={w - pad.r} y={16} textAnchor="end" className="fill-slate-600 dark:fill-slate-300" fontSize={12}>
        {rightLabel}
      </text>
      {lDom.ticks.map((v) => {
        const y = toYL(v);
        return (
          <g key={`lg-${v}`}>
            <line
              x1={pad.l}
              x2={w - pad.r}
              y1={y}
              y2={y}
              className="stroke-slate-200 dark:stroke-slate-700"
              strokeWidth={1}
            />
            <text
              x={pad.l - 8}
              y={y + 4}
              textAnchor="end"
              className="fill-amber-800 dark:fill-amber-300"
              fontSize={11}
            >
              {fmtTick(v)}
            </text>
          </g>
        );
      })}
      {rDom.ticks.map((v) => (
        <text
          key={`rg-${v}`}
          x={w - pad.r + 8}
          y={toYR(v) + 4}
          className="fill-slate-600 dark:fill-slate-300"
          fontSize={11}
        >
          {fmtTick(v)}
        </text>
      ))}
      {zeroY != null && (
        <line
          x1={pad.l}
          x2={w - pad.r}
          y1={zeroY}
          y2={zeroY}
          className="stroke-slate-400 dark:stroke-slate-500"
          strokeWidth={1.2}
          strokeDasharray="4 4"
        />
      )}
      <rect
        x={pad.l}
        y={pad.t}
        width={innerW}
        height={innerH}
        fill="transparent"
        className="stroke-slate-300 dark:stroke-slate-600"
      />
      <path d={pathOf(left, toYL)} className="stroke-amber-600 dark:stroke-amber-400" fill="none" strokeWidth={2} />
      <path d={pathOf(right, toYR)} className="stroke-slate-600 dark:stroke-slate-300" fill="none" strokeWidth={2} />
      {keys.map((y) => {
        const label = formatTick(y, grain);
        if (!label) return null;
        return (
          <g key={y}>
            <line
              x1={toX(y)}
              x2={toX(y)}
              y1={pad.t + innerH}
              y2={pad.t + innerH + 5}
              className="stroke-slate-400 dark:stroke-slate-500"
            />
            <text
              x={toX(y)}
              y={pad.t + innerH + 20}
              textAnchor="middle"
              className="fill-slate-600 dark:fill-slate-300"
              fontSize={11}
            >
              {label}
            </text>
          </g>
        );
      })}
      <text x={w / 2} y={h - 8} textAnchor="middle" className="fill-current" fontSize={11}>
        {grain === "calendar_month" ? "달력 월 (1월 눈금)" : "달력 연도"}
      </text>
    </svg>
  );
}

export default function MacroTsLab() {
  const [grain, setGrain] = useState<MacroGrain>("calendar_month");
  const [lag, setLag] = useState(0);
  const q = useQuery({
    queryKey: ["lab-macro-ts", grain],
    queryFn: () => fetchMacroTs(grain),
  });
  const [pane, setPane] = useState<"rate" | "m2">("rate");
  const [rateId, setRateId] = useState<string | null>(null);
  const [metric, setMetric] = useState<"count" | "amount">("count");
  const [picked, setPicked] = useState("합계");

  const resolvedRate = rateId || q.data?.default_rate || "cd_91";
  const rate = q.data?.rates[resolvedRate];
  const typeSeries = q.data?.series[picked];
  const lags = q.data?.lags ?? (grain === "calendar_month" ? [0, 1, 3, 6] : [0, 1]);
  const activeGrain: MacroGrain = q.data?.grain === "calendar_month" ? "calendar_month" : "calendar_year";

  const chart = useMemo(() => {
    if (!q.data || !typeSeries) return null;
    const leftPts = pane === "rate" ? rate?.d_pp : q.data.m2?.yoy_pct;
    if (!leftPts) return null;
    const rightPts = metric === "count" ? typeSeries.yoy_count : typeSeries.yoy_amount;
    const left = toMap(leftPts);
    const rightRaw = toMap(rightPts);
    const right = new Map<number, number>();
    for (const [t, xv] of left) {
      const yv = rightRaw.get(addLag(t, lag, activeGrain));
      if (yv == null) continue;
      right.set(t, yv);
    }
    const keys = [...left.keys()].filter((k) => right.has(k)).sort((a, b) => a - b);
    return {
      keys,
      left,
      right,
      leftLabel: pane === "rate" ? `${rate?.label ?? "금리"} 전년동월 %p` : "M2 전년동월 %",
      rightLabel: `${picked} ${metric === "count" ? "건수" : "거래액"} 전년동월 %${lag ? ` · +${lag}` : ""}`,
    };
  }, [q.data, pane, rate, typeSeries, metric, picked, lag, activeGrain]);

  const corrKey = (k: number) => {
    if (pane === "m2") return `m2_${metric}_lag${k}`;
    return `${resolvedRate}_${metric}_lag${k}`;
  };

  const err = q.isError ? ((q.error as { message?: string })?.message ?? "불러오지 못했습니다") : null;
  const isMonth = grain === "calendar_month";

  return (
    <div className="max-w-6xl mx-auto px-4 py-4 space-y-4 pb-10">
      <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
        전국에서 금리·M2의 <strong>전년{isMonth ? "동월" : ""} 변화</strong>와 8유형 거래 건수·액 YoY를 봅니다.
        시군구 상관·인과 문장이 아닙니다. 거래는 국토부 CSV 전국 합(실험 마트)이고, 연도는 그 월을 달력연도로 더한 값입니다.
        월 주기에서 시차 0/1/3/6개월을 봅니다. 그래프는 <strong>전년 대비</strong>만 그립니다.
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex rounded border border-slate-300 dark:border-slate-600 p-0.5">
          <button
            type="button"
            className={clsx(
              "px-2 py-0.5 text-[11px] rounded",
              grain === "calendar_year"
                ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900"
                : "text-slate-600",
            )}
            onClick={() => {
              setGrain("calendar_year");
              setLag(0);
            }}
          >
            연도
          </button>
          <button
            type="button"
            className={clsx(
              "px-2 py-0.5 text-[11px] rounded",
              grain === "calendar_month"
                ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900"
                : "text-slate-600",
            )}
            onClick={() => {
              setGrain("calendar_month");
              setLag(0);
            }}
          >
            월
          </button>
        </div>
        <div className="inline-flex rounded border border-slate-300 dark:border-slate-600 p-0.5">
          <button
            type="button"
            className={clsx(
              "px-2 py-0.5 text-[11px] rounded",
              pane === "rate" ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900" : "text-slate-600",
            )}
            onClick={() => setPane("rate")}
          >
            금리
          </button>
          <button
            type="button"
            className={clsx(
              "px-2 py-0.5 text-[11px] rounded",
              pane === "m2" ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900" : "text-slate-600",
            )}
            onClick={() => setPane("m2")}
          >
            유동성(M2)
          </button>
        </div>
        {pane === "rate" && q.data && (
          <span className="inline-flex flex-wrap gap-1">
            {Object.values(q.data.rates).map((r) => (
              <button
                key={r.id}
                type="button"
                className={clsx(
                  "rounded-md border px-2 py-0.5 text-[11px] font-semibold",
                  resolvedRate === r.id
                    ? "border-amber-600 bg-amber-50 text-amber-950 dark:border-amber-400 dark:bg-amber-950 dark:text-amber-100"
                    : "border-slate-300 text-slate-600 dark:border-slate-600",
                )}
                onClick={() => setRateId(r.id)}
              >
                {r.label}
                {r.id === q.data.default_rate ? " · 대표" : ""}
              </button>
            ))}
          </span>
        )}
        <div className="inline-flex rounded border border-slate-300 dark:border-slate-600 p-0.5 ml-1">
          <button
            type="button"
            className={clsx(
              "px-2 py-0.5 text-[11px] rounded",
              metric === "count" ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900" : "text-slate-600",
            )}
            onClick={() => setMetric("count")}
          >
            거래건수
          </button>
          <button
            type="button"
            className={clsx(
              "px-2 py-0.5 text-[11px] rounded",
              metric === "amount" ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900" : "text-slate-600",
            )}
            onClick={() => setMetric("amount")}
          >
            거래액
          </button>
        </div>
        <div className="inline-flex rounded border border-slate-300 dark:border-slate-600 p-0.5">
          {lags.map((k) => (
            <button
              key={k}
              type="button"
              className={clsx(
                "px-2 py-0.5 text-[11px] rounded",
                lag === k ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900" : "text-slate-600",
              )}
              onClick={() => setLag(k)}
            >
              {k === 0 ? "시차 0" : isMonth ? `+${k}개월` : "+1년"}
            </button>
          ))}
        </div>
      </div>

      {q.isLoading && (
        <p className="text-sm text-slate-500">
          {isMonth ? "월 시계열을 읽고 있습니다…" : "연도 시계열을 읽고 있습니다…"}
        </p>
      )}
      {err && <p className="text-sm text-red-600">{err}</p>}

      {q.data && (
        <p className="text-[11px] text-slate-500">
          {(q.data.periods && q.data.periods.length
            ? `${q.data.periods[0]}–${q.data.periods[q.data.periods.length - 1]}`
            : `${q.data.years[0]}–${q.data.years[q.data.years.length - 1]}`)}{" "}
          · 금리 {q.data.sources.rates}
          {q.data.sources.policy ? ` · 기준 ${q.data.sources.policy}` : ""} · M2 {q.data.sources.m2}
          {q.data.sources.rates_dir ? ` · ${q.data.sources.rates_dir}` : ""}
          {q.data.missing.length ? ` · 없음 ${q.data.missing.join(", ")}` : ""}
          {q.data.coverage_notes.length ? ` · ${q.data.coverage_notes.join(" · ")}` : ""}
        </p>
      )}

      {q.data && chart && (
        <section className="card p-4">
          <h2 className="text-sm font-semibold">
            전년{isMonth ? "동월" : ""} 대비 · {picked}
          </h2>
          <p className="text-[11px] text-slate-500 mt-0.5">노란 선 왼쪽 축, 회색 선 오른쪽 축. 수준이 아니라 변화량입니다.</p>
          <div className="mt-3">
            <DualLines
              keys={chart.keys}
              grain={activeGrain}
              left={chart.left}
              right={chart.right}
              leftLabel={chart.leftLabel}
              rightLabel={chart.rightLabel}
            />
          </div>
        </section>
      )}

      {q.data && (
        <section className="card overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-700">
            <h2 className="text-sm font-semibold">유형별 Pearson r (변화량)</h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              {isMonth
                ? "같은 달 · 거래는 1·3·6개월 뒤. n은 겹치는 달 수입니다. 행을 누르면 그래프 유형이 바뀝니다."
                : "같은 해 · 거래는 한 해 뒤. n은 겹치는 연 수입니다. 행을 누르면 그래프 유형이 바뀝니다."}
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="data w-full text-xs">
              <thead>
                <tr>
                  <th className="text-left">유형</th>
                  {lags.map((k) => (
                    <th key={k} colSpan={2}>
                      {k === 0 ? (isMonth ? "같은 달" : "같은 해") : isMonth ? `+${k}개월` : "+1년"}
                    </th>
                  ))}
                </tr>
                <tr>
                  <th />
                  {lags.map((k) => (
                    <Fragment key={k}>
                      <th>r</th>
                      <th>n</th>
                    </Fragment>
                  ))}
                </tr>
              </thead>
              <tbody>
                {q.data.pairs.map((row) => {
                  const active = picked === row.type;
                  return (
                    <tr
                      key={row.type}
                      className={clsx("cursor-pointer", active && "bg-amber-50 dark:bg-amber-950/40")}
                      onClick={() => setPicked(row.type)}
                    >
                      <td className="text-left">{row.type}</td>
                      {lags.map((k) => {
                        const cell = row[corrKey(k)] as MacroCorr | undefined;
                        return (
                          <Fragment key={k}>
                            <td className="tabular-nums">{fmtR(cell?.r)}</td>
                            <td className="tabular-nums">{cell?.n ?? "—"}</td>
                          </Fragment>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
