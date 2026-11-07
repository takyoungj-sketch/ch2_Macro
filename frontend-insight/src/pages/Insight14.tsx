import { useState } from "react";
import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { INSIGHT_14, INSIGHT_14_SNAP } from "../copy/insight14";

function Prose({ lines }: { lines: readonly string[] }) {
  return (
    <div className="space-y-2">
      {lines.map((p) => (
        <p key={p}>{p}</p>
      ))}
    </div>
  );
}

function HelpMark({ label, text, align = "start" }: { label: string; text: string; align?: "start" | "end" }) {
  const [open, setOpen] = useState(false);
  const paragraphs = text.split("\n").map((line) => line.trim()).filter(Boolean);
  return (
    <span className="relative inline-flex align-middle">
      <button
        type="button"
        className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full border border-slate-300 text-[10px] leading-none text-slate-500 hover:border-slate-500 hover:text-slate-800 dark:border-slate-500 dark:hover:text-slate-100"
        aria-expanded={open}
        aria-label={`${label} 도움말`}
        onClick={() => setOpen((v) => !v)}
      >
        ?
      </button>
      {open ? (
        <span
          role="note"
          className={`absolute top-6 z-20 w-80 space-y-2 rounded-md border border-slate-200 bg-white p-3 text-xs leading-relaxed text-slate-700 shadow-md dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200 ${
            align === "end" ? "right-0" : "left-0"
          }`}
        >
          {paragraphs.map((line) => (
            <span key={line} className="block">
              {line}
            </span>
          ))}
        </span>
      ) : null}
    </span>
  );
}

const REGION_BARS = [
  { name: "서울", n: 24, pct: 80.1, p25: 72.1, p75: 85.6 },
  { name: "광역시", n: 45, pct: 56.8, p25: 48.1, p75: 67.0 },
  { name: "도 지역 시", n: 34, pct: 59.9, p25: 53.9, p75: 63.2 },
];

function RegionChart() {
  return (
    <figure className="space-y-3">
      <div className="space-y-3" aria-hidden="true">
        {REGION_BARS.map((row) => (
          <div key={row.name} className="grid grid-cols-[4.5rem_1fr_3.5rem] items-center gap-2 text-sm">
            <span className="text-slate-700 dark:text-slate-200">{row.name}</span>
            <span className="relative h-3 rounded-full bg-slate-100 dark:bg-slate-800">
              <span
                className="absolute inset-y-0 left-0 rounded-full bg-indigo-500/80"
                style={{ width: `${row.pct}%` }}
              />
              <span
                className="absolute top-1/2 h-2 -translate-y-1/2 border-x border-slate-900 dark:border-white"
                style={{ left: `${row.p25}%`, width: `${row.p75 - row.p25}%` }}
              />
            </span>
            <span className="text-right font-semibold tabular-nums text-slate-900 dark:text-slate-50">
              {row.pct.toFixed(1)}%
            </span>
          </div>
        ))}
        <div className="grid grid-cols-[4.5rem_1fr_3.5rem] gap-2 text-[11px] tabular-nums text-slate-400">
          <span />
          <span className="flex justify-between">
            <span>0%</span>
            <span>25%</span>
            <span>50%</span>
            <span>75%</span>
            <span>100%</span>
          </span>
          <span />
        </div>
      </div>
      <figcaption className="sr-only">
        {REGION_BARS.map((row) => `${row.name} ${row.n}곳 중앙값 ${row.pct}%`).join(". ")}
      </figcaption>
    </figure>
  );
}

const snap = INSIGHT_14_SNAP;
const copy = INSIGHT_14;

const cards = [
  { label: "104곳 가격비율 중앙값", value: "62.0%", note: "", caption: "" },
  { label: "엄격 매칭 62곳", value: "61.4%", note: "", caption: "" },
  {
    label: "오피스텔 가격이 유의하게 낮은 곳",
    value: "84/88",
    note: "회귀분석 대상 88곳",
    caption: "면적·거래시점 등을 고려한 분석 결과",
  },
];

export default function Insight14() {
  const prose = "space-y-3 text-sm leading-relaxed text-slate-700 dark:text-slate-200";
  const h3 = "text-base font-semibold text-slate-900 dark:text-slate-50";
  const h4 = "text-sm font-semibold text-slate-900 dark:text-slate-50";
  const aiContext = {
    app: "insight" as const,
    panel: "Insight14",
    purpose: "statistics" as const,
    scope: { region_label: "전국" },
    facts: {
      as_of: snap.asOfMonth,
      period_start: snap.periodStart,
      period_end: snap.periodEnd,
      n_headline: snap.nHeadline,
      n_strict: snap.nStrict,
      n_regression: snap.nRegression,
      n_interval_below: snap.nIntervalBelow,
      headline_pct: "62.0%",
      strict_pct: "61.4%",
    },
    explain: {
      spec_id: "insight_14",
      spec_version: "2",
      title: copy.listTitle,
      summary: copy.summary.join(" "),
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

        <header className="space-y-4">
          <div className="space-y-2">
            <h2 className="text-xl font-bold leading-snug">{copy.listTitle}</h2>
            <p className="text-sm italic text-slate-600 dark:text-slate-300">{copy.listSub}</p>
            <p className="text-sm font-medium text-slate-800 dark:text-slate-100">분석기간: {snap.periodLabel}</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {cards.map((card, index) => (
              <div
                key={card.label}
                className="rounded-md border border-slate-200 bg-slate-50 px-3 py-3 dark:border-slate-600 dark:bg-slate-800/60"
              >
                <p className="text-xs text-slate-500">
                  {card.label}
                  {index === 2 ? <HelpMark label="회귀분석" text={copy.helps.regression} align="end" /> : null}
                </p>
                <p
                  className={`mt-1 font-semibold tabular-nums text-slate-900 dark:text-slate-50 ${
                    index === 0 ? "text-3xl" : "text-lg"
                  }`}
                >
                  {card.value}
                </p>
                {card.note ? <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">{card.note}</p> : null}
                {card.caption ? <p className="mt-1 text-xs leading-snug text-slate-500">{card.caption}</p> : null}
              </div>
            ))}
          </div>
        </header>

        <section className={prose}>
          <h3 className={h3}>{copy.summaryTitle}</h3>
          <p>
            동일 지번에 아파트와 오피스텔이 함께 있는 곳 가운데 비교조건을 충족한 104곳을 분석했습니다.{" "}
            <strong className="text-slate-900 dark:text-slate-50">오피스텔의 아파트 대비 ㎡당 거래가격 비율은 중앙값 62.0%</strong>{"로 나타났습니다. "} 비교대상의 절반은 53.7~75.0%에 있었고, 104곳 중 102곳에서 오피스텔 가격이 더 낮았습니다.
          </p>
          <p>{copy.summary[1]}</p>
        </section>

        <section className={prose}>
          <h3 className={h3}>{copy.methodTitle}</h3>
          <p>{copy.methodLead}</p>
          <p>
            {copy.methodPick}
            <HelpMark label="비교 단위" text={copy.helps.key} />
          </p>
          <p>{copy.methodAfter}</p>
          <ul className="list-disc space-y-1 pl-5">
            {copy.methodBullets.map((item) => (
              <li key={item.label}>
                <span className="font-medium text-slate-900 dark:text-slate-50">{item.label}: </span>
                {item.text}
                {item.label === "면적" ? <HelpMark label="면적 조건" text={copy.helps.area} /> : null}
                {item.label === "층" ? <HelpMark label="층 구간" text={copy.helps.floor} /> : null}
              </li>
            ))}
          </ul>
          <Prose lines={copy.methodTail} />
          <p className="font-medium text-slate-900 dark:text-slate-50">{copy.ratioMeaning}</p>
          <p>{copy.methodNote}</p>
        </section>

        <section className="space-y-4">
          <h3 className={h3}>{copy.bodyTitle}</h3>
          <h4 className={h4}>{copy.regionTitle}</h4>
          <RegionChart />
          <p className="text-xs text-slate-500">{copy.regionChartNote}</p>
          <table className="data w-full text-[13px]">
            <caption className="sr-only">지역별 가격비율</caption>
            <thead>
              <tr>
                <th className="text-left">지역</th>
                <th>비교대상</th>
                <th>가격비율 중앙값</th>
                <th>25~75% 범위</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>서울</td>
                <td>24곳</td>
                <td>80.1%</td>
                <td>72.1~85.6%</td>
              </tr>
              <tr>
                <td>광역시</td>
                <td>45곳</td>
                <td>56.8%</td>
                <td>48.1~67.0%</td>
              </tr>
              <tr>
                <td>도 지역 시</td>
                <td>34곳</td>
                <td>59.9%</td>
                <td>53.9~63.2%</td>
              </tr>
              <tr>
                <td>군</td>
                <td>1곳</td>
                <td colSpan={2}>표본이 1곳이라 중앙값을 읽지 않음</td>
              </tr>
            </tbody>
          </table>
          <div className={prose}>
            <p>{copy.regionLead}</p>
          </div>
          <h4 className={h4}>{copy.vintageTitle}</h4>
          <div className={prose}>
            <p>{copy.vintage}</p>
          </div>
        </section>

        <section className="space-y-6">
          <h3 className={h3}>{copy.checkTitle}</h3>
          <section className={prose}>
            <h4 className={h4}>
              {copy.checkAreaTitle}
              <HelpMark label="면적·시점 검증" text={copy.helps.area} />
            </h4>
            <Prose lines={copy.checkArea} />
          </section>
          <section className={prose}>
            <h4 className={h4}>
              {copy.checkRegTitle}
              <HelpMark label="회귀분석 검증" text={copy.helps.regression} />
            </h4>
            <Prose lines={copy.checkReg} />
          </section>
          <section className={prose}>
            <h4 className={h4}>{copy.checkIdTitle}</h4>
            <Prose lines={copy.checkId} />
          </section>
          <div className={prose}>
            <Prose lines={copy.selection} />
          </div>
        </section>

        <section className={prose}>
          <h3 className={h3}>{copy.limitsTitle}</h3>
          <p>{copy.limitsLead}</p>
          <ol className="list-decimal space-y-2 pl-5">
            {copy.limits.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ol>
        </section>

        <section className={prose}>
          <h3 className={h3}>{copy.closeTitle}</h3>
          <Prose lines={copy.close} />
        </section>

        <section className={prose}>
          <h3 className={h3}>{copy.relatedTitle}</h3>
          <Prose lines={copy.related} />
          <p>
            <a href={copy.relatedHref} className="font-medium text-indigo-700 hover:underline dark:text-indigo-300">
              {copy.relatedLink}
            </a>
          </p>
        </section>
      </article>
    </>
  );
}
