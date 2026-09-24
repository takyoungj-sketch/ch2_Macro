import { useState } from "react";
import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { INSIGHT_11, INSIGHT_11_SNAP } from "../copy/insight11";

function Prose({ lines }: { lines: readonly string[] }) {
  return (
    <div className="space-y-2">
      {lines.map((p) => (
        <p key={p}>{p}</p>
      ))}
    </div>
  );
}

function pct(v: number): string {
  return v.toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function YearTable({
  caption,
  rows,
  totalHeader,
  annualHeader,
}: {
  caption: string;
  rows: { label: string; values: readonly number[]; total?: number; annual?: number }[];
  totalHeader?: string;
  annualHeader?: string;
}) {
  const years = INSIGHT_11_SNAP.years;
  return (
    <div className="space-y-1 overflow-x-auto">
      <p className="text-xs text-slate-500">{caption}</p>
      <table className="data w-full text-[13px]">
        <thead>
          <tr>
            <th className="text-left">항목</th>
            {years.map((year) => (
              <th key={year}>{year}</th>
            ))}
            {totalHeader ? <th>{totalHeader}</th> : null}
            {annualHeader ? <th>{annualHeader}</th> : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <td className="text-left">{row.label}</td>
              {row.values.map((value, index) => (
                <td key={`${row.label}-${years[index]}`}>{pct(value)}</td>
              ))}
              {totalHeader ? <td>{row.total == null ? "" : pct(row.total)}</td> : null}
              {annualHeader ? <td>{row.annual == null ? "" : pct(row.annual)}</td> : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const SERIES_COLORS = [
  "#1d4ed8",
  "#0f766e",
  "#a16207",
  "#7c3aed",
  "#b91c1c",
  "#c2410c",
  "#0369a1",
  "#be185d",
] as const;

function ReturnChart({
  rows,
}: {
  rows: { label: string; values: readonly number[]; color: string }[];
}) {
  const years = INSIGHT_11_SNAP.years;
  const width = 640;
  const height = 280;
  const pad = { l: 44, r: 12, t: 12, b: 28 };
  const flat = rows.flatMap((row) => [...row.values]);
  const yMin = Math.min(0, Math.floor(Math.min(...flat) / 5) * 5);
  const yMax = Math.max(10, Math.ceil(Math.max(...flat) / 5) * 5);
  const xOf = (index: number) =>
    pad.l + (index / (years.length - 1)) * (width - pad.l - pad.r);
  const yOf = (value: number) =>
    pad.t + ((yMax - value) / (yMax - yMin)) * (height - pad.t - pad.b);
  const ticks = [yMax, Math.round((yMax + yMin) / 2), yMin].filter((tick, index, all) => all.indexOf(tick) === index);
  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-500">연간 투자성과 비교(%). 유형마다 색이 다릅니다.</p>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" role="img">
        {ticks.map((tick) => (
          <g key={tick}>
            <line
              x1={pad.l}
              x2={width - pad.r}
              y1={yOf(tick)}
              y2={yOf(tick)}
              stroke="#e2e8f0"
            />
            <text x={pad.l - 6} y={yOf(tick) + 4} textAnchor="end" fontSize="11" fill="#64748b">
              {tick}
            </text>
          </g>
        ))}
        {years.map((year, index) => (
          <text key={year} x={xOf(index)} y={height - 8} textAnchor="middle" fontSize="11" fill="#64748b">
            {year}
          </text>
        ))}
        {rows.map((row) => (
          <polyline
            key={row.label}
            fill="none"
            stroke={row.color}
            strokeWidth="2"
            points={row.values.map((value, index) => `${xOf(index)},${yOf(value)}`).join(" ")}
          />
        ))}
      </svg>
      <ul className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-600 dark:text-slate-300">
        {rows.map((row) => (
          <li key={row.label} className="inline-flex items-center gap-1">
            <span className="inline-block h-2 w-3" style={{ background: row.color }} />
            {row.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

function CumulativeChart({
  rows,
}: {
  rows: { label: string; value: number; color: string }[];
}) {
  const width = 640;
  const height = 220;
  const pad = { l: 148, r: 48, t: 8, b: 8 };
  const max = Math.max(...rows.map((row) => row.value)) * 1.15;
  const rowH = (height - pad.t - pad.b) / rows.length;
  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-500">5년 누적수익률(%). 각 줄의 연간 값을 복리로 이었습니다.</p>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" role="img">
        {rows.map((row, index) => {
          const y = pad.t + index * rowH;
          const barW = (row.value / max) * (width - pad.l - pad.r);
          return (
            <g key={row.label}>
              <text x={pad.l - 8} y={y + rowH * 0.65} textAnchor="end" fontSize="11" fill="#64748b">
                {row.label}
              </text>
              <rect x={pad.l} y={y + 4} width={barW} height={rowH - 8} fill={row.color} />
              <text x={pad.l + barW + 6} y={y + rowH * 0.65} fontSize="11" fill="#64748b">
                {pct(row.value)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

const snap = INSIGHT_11_SNAP;
const copy = INSIGHT_11;

const PERF_ROWS = [
  { label: "오피스 투자수익률", values: INSIGHT_11_SNAP.officeInv, total: INSIGHT_11_SNAP.fiveYear.office, color: SERIES_COLORS[0] },
  { label: "중대형 상가 투자수익률", values: INSIGHT_11_SNAP.midInv, total: INSIGHT_11_SNAP.fiveYear.mid, color: SERIES_COLORS[1] },
  { label: "소규모 상가 투자수익률", values: INSIGHT_11_SNAP.smallInv, total: INSIGHT_11_SNAP.fiveYear.small, color: SERIES_COLORS[2] },
  { label: "집합 상가 투자수익률", values: INSIGHT_11_SNAP.strataInv, total: INSIGHT_11_SNAP.fiveYear.strata, color: SERIES_COLORS[3] },
  { label: "아파트 소득+자본", values: INSIGHT_11_SNAP.aptSum, total: INSIGHT_11_SNAP.fiveYear.apt, color: SERIES_COLORS[4] },
  { label: "연립다세대 소득+자본", values: INSIGHT_11_SNAP.rowSum, total: INSIGHT_11_SNAP.fiveYear.row, color: SERIES_COLORS[5] },
  { label: "오피스텔 소득+자본", values: INSIGHT_11_SNAP.offiSum, total: INSIGHT_11_SNAP.fiveYear.officetel, color: SERIES_COLORS[6] },
  { label: "KODEX KOSPI TR", values: INSIGHT_11_SNAP.kospiTr, total: INSIGHT_11_SNAP.fiveYear.kospi, color: SERIES_COLORS[7] },
];

export default function Insight11() {
  const [withKospi, setWithKospi] = useState(false);
  const prose = "space-y-3 text-sm leading-relaxed text-slate-700 dark:text-slate-200";
  const propertyRows = PERF_ROWS.slice(0, 7);
  const kospiRows = PERF_ROWS;
  const aiContext = {
    app: "insight" as const,
    panel: "Insight11",
    purpose: "statistics" as const,
    scope: { region_label: "전국" },
    facts: {
      as_of: "2025",
      office_income_2025: snap.officeIncome[4],
      apt_converted_2025: snap.aptConverted[4],
      apt_cash_2025: snap.aptCash[4],
      ktb_2025: snap.ktb[4],
      office_invest_2025: snap.officeInv[4],
      apt_sum_2025: snap.aptSum[4],
      kospi_tr_2025: snap.kospiTr[4],
    },
    explain: {
      spec_id: "insight_11",
      spec_version: "1",
      title: copy.listTitle,
      summary: copy.lead,
      limitations: [...copy.limits],
    },
  };

  return (
    <>
      <PublishAiContext context={aiContext} />
      <article className="max-w-4xl mx-auto px-4 py-8 space-y-10 pb-16">
        <p>
          <a href="/insight/" className="text-sm text-slate-500 hover:text-slate-800 dark:hover:text-slate-200">
            ← 질문 목록
          </a>
        </p>
        <header className="space-y-3">
          <h2 className="text-xl font-bold leading-snug">{copy.listTitle}</h2>
          <p className="text-sm text-slate-500">{copy.listSub}</p>
        </header>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.summaryTitle}</h3>
          <p className="text-sm font-medium text-slate-800 dark:text-slate-100 leading-relaxed">{copy.lead}</p>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.seeTitle}</h3>
          <Prose lines={copy.intro} />
          <ul className="list-disc ml-5 space-y-1.5">
            {copy.see.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>

        <section className="space-y-10">
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.bodyTitle}</h3>
          <section className={prose}>
            <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{copy.s1Title}</h4>
            <Prose lines={copy.s1} />
            <YearTable
              caption="소득(%). 국고채 3년과 코스피 배당수익률은 그해 수준입니다."
              rows={[
                { label: "오피스", values: snap.officeIncome },
                { label: "중대형 상가", values: snap.midIncome },
                { label: "소규모 상가", values: snap.smallIncome },
                { label: "집합 상가", values: snap.strataIncome },
                { label: "아파트 월세환산", values: snap.aptConverted },
                { label: "연립다세대 월세환산", values: snap.rowConverted },
                { label: "오피스텔 월세환산", values: snap.offiConverted },
                { label: "국고채 3년", values: snap.ktb },
                { label: "코스피 배당수익률", values: snap.dividend },
              ]}
            />
            <YearTable
              caption="소득에서 국고채 3년을 뺀 차이(%포인트)."
              rows={[
                { label: "오피스", values: snap.spreadOffice },
                { label: "집합 상가", values: snap.spreadStrata },
                { label: "아파트 현금 월세", values: snap.spreadAptCash },
                { label: "아파트 월세환산", values: snap.spreadAptConv },
              ]}
            />
          </section>
          <section className={prose}>
            <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{copy.s2Title}</h4>
            <Prose lines={copy.s2} />
            <YearTable
              caption="자본(%). 코스피는 가격수익률입니다."
              rows={[
                { label: "오피스", values: snap.officeCap },
                { label: "중대형 상가", values: snap.midCap },
                { label: "소규모 상가", values: snap.smallCap },
                { label: "집합 상가", values: snap.strataCap },
                { label: "아파트 매매가격지수", values: snap.aptCap },
                { label: "연립다세대 매매가격지수", values: snap.rowCap },
                { label: "오피스텔 매매가격지수", values: snap.offiCap },
                { label: "코스피 가격수익률", values: snap.kospiPrice },
              ]}
            />
          </section>
          <section className={prose}>
            <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{copy.s3Title}</h4>
            <Prose lines={copy.s3} />
            <YearTable
              caption="연간 투자성과(%). 5년 누적은 그 줄의 연간 값을 복리로 이은 값이고, 연평균은 그 누적을 한 해로 나눈 값입니다. 상업은 공표 투자수익률, 주거는 소득+자본, 코스피는 KODEX KOSPI TR입니다."
              totalHeader="5년 누적"
              annualHeader="연평균"
              rows={[
                { label: "오피스 투자수익률", values: snap.officeInv, total: snap.fiveYear.office, annual: snap.annualAvg.office },
                { label: "중대형 상가 투자수익률", values: snap.midInv, total: snap.fiveYear.mid, annual: snap.annualAvg.mid },
                { label: "소규모 상가 투자수익률", values: snap.smallInv, total: snap.fiveYear.small, annual: snap.annualAvg.small },
                { label: "집합 상가 투자수익률", values: snap.strataInv, total: snap.fiveYear.strata, annual: snap.annualAvg.strata },
                { label: "아파트 소득+자본", values: snap.aptSum, total: snap.fiveYear.apt, annual: snap.annualAvg.apt },
                { label: "연립다세대 소득+자본", values: snap.rowSum, total: snap.fiveYear.row, annual: snap.annualAvg.row },
                { label: "오피스텔 소득+자본", values: snap.offiSum, total: snap.fiveYear.officetel, annual: snap.annualAvg.officetel },
                { label: "KODEX KOSPI TR", values: snap.kospiTr, total: snap.fiveYear.kospi, annual: snap.annualAvg.kospi },
              ]}
            />
            <ReturnChart rows={propertyRows} />
            <CumulativeChart rows={propertyRows.map((row) => ({ label: row.label, value: row.total, color: row.color }))} />
            {withKospi ? (
              <>
                <ReturnChart rows={kospiRows} />
                <CumulativeChart rows={kospiRows.map((row) => ({ label: row.label, value: row.total, color: row.color }))} />
              </>
            ) : (
              <p>
                <button
                  type="button"
                  className="rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-800 dark:border-slate-600 dark:text-slate-100"
                  onClick={() => setWithKospi(true)}
                >
                  코스피 추가
                </button>
              </p>
            )}
          </section>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.limitsTitle}</h3>
          <ul className="list-disc ml-5 space-y-1.5">
            {copy.limits.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.closeTitle}</h3>
          <Prose lines={copy.close} />
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.nextTitle}</h3>
          <ul className="list-disc ml-5 space-y-1.5">
            {copy.next.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.relatedTitle}</h3>
          <p>{copy.related}</p>
          <p>
            <a href="/rent/" className="text-slate-800 underline dark:text-slate-200">
              임대 화면
            </a>
          </p>
        </section>
      </article>
    </>
  );
}
