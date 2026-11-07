import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { INSIGHT_13, INSIGHT_13_SNAP } from "../copy/insight13";

function Prose({ lines }: { lines: readonly string[] }) {
  return (
    <div className="space-y-2">
      {lines.map((p) => (
        <p key={p}>{p}</p>
      ))}
    </div>
  );
}

const snap = INSIGHT_13_SNAP;
const copy = INSIGHT_13;

const cards = [
  { label: "전국 비교집단", value: "887개" },
  { label: "전국 가격차이 중앙값", value: "−12.8%" },
  { label: "주거지역 단독·다가구 가격차이", value: "+3.7%" },
];

export default function Insight13() {
  const prose = "space-y-3 text-sm leading-relaxed text-slate-700 dark:text-slate-200";
  const aiContext = {
    app: "insight" as const,
    panel: "Insight13",
    purpose: "statistics" as const,
    scope: { region_label: "전국" },
    facts: {
      as_of: snap.asOfMonth,
      period_start: snap.periodStart,
      period_end: snap.periodEnd,
      n_cells: snap.cells,
      n_positive_median: snap.positiveMedian,
      n_positive_mean: snap.positiveMean,
    },
    explain: {
      spec_id: "insight_13",
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
            <p className="text-sm text-slate-500">
              {copy.listSub}
              <span className="mx-1.5 text-slate-300">·</span>
              {snap.periodLabel}
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {cards.map((card) => (
              <div
                key={card.label}
                className="rounded-md border border-slate-200 bg-slate-50 px-3 py-3 dark:border-slate-600 dark:bg-slate-800/60"
              >
                <p className="text-xs text-slate-500">{card.label}</p>
                <p className="mt-1 text-lg font-semibold tabular-nums text-slate-900 dark:text-slate-50">
                  {card.value}
                </p>
              </div>
            ))}
          </div>
        </header>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.summaryTitle}</h3>
          <Prose lines={copy.summary} />
        </section>

        <section className="space-y-6">
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.methodTitle}</h3>
          <section className={prose}>
            <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{copy.backgroundTitle}</h4>
            <Prose lines={copy.background} />
          </section>
          <section className={prose}>
            <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{copy.compareTitle}</h4>
            <p>{copy.compareLead}</p>
            <ul className="list-disc ml-5 space-y-1.5">
              {copy.compare.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <p>{copy.compareNote}</p>
          </section>
          <section className={prose}>
            <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{copy.defineTitle}</h4>
            <p className="font-medium text-slate-800 dark:text-slate-100">{copy.defineFormula}</p>
            <Prose lines={copy.define} />
          </section>
        </section>

        <section className="space-y-10">
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.bodyTitle}</h3>

          <section className={prose}>
            <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{copy.s1Title}</h4>
            <Prose lines={copy.s1} />
            <table className="data w-full text-[13px]">
              <caption className="sr-only">전국 비교 결과</caption>
              <thead>
                <tr>
                  <th className="text-left">산출 기준</th>
                  <th>비교집단</th>
                  <th>토지 단독거래가 높은 집단</th>
                  <th>비교집단 비율</th>
                  <th>거래수 가중 비율</th>
                  <th>가격차이 중앙값</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>중앙값</td>
                  <td>887</td>
                  <td>312</td>
                  <td>35.2%</td>
                  <td>22.6%</td>
                  <td>−12.8%</td>
                </tr>
                <tr>
                  <td>평균값</td>
                  <td>887</td>
                  <td>290</td>
                  <td>32.7%</td>
                  <td>21.4%</td>
                  <td>−11.6%</td>
                </tr>
              </tbody>
            </table>
            <p className="text-slate-600 dark:text-slate-300">{copy.s1Caption}</p>
          </section>

          <section className={prose}>
            <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{copy.s2Title}</h4>
            <Prose lines={copy.s2} />
            <table className="data w-full max-w-xl text-[13px]">
              <caption className="sr-only">지역 규모별 중앙값 비교</caption>
              <thead>
                <tr>
                  <th className="text-left">지역</th>
                  <th>비교집단</th>
                  <th>토지 단독거래가 높은 비율</th>
                  <th>가격차이 중앙값</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>서울</td>
                  <td>43</td>
                  <td>39.5%</td>
                  <td>−7.1%</td>
                </tr>
                <tr>
                  <td>광역시</td>
                  <td>139</td>
                  <td>58.3%</td>
                  <td>+3.7%</td>
                </tr>
                <tr>
                  <td>일반시</td>
                  <td>464</td>
                  <td>37.3%</td>
                  <td>−10.1%</td>
                </tr>
                <tr>
                  <td>군</td>
                  <td>241</td>
                  <td>17.0%</td>
                  <td>−38.3%</td>
                </tr>
              </tbody>
            </table>
            <details className="rounded-md border border-slate-200 px-3 py-2 dark:border-slate-600">
              <summary className="cursor-pointer text-sm font-medium text-slate-800 dark:text-slate-100">
                {copy.detailLabel}
              </summary>
              <table className="data mt-3 w-full text-[13px]">
                <caption className="sr-only">지역 규모별 거래수 가중과 평균값 기준</caption>
                <thead>
                  <tr>
                    <th className="text-left">지역</th>
                    <th>거래수 가중 비율</th>
                    <th>평균값 기준 비율</th>
                    <th>평균값 기준 가격차이 중앙값</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>서울</td>
                    <td>40.2%</td>
                    <td>37.2%</td>
                    <td>−8.1%</td>
                  </tr>
                  <tr>
                    <td>광역시</td>
                    <td>50.0%</td>
                    <td>56.1%</td>
                    <td>+2.2%</td>
                  </tr>
                  <tr>
                    <td>일반시</td>
                    <td>25.5%</td>
                    <td>34.1%</td>
                    <td>−8.6%</td>
                  </tr>
                  <tr>
                    <td>군</td>
                    <td>7.3%</td>
                    <td>15.8%</td>
                    <td>−42.2%</td>
                  </tr>
                </tbody>
              </table>
              <p className="mt-2 text-slate-600 dark:text-slate-300">
                거래수 가중은 토지 거래수와 건부지 거래수 중 적은 쪽을 무게로 합니다. 평균값 기준은 각
                비교집단의 평균 단가로 가격차이를 만든 결과입니다.
              </p>
            </details>
          </section>

          <section className={prose}>
            <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{copy.s3Title}</h4>
            <Prose lines={copy.s3} />
            <table className="data w-full max-w-xl text-[13px]">
              <caption className="sr-only">주거지역 단독·다가구 비교</caption>
              <thead>
                <tr>
                  <th className="text-left">산출 기준</th>
                  <th>비교집단</th>
                  <th>토지 단독거래가 높은 비율</th>
                  <th>거래수 가중 비율</th>
                  <th>가격차이 중앙값</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>중앙값</td>
                  <td>363</td>
                  <td>56.7%</td>
                  <td>55.0%</td>
                  <td>+3.7%</td>
                </tr>
                <tr>
                  <td>평균값</td>
                  <td>363</td>
                  <td>54.5%</td>
                  <td>52.9%</td>
                  <td>+4.0%</td>
                </tr>
              </tbody>
            </table>
          </section>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.limitsTitle}</h3>
          <p>{copy.limitsLead}</p>
          <Prose lines={copy.limits} />
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.closeTitle}</h3>
          <Prose lines={copy.close} />
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.relatedTitle}</h3>
          <Prose lines={copy.related} />
          <p>
            <a href={copy.relatedHref} className="text-slate-800 underline dark:text-slate-200">
              {copy.relatedLink}
            </a>
          </p>
        </section>
      </article>
    </>
  );
}
