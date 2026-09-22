import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAnnualScale, type YearPoint } from "../api/annualScaleClient";
import LabResume from "./LabResume";

const TYPE_COLOR: Record<string, string> = {
  토지: "#a16207",
  상가: "#0369a1",
  공장: "#4b5563",
  단독다가구: "#7c3aed",
  아파트: "#dc2626",
  오피스텔: "#0891b2",
  연립다세대: "#ea580c",
  분양권: "#65a30d",
};

function toMap(pts: YearPoint[]): Map<number, number> {
  const out = new Map<number, number>();
  for (const p of pts) out.set(p.year, p.v);
  return out;
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

function axisDomain(min: number, max: number): { ticks: number[]; lo: number; hi: number } {
  let lo = min;
  let hi = max;
  if (lo === hi) {
    const pad = Math.abs(lo) * 0.1 || 1;
    lo -= pad;
    hi += pad;
  }
  if (lo > 0 && lo / (hi - lo) < 0.35) lo = 0;
  const step = niceStep(hi - lo);
  lo = Math.floor(lo / step) * step;
  hi = Math.ceil(hi / step) * step;
  if (lo === hi) hi = lo + step;
  const ticks: number[] = [];
  const n = Math.round((hi - lo) / step);
  for (let i = 0; i <= n; i++) ticks.push(Number((lo + i * step).toFixed(10)));
  return { ticks, lo, hi };
}

function fmtPct(v: number): string {
  return `${Number(v.toFixed(1)).toLocaleString("ko-KR")}%`;
}

function fmtJo(v: number): string {
  const jo = v / 1000;
  if (Math.abs(jo) < 1e-12) return "0조";
  const digits = Math.abs(jo) >= 100 ? 0 : 1;
  return `${Number(jo.toFixed(digits)).toLocaleString("ko-KR")}조`;
}

function fmtR(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return Number(v.toFixed(2)).toLocaleString("ko-KR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

type YearDomain = { ticks: number[]; lo: number; hi: number };

function domainFromMaps(maps: Map<number, number>[]): YearDomain {
  const pts: number[] = [];
  for (const m of maps) {
    for (const v of m.values()) pts.push(v);
  }
  if (pts.length < 1) return { ticks: [0, 1], lo: 0, hi: 1 };
  return axisDomain(Math.min(0, ...pts), Math.max(...pts));
}

const LEVEL_COLOR = {
  re: "#dc2626",
  gdp: "#2563eb",
  m2: "#059669",
  stock: "#d97706",
};

function YearLine({
  years,
  values,
  label,
  formatY = fmtPct,
  color = "#b45309",
  domain,
  showValues = false,
}: {
  years: number[];
  values: Map<number, number>;
  label: string;
  formatY?: (v: number) => string;
  color?: string;
  domain?: YearDomain;
  showValues?: boolean;
}) {
  const w = 920;
  const h = showValues ? 280 : 240;
  const pad = { l: 88, r: showValues ? 36 : 16, t: showValues ? 44 : 28, b: 36 };
  const pts = years.map((y) => values.get(y)).filter((v): v is number => v != null);
  if (years.length < 2 || pts.length < 2) {
    return <p className="text-sm text-slate-500">점이 부족합니다.</p>;
  }
  const dom = domain ?? axisDomain(Math.min(...pts), Math.max(...pts));
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const x0 = years[0];
  const dx = years[years.length - 1] - x0 || 1;
  const span = dom.hi - dom.lo || 1;
  const toX = (y: number) => pad.l + ((y - x0) / dx) * innerW;
  const toY = (v: number) => pad.t + (1 - (v - dom.lo) / span) * innerH;
  const keyed = years.filter((y) => values.has(y));
  const d = keyed.map((y, i) => `${i === 0 ? "M" : "L"} ${toX(y)} ${toY(values.get(y)!)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-auto" role="img" aria-label={label}>
      <text x={pad.l} y={16} className="fill-slate-700 dark:fill-slate-200" fontSize={12}>
        {label}
      </text>
      {dom.ticks.map((v) => {
        const y = toY(v);
        return (
          <g key={v}>
            <line
              x1={pad.l}
              x2={w - pad.r}
              y1={y}
              y2={y}
              className="stroke-slate-200 dark:stroke-slate-700"
              strokeWidth={1}
            />
            <text x={pad.l - 8} y={y + 4} textAnchor="end" className="fill-slate-500" fontSize={11}>
              {formatY(v)}
            </text>
          </g>
        );
      })}
      <path d={d} fill="none" stroke={color} strokeWidth={2} />
      {keyed.map((y) => {
        const v = values.get(y)!;
        const x = toX(y);
        const py = toY(v);
        const nearTop = py < pad.t + 18;
        return (
          <g key={y}>
            <circle cx={x} cy={py} r={2.5} fill={color} />
            {showValues ? (
              <text x={x} y={nearTop ? py + 14 : py - 8} textAnchor="middle" fontSize={9} fill={color}>
                {formatY(v)}
              </text>
            ) : null}
          </g>
        );
      })}
      {years.map((y) =>
        y % 2 === 0 ? (
          <text key={y} x={toX(y)} y={h - 10} textAnchor="middle" className="fill-slate-500" fontSize={11}>
            {y}
          </text>
        ) : null,
      )}
    </svg>
  );
}

function MultiYearLine({
  years,
  series,
  label,
  formatY = fmtPct,
  domain,
  showValues = false,
}: {
  years: number[];
  series: { key: string; label: string; values: Map<number, number>; color: string }[];
  label: string;
  formatY?: (v: number) => string;
  domain?: YearDomain;
  showValues?: boolean;
}) {
  const w = 920;
  const h = showValues ? 340 : 260;
  const pad = { l: 88, r: 36, t: showValues ? 56 : 28, b: 36 };
  const maps = series.map((s) => s.values);
  const pts = maps.flatMap((m) => years.map((y) => m.get(y)).filter((v): v is number => v != null));
  if (years.length < 2 || pts.length < 2) {
    return <p className="text-sm text-slate-500">점이 부족합니다.</p>;
  }
  const dom = domain ?? domainFromMaps(maps);
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const x0 = years[0];
  const dx = years[years.length - 1] - x0 || 1;
  const span = dom.hi - dom.lo || 1;
  const toX = (y: number) => pad.l + ((y - x0) / dx) * innerW;
  const toY = (v: number) => pad.t + (1 - (v - dom.lo) / span) * innerH;
  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-auto" role="img" aria-label={label}>
        <text x={pad.l} y={16} className="fill-slate-700 dark:fill-slate-200" fontSize={12}>
          {label}
        </text>
        {dom.ticks.map((v) => {
          const y = toY(v);
          return (
            <g key={v}>
              <line
                x1={pad.l}
                x2={w - pad.r}
                y1={y}
                y2={y}
                className="stroke-slate-200 dark:stroke-slate-700"
                strokeWidth={1}
              />
              <text x={pad.l - 8} y={y + 4} textAnchor="end" className="fill-slate-500" fontSize={11}>
                {formatY(v)}
              </text>
            </g>
          );
        })}
        {series.map((s) => {
          const keyed = years.filter((y) => s.values.has(y));
          const d = keyed
            .map((y, i) => `${i === 0 ? "M" : "L"} ${toX(y)} ${toY(s.values.get(y)!)}`)
            .join(" ");
          return <path key={s.key} d={d} fill="none" stroke={s.color} strokeWidth={2} />;
        })}
        {series.map((s, si) =>
          years
            .filter((y) => s.values.has(y))
            .map((y) => {
              const v = s.values.get(y)!;
              const x = toX(y);
              const py = toY(v);
              const nearTop = py < pad.t + 22;
              const stagger = si * 11;
              return (
                <g key={`${s.key}-${y}`}>
                  <circle cx={x} cy={py} r={2.5} fill={s.color} />
                  {showValues ? (
                    <text
                      x={x}
                      y={nearTop ? py + 12 + stagger : py - 8 - stagger}
                      textAnchor="middle"
                      fontSize={8}
                      fill={s.color}
                    >
                      {formatY(v)}
                    </text>
                  ) : null}
                </g>
              );
            }),
        )}
        {years.map((y) =>
          y % 2 === 0 ? (
            <text key={y} x={toX(y)} y={h - 10} textAnchor="middle" className="fill-slate-500" fontSize={11}>
              {y}
            </text>
          ) : null,
        )}
      </svg>
      <ul className="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-[11px] text-slate-600 dark:text-slate-300">
        {series.map((s) => (
          <li key={s.key} className="inline-flex items-center gap-1">
            <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: s.color }} />
            {s.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

function MixStack({
  years,
  share,
  label = "유형 구성비",
  formatY = fmtPct,
  domain,
}: {
  years: number[];
  share: Record<string, YearPoint[]>;
  label?: string;
  formatY?: (v: number) => string;
  domain?: YearDomain;
}) {
  const types = Object.keys(TYPE_COLOR).filter((t) => share[t]?.length);
  const maps = Object.fromEntries(types.map((t) => [t, toMap(share[t])]));
  const pctDom: YearDomain = { ticks: [0, 25, 50, 75, 100], lo: 0, hi: 100 };
  const dom = domain ?? pctDom;
  const w = 920;
  const h = 280;
  const pad = { l: domain ? 88 : 56, r: 16, t: 28, b: 36 };
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const gap = 4;
  const bw = Math.max(6, innerW / years.length - gap);
  const span = dom.hi - dom.lo || 1;
  const toY = (v: number) => pad.t + (1 - (v - dom.lo) / span) * innerH;
  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-auto" role="img" aria-label={label}>
        <text x={pad.l} y={16} className="fill-slate-700 dark:fill-slate-200" fontSize={12}>
          {label}
        </text>
        {dom.ticks.map((v) => {
          const y = toY(v);
          return (
            <g key={v}>
              <line
                x1={pad.l}
                x2={w - pad.r}
                y1={y}
                y2={y}
                className="stroke-slate-200 dark:stroke-slate-700"
                strokeWidth={1}
              />
              <text x={pad.l - 8} y={y + 4} textAnchor="end" className="fill-slate-500" fontSize={11}>
                {formatY(v)}
              </text>
            </g>
          );
        })}
        {years.map((year, i) => {
          const x = pad.l + (i + 0.5) * (innerW / years.length) - bw / 2;
          let acc = 0;
          return (
            <g key={year}>
              {types.map((t) => {
                const v = maps[t].get(year) ?? 0;
                const bh = (v / span) * innerH;
                const y = pad.t + innerH - acc - bh;
                acc += bh;
                return <rect key={t} x={x} y={y} width={bw} height={Math.max(0, bh)} fill={TYPE_COLOR[t]} />;
              })}
              {year % 2 === 0 ? (
                <text x={x + bw / 2} y={h - 10} textAnchor="middle" className="fill-slate-500" fontSize={11}>
                  {year}
                </text>
              ) : null}
            </g>
          );
        })}
      </svg>
      <ul className="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-[11px] text-slate-600 dark:text-slate-300">
        {types.map((t) => (
          <li key={t} className="inline-flex items-center gap-1">
            <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: TYPE_COLOR[t] }} />
            {t}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function MacroAnnualScaleLab() {
  const q = useQuery({ queryKey: ["lab-macro-annual-scale"], queryFn: fetchAnnualScale });
  const [showTypeGdp, setShowTypeGdp] = useState(false);
  const data = q.data;

  const reMap = useMemo(() => (data ? toMap(data.levels_eok.re_total) : new Map()), [data]);
  const gdpLevelMap = useMemo(() => (data ? toMap(data.levels_eok.gdp) : new Map()), [data]);
  const m2LevelMap = useMemo(() => (data ? toMap(data.levels_eok.m2) : new Map()), [data]);
  const stockLevelMap = useMemo(() => (data ? toMap(data.levels_eok.stock) : new Map()), [data]);
  const gdpMap = useMemo(() => (data ? toMap(data.ratios.vs_gdp) : new Map()), [data]);
  const m2Map = useMemo(() => (data ? toMap(data.ratios.vs_m2) : new Map()), [data]);
  const stockMap = useMemo(() => (data ? toMap(data.ratios.vs_stock) : new Map()), [data]);

  if (q.isLoading) return <p className="p-4 text-sm text-slate-500">불러오는 중…</p>;
  if (q.isError || !data) {
    return <p className="p-4 text-sm text-red-700">연 규모 시계열을 읽지 못했습니다.</p>;
  }

  const years = data.years;
  const s2010 = data.smoke["2010"];
  const s2024 = data.smoke["2024"];
  const mixTypes = data.types.filter((t) => t !== "합계");
  const mixAmountMaps = mixTypes.map((t) => toMap(data.mix.amount_eok[t] ?? []));
  const mixStacked = new Map(
    years.map((y) => [y, mixAmountMaps.reduce((sum, m) => sum + (m.get(y) ?? 0), 0)] as const),
  );
  const mixAmtStackDom = domainFromMaps([mixStacked]);
  const mixAmtLineDom = domainFromMaps(mixAmountMaps);
  const mixAmountSeries = mixTypes.map((t, i) => ({
    key: t,
    label: t,
    values: mixAmountMaps[i],
    color: TYPE_COLOR[t] ?? "#64748b",
  }));
  const levelDom = domainFromMaps([reMap, gdpLevelMap, m2LevelMap, stockLevelMap]);
  const ratioDom = domainFromMaps([gdpMap, m2Map, stockMap]);
  const levelSeries = [
    { key: "re", label: "부동산 거래액 (8유형 합)", values: reMap, color: LEVEL_COLOR.re },
    { key: "gdp", label: "명목 GDP", values: gdpLevelMap, color: LEVEL_COLOR.gdp },
    { key: "m2", label: "시중 돈(M2) 잔액", values: m2LevelMap, color: LEVEL_COLOR.m2 },
    { key: "stock", label: "주식 거래대금", values: stockLevelMap, color: LEVEL_COLOR.stock },
  ];
  const ratioSeries = [
    { key: "vsGdp", label: "거래액 / 명목 GDP", values: gdpMap, color: LEVEL_COLOR.gdp },
    { key: "vsM2", label: "거래액 / M2 잔액", values: m2Map, color: LEVEL_COLOR.m2 },
    { key: "vsStock", label: "거래액 / 주식 거래대금", values: stockMap, color: LEVEL_COLOR.stock },
  ];

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-8 text-sm text-slate-700 dark:text-slate-200">
      {data.resume ? <LabResume resume={data.resume} /> : null}

      <section className="space-y-2">
        <h2 className="text-base font-semibold text-slate-900 dark:text-slate-50">질문</h2>
        <p>부동산 거래액은 경제 규모와 비교하면 얼마나 클까?</p>
        <p className="text-slate-600 dark:text-slate-300">
          GDP·M2·주식 거래대금과 비교하고, 부동산 시장의 유형별 구성을 살펴봅니다.
        </p>
        <p className="text-xs text-slate-500">
          전국 · 달력 연 {data.year_start}–{data.year_end} · {years.length}개 완결 연 · 단위 십억 원 맞춤 후 비율. G3(월
          전년동월 r)와 다른 문.
        </p>
        <p>{data.note}</p>
      </section>

      <section className="space-y-2">
        <h2 className="text-base font-semibold text-slate-900 dark:text-slate-50">① 무엇을 비교하나</h2>
        <ul className="list-disc ml-5 space-y-1">
          <li>분자: 국토부 CSV 전국 월 마트 거래액을 달력연으로 더한 값. 여덟 유형 합.</li>
          <li>분모: 명목 GDP(원화), M2 평잔 합계, KOSPI+KOSDAQ 거래대금(연 열).</li>
          <li>원 금액은 같은 조 원 눈금으로 봅니다. 이중축은 쓰지 않습니다.</li>
        </ul>
        <div className="overflow-x-auto rounded border border-slate-200 dark:border-slate-700">
          <table className="min-w-full text-xs">
            <thead className="bg-slate-50 dark:bg-slate-800">
              <tr>
                <th className="text-left px-2 py-1.5">게이트</th>
                <th className="text-right px-2 py-1.5">거래액</th>
                <th className="text-right px-2 py-1.5">GDP</th>
                <th className="text-right px-2 py-1.5">M2</th>
                <th className="text-right px-2 py-1.5">주식대금</th>
                <th className="text-right px-2 py-1.5">/GDP</th>
                <th className="text-left px-2 py-1.5">단위</th>
              </tr>
            </thead>
            <tbody>
              {[s2010, s2024].map((s) =>
                s ? (
                  <tr key={s.year} className="border-t border-slate-200 dark:border-slate-700">
                    <td className="px-2 py-1.5">{s.year}</td>
                    <td className="text-right px-2 py-1.5">{s.re_eok?.toLocaleString("ko-KR")}</td>
                    <td className="text-right px-2 py-1.5">{s.gdp_eok?.toLocaleString("ko-KR")}</td>
                    <td className="text-right px-2 py-1.5">{s.m2_eok?.toLocaleString("ko-KR")}</td>
                    <td className="text-right px-2 py-1.5">{s.stock_eok?.toLocaleString("ko-KR")}</td>
                    <td className="text-right px-2 py-1.5">
                      {s.vs_gdp_pct == null ? "—" : fmtPct(s.vs_gdp_pct)}
                    </td>
                    <td className="px-2 py-1.5">{s.unit_ok ? "십억 원 맞춤" : "확인 필요"}</td>
                  </tr>
                ) : null,
              )}
            </tbody>
          </table>
        </div>
        <p className="text-[11px] text-slate-500">표의 거래액·GDP·M2·주식대금은 십억 원. 비율은 분모 대비 %.</p>
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold text-slate-900 dark:text-slate-50">② 한 해의 총액</h2>
        <p>세로축은 네 그림이 같은 조 원입니다. 선의 높이를 관계의 증거로 읽지 않습니다.</p>
        <p>
          각 지표는 측정 대상과 의미가 서로 다르므로 절대액의 크기 자체를 서로 비교하기보다는, 아래의 비율과
          변화 흐름을 중심으로 봅니다.
        </p>
        <YearLine
          years={years}
          values={reMap}
          label="부동산 거래액 (8유형 합)"
          formatY={fmtJo}
          color={LEVEL_COLOR.re}
          domain={levelDom}
          showValues
        />
        <YearLine
          years={years}
          values={gdpLevelMap}
          label="명목 GDP"
          formatY={fmtJo}
          color={LEVEL_COLOR.gdp}
          domain={levelDom}
          showValues
        />
        <YearLine
          years={years}
          values={m2LevelMap}
          label="시중 돈(M2) 잔액"
          formatY={fmtJo}
          color={LEVEL_COLOR.m2}
          domain={levelDom}
          showValues
        />
        <YearLine
          years={years}
          values={stockLevelMap}
          label="주식 거래대금"
          formatY={fmtJo}
          color={LEVEL_COLOR.stock}
          domain={levelDom}
          showValues
        />
        <MultiYearLine
          years={years}
          series={levelSeries}
          label="네 총액 (같은 조 원)"
          formatY={fmtJo}
          domain={levelDom}
          showValues
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold text-slate-900 dark:text-slate-50">③ 경제·시중 돈·주식 대비</h2>
        <p>해석하지 않습니다. 세로축은 거래액 ÷ 분모입니다. GDP 기여도가 아닙니다.</p>
        <YearLine years={years} values={gdpMap} label="거래액 / 명목 GDP" color={LEVEL_COLOR.gdp} domain={ratioDom} showValues />
        <YearLine years={years} values={m2Map} label="거래액 / M2 잔액" color={LEVEL_COLOR.m2} domain={ratioDom} showValues />
        <YearLine
          years={years}
          values={stockMap}
          label="거래액 / 주식 거래대금"
          color={LEVEL_COLOR.stock}
          domain={ratioDom}
          showValues
        />
        <MultiYearLine years={years} series={ratioSeries} label="세 비율을 한 그림에" domain={ratioDom} showValues />
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold text-slate-900 dark:text-slate-50">
          ④ 부동산 시장의 유형 구성은 어떻게 달라졌나
        </h2>
        <p>세로축은 조 원입니다. 그해 각 유형이 거래된 금액입니다. 구성비가 아닙니다.</p>
        <MixStack
          years={years}
          share={data.mix.amount_eok}
          label="유형별 거래액"
          formatY={fmtJo}
          domain={mixAmtStackDom}
        />
        <MultiYearLine
          years={years}
          series={mixAmountSeries}
          label="여덟 유형 거래액 (같은 조 원)"
          formatY={fmtJo}
          domain={mixAmtLineDom}
        />
        <p>그해 여덟 유형 합에서 각 유형 거래액이 차지하는 몫입니다. 시군구 구성비 8×8이 아닙니다.</p>
        <MixStack years={years} share={data.mix.share} label="유형 구성비" />
      </section>

      {data.corr ? (
        <section className="space-y-2">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-50">⑤ 같은 해에 같이 움직였나</h2>
          <p>{data.corr.read}</p>
          <div className="overflow-x-auto rounded border border-slate-200 dark:border-slate-700">
            <table className="min-w-full text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800">
                <tr>
                  <th className="text-left px-2 py-1.5">거래액과</th>
                  <th className="text-right px-2 py-1.5">GDP</th>
                  <th className="text-right px-2 py-1.5">M2</th>
                  <th className="text-right px-2 py-1.5">주식대금</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-t border-slate-200 dark:border-slate-700">
                  <td className="px-2 py-1.5">총액 수준 (n={data.corr.n_level})</td>
                  <td className="text-right px-2 py-1.5">{fmtR(data.corr.level.re_gdp)}</td>
                  <td className="text-right px-2 py-1.5">{fmtR(data.corr.level.re_m2)}</td>
                  <td className="text-right px-2 py-1.5">{fmtR(data.corr.level.re_stock)}</td>
                </tr>
                <tr className="border-t border-slate-200 dark:border-slate-700">
                  <td className="px-2 py-1.5">전년 대비 (n={data.corr.n_yoy})</td>
                  <td className="text-right px-2 py-1.5">{fmtR(data.corr.yoy.re_gdp)}</td>
                  <td className="text-right px-2 py-1.5">{fmtR(data.corr.yoy.re_m2)}</td>
                  <td className="text-right px-2 py-1.5">{fmtR(data.corr.yoy.re_stock)}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="text-[11px] text-slate-500">
            GDP–M2 수준 r={fmtR(data.corr.level.gdp_m2)} (둘 다 커져 온 추세). 전년 대비 GDP–M2 r=
            {fmtR(data.corr.yoy.gdp_m2)}. 인과 아님. 월 시차 r는 1번.
          </p>
        </section>
      ) : null}

      <section className="space-y-2">
        <button
          type="button"
          className="text-sm underline text-slate-700 dark:text-slate-200"
          onClick={() => setShowTypeGdp((v) => !v)}
        >
          {showTypeGdp ? "유형별 거래액/GDP 접기" : "⑥ 유형별 거래액/GDP (접힌 확인용)"}
        </button>
        {showTypeGdp
          ? data.types.map((t) => (
              <YearLine key={t} years={years} values={toMap(data.type_vs_gdp[t] ?? [])} label={`${t} / GDP`} />
            ))
          : null}
      </section>

      <section className="space-y-2">
        <h2 className="text-base font-semibold text-slate-900 dark:text-slate-50">한계</h2>
        <ul className="list-disc ml-5 space-y-1">
          {data.limits.map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
        {data.coverage_notes.length > 0 ? (
          <p className="text-[11px] text-slate-500">{data.coverage_notes.join(" · ")}</p>
        ) : null}
        <p className="text-[11px] text-slate-500">
          출처 {data.sources.dir}/{data.sources.gdp} · {data.sources.m2} · {data.sources.stock}
        </p>
      </section>
    </div>
  );
}
